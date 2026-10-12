# S3：Evidence 与冻结恢复

## EvidencePack 与公开引用

`backend/rag/evidence.py:_document_parts` 为叶子渲染文件/Sheet/真实行；父块明确标记
“父块正文；命中行：2、6”，来源截断显示提示。标题计入原 maximum_characters，保留
原候选顺序、整块优先、fallback 和每块预算；配置名 tokens 沿用既有字符代理实现，
不将本轮称为精确 Token 计数。fallback 投影仅保留实际呈现的文本，并标记正文截断。

`evidence_trace` 保存实际入选顺序；`audit_citations` 检查 `[n]`/`[n,m]`，排除代码和
Markdown 链接，不凭检索排名替代入选位置。非法编号移除并计数，不吞掉 Schema 错误，
不重编号，不判断事实 entailment。`audit_trace_citations` 对旧未记录入选集合的 Trace
保持兼容，不猜测当时预算。

`backend/tools/knowledge.py:_render_rag_result` 为正常回答写入 Agent 实际预算的
EvidencePack；澄清/拒答在尚未构建 Answer pack 时显式空集合，不把候选排名当引用。
`backend/agent/runtime.py:_finish` 发布确定性审计后的最终内容/Trace；终端缓冲输出
同一内容。非终端流的早期数字只是文本，最终 message.completed 为权威版本。
`backend/runs/agent_executor.py:_resume_answer_prompt` 重建同样预算并写入 result Trace，
调用方在重建后才读取 initial_rag_trace，避免传入旧 selection。

## Checkpoint 约束

| 修改位置 | 行为 |
| --- | --- |
| `documents/retrieval.py:RetrievalSnapshot.to_payload/from_payload` | 128 KiB、最多 128 target/10000 version；重新构造并比对 Tenant + version + L3 filter，拒绝扩大 scope |
| `runs/request_context.py:restore_rag_retrieval_snapshot` | Run-local 锁内恢复，拒绝与已有快照重绑定 |
| `rag/pipeline.py:_initial_state/_retrieve_for_state` | 初始冻结并跨子问题传递；`_copy_jsonable_doc` 复用正式白名单，保留 provenance |
| `rag/checkpoint_runner.py:_compact_hitl_state` | annotations 白名单；元数据 Trace 最多 64 chunks、4 子 Trace；去正文/context/docs/sub_results；保留 frozen snapshot，总计 256 KiB |
| `_compact_resume_result` | 为恢复后的回答保留必要、有界证据（最多 64），总计 256 KiB；不是全文数据库 |
| `assert_snapshot_available` | 既有 Catalog 检查删除/READY 或未清理、pending cleanup 的替换旧版本；不替换 frozen IDs |

恢复前仍经过原 Run/Thread/用户/一次性 token/权限校验。快照 Tenant 不匹配、已删除、
已清理、Collection 不一致均 fail closed。旧暂停 Checkpoint 缺少 frozen snapshot 返回
`RUN_STATE_CONFLICT`，要求新问题；这是明确兼容限制，不静默访问新 current。
已完成旧结果/历史消息正常文件级显示。原一小时 cleanup grace 与 Index Worker 不变。

## 验证层级

原生 LangGraph HITL 测试：新 RequestContext 恢复同一 Snapshot，不再次选择 current，
叶子 anchor 不丢失。Catalog fake 测试撤销/cleanup/替换版本；原 PostgreSQL Run/Checkpoint
测试继续执行。真实 API/SSE/历史联调见 [前端报告](s3-frontend-citations.md)。
本轮没有在真实服务上主动替换/删除文档再恢复 HITL；这类竞态由测试验证，不声称真实
并发清理实验已经完成。没有延长历史版本存储期限。
