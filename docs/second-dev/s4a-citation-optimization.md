# S4-A 实现与验证

日期：2026-10-12。设计、根因及边界见 [证据归因设计](s4a-evidence-attribution-design.md)，真实指标见 [开发集评测](s4a-evaluation.md)。不是 S4-B/C，不改路由策略或质量 Gate。

## 本轮文件与函数

| 文件 | 具体改动 |
| --- | --- |
| `backend/rag/utils.py` | `_merge_to_parent_level` 保留真实命中 L3 正文；`dedupe_documents` 合并有界正文集合，原检索排序不变 |
| `backend/rag/evidence.py` | `citation_leaves` 作用域/来源/hash 校验；`pack_evidence(question=...)` 回答专用细粒度组装；EvidencePack 成本/降级统计 |
| `backend/schemas/rag.py` | `RagTraceFields.citations_belong_to_selected_evidence` 验证原检索或父块命中叶子的归属；字段不变 |
| `backend/rag/pipeline.py` | `_copy_jsonable_doc` 保留受限私有正文，公开来源继续白名单投影；图节点和拓扑不变 |
| `backend/rag/checkpoint_runner.py` | `_compact_resume_result` 复用同一安全投影；暂停状态/原 Snapshot 校验不变 |
| `backend/tools/knowledge.py` | `_render_rag_result` 给回答 Pack 传当前问题，拒答/澄清分支不变 |
| `backend/runs/agent_executor.py` | `_resume_answer_prompt` 给同一 Pack 传原问题和用户补充 |
| `backend/evaluation/runtime.py` | `_evidence_text`、`_generate_answer`、`_judge_answer`、`_execution_result` 编号一致；原 identity JSON 增加 context/unit 标记及实测 Pack 成本，不改变 Evaluation Schema/评分算法 |
| `scripts/audit_rag_citations.py` | 原严格审计保持，附加行级 P/R、精确覆盖、过宽、漏引；新增叶子不污染原 retrieval population |
| `tests/test_evidence_attribution.py` | 21 个确定性用例覆盖公开 Pack、检索 Provider 边界、身份、降级、有界恢复和 N+1 |
| `tests/test_rag_citation_audit.py` | 增加派生叶子不得放大覆盖分母的回归 |
| `frontend/src/utils/ragSources.spec.ts` | 增加父块检索/叶子引用的历史 JSON 投影测试，不改生产 Vue/TS 类型或 UI |
| `README.md`、`CONTEXT.md`、`docs/adr/0027-rag-provenance-and-frozen-resume.md` | 同步本次既有 Evidence 投影语义与入口说明 |
| 本目录三份 `s4a-*.md` | 设计、实现、实际评测与风险 |

本轮没有改 Parser、ParentChunkStore、Milvus writer/schema、PostgreSQL migration、API route、DeepSeek 客户端、LangGraph 拓扑、Rerank 或 Gate。以上文件已有 S1.5/S2/S3 未提交内容，均保留；不把整个 Git dirty diff 冒充本轮改动。

## 自动化验证

使用官方 WSL `Ubuntu-24.04` 锁定虚拟环境 `/home/lenovo/.local/share/supermew/venv/bin/python`，不是全局 Python。命令在仓库根执行，下列 `python` 指代该解释器；完整 JUnit 放在 `.artifacts/synthetic-enterprise/s4a/`。

```bash
python -m pytest tests/test_evidence_attribution.py tests/test_rag_citation_audit.py -q --junitxml=.artifacts/synthetic-enterprise/s4a/attribution-final.xml
python -m pytest tests/test_evidence_attribution.py tests/test_excel_provenance.py tests/test_rag_provenance_contract.py tests/test_rag_evidence.py tests/test_rag_trace_schema.py tests/test_native_checkpoint_hitl.py tests/test_rag_evaluation_judge_runtime.py tests/test_rag_eval_adapters.py tests/test_rag_eval_cli.py tests/test_rag_citation_audit.py tests/test_rag_short_circuit.py tests/test_rag_fault_injection.py tests/test_rag_retrieval_targets.py tests/test_rerank_stage.py tests/test_agent_runtime.py tests/test_rag_evaluation.py tests/test_rag_evaluation_jobs.py tests/test_rag_evaluation_routes.py tests/test_run_agent_execution.py tests/test_run_event_contract.py tests/test_rag_parent_scope.py tests/test_rag_latency_guards.py tests/test_run_routes.py tests/test_run_service.py -q --junitxml=.artifacts/synthetic-enterprise/s4a/backend-final.xml
python scripts/generate_rag_eval_schemas.py --check
python scripts/generate_contract_types.py --check
python scripts/evaluate_rag.py validate --dataset evals/rag/synthetic_enterprise/dataset_dev_v1.json
```

聚焦曾执行23 passed，最后增加一个独立版本保留测试后为24个用例，均包含在扩大最终结果：298 passed、2 failed、16 subtests passed，不重复累加。两失败始终是历史 CLI baseline 的 corpus/source fingerprint 不匹配，不关闭校验、不改 fingerprint、不覆盖 baseline。首次误写不存在 `test_run_agent_executor.py` 导致零用例运行，已改用实际 `test_run_agent_execution.py`；不能将错误命令列为通过。

初始 TDD 两个失败分别是缺少 question 参数和 Trace 不接受真实派生叶子，随后修复；第三个同身份正文哈希冲突回归先失败后通过。新增检索测试先沿用仓库 fake module loader 暴露 NumPy 重载导入冲突，提前加载正式 Checkpoint 模块后单文件与扩大测试通过；不修改 NumPy 或生产依赖。一次 WSL 启动返回 `Wsl/Service/0x8007274c`，独立重试成功，没有改全局环境。

Ruff changed-file check/format check、两类 Schema 生成检查、20-dev Dataset Validate、原生Offline Contract Score 已通过。前端五文件41 passed，全量230 passed/27 files，`npm run typecheck`、lint和build:check（初始JS gzip73.64KiB）通过，无生产前端改动。实际 SSE、引用点击、历史刷新由仓库既有 Playwright Smoke 驱动验证，资产独立保存在 s4a，不重写组件。

## 例子与边界

真实 UI `run_8f220e7b3b9e46b8af5119e4af790d12`：NX-003 库存 88 台 [1]；[1] 是 `docver_f515043826194db68855bdd7aa3c3a96::inventory.xlsx::p0::l3::2`，库存第 4 行。仍显示其他“入选但未引用”单元，未隐藏全部引用来制造准确率。

明确降级不是成功定位：无正文、hash 损坏、缺失叶子、来源截断均保留父块，不赋予直接行来源。跨 Tenant/Version/KB/ACL/Index/section/文件不一致抛错。多个版本记录不由本阶段挑最新，型号匹配不等于事实验证。真并发删除/清理后的在线 HITL 恢复仍未现场重复；继承原版本可用性检查和自动化冻结快照测试，不能声称永久可回放索引。
