# S4-D：健康 Rerank 的 20 题真实开发集基线

日期：2026-10-12（Asia/Shanghai）。在用户明确授权模型调用及仅重设 `account_id=3` 后，执行**一次**正式持久 Evaluation Job。此前四题 Smoke 独立保留于 [Smoke 报告](s4d-rerank-end-to-end-smoke.md)，不混入本轮分母。

## 结论与边界

Job `rag_eval_654bb3d8fef148a19803db409859b879` 为 `succeeded`，实际完成 20/20；原生 Report 为 **FAIL**：Case Pass 14/20，未达到原有 0.95 门禁。执行完成不等于质量通过。

31 次正式检索链路中的 Rerank 全部成功，全部单次 Provider attempt、零回退、零错误。本轮没有 HTTP 400、`PROVIDER_REQUEST_INVALID` 或 Provider Timeout。由此获得了可保存的健康 Rerank 开发集基线，但未解决拒答、版本 Outcome 和澄清证据契约问题。

未运行冻结 60 题，未二次重测失败题，未上传任何问题/答案资产，未调整 NO_KNOWLEDGE、HITL、版本澄清、跨文档规划或评分门禁。未修改生产源码、正式 Schema/API 或测试语料，未 Commit/Push/Merge。

## 实际运行路径与环境

复用正式 Dataset 导入 API → Evaluation Job API → `backend.workers.evaluation` → `RagEvaluationRuntime.execute_case` → 原有 LangGraph 检索、Answer 及 Evaluator Judge。不是独立 RerankStage 测试，也不是另写的 RAG 模拟器。临时实验包装只记录同一次调用的候选身份、排序、分数、延迟和返回结果，不改变输入、输出、错误或排序策略。

运行前没有活动 Run、Index Job 或 Evaluation Job；通过正式 launcher 优雅关闭旧服务，再启用观测包装。结束后再次核实无活动任务，优雅移除包装，恢复 `python -m backend.launcher --no-reload --shutdown-timeout-seconds 30`。没有强杀活动任务。

最终 API Health 为 200；API、Indexing Worker、Evaluation Worker 及 launcher 的 Rerank 环境均与当前配置匹配；两个 Worker 心跳新鲜。PostgreSQL Schema 检查通过，原有 12 份文档全部 READY，Milvus 与 PostgreSQL 的真实身份、内容 hash、Parent/Vector Manifest 完整匹配，与 S4-B 的 Document ID、Document Version、Build 和 Catalog Index 均一致。未重建索引或清理共享数据。

当前测试隔离使用已有专用知识库及所有者，不宣称新建独立 Tenant；记录的 Tenant 为 `default`，读取时确认有效语料仅为这 12 份授权文档。只重设测试账号 3 的随机密码，正式登录/退出，密码及 Token 均不落盘。

## 配置与指纹

Rerank 来自正式 Settings/进程环境：`qwen3.7-text-rerank`，enabled=true，timeout=5s，min_score=0，candidate_limit=30，单文档字符上限 8000、总字符上限 60000。实际 31 个阶段都返回该模型身份、`rerank_applied=true`、`rerank_fallback_applied=false`。新网关绑定只记录摘要，不记录地址或密钥。

Answer/Grader/Evaluator 为 `deepseek-flash`，Model Profile `model_cca5c8be5c5b42d2b31449a8579aea38` v1；Fast 为 `deepseek-v4-pro`，Profile `model_489cb92681f943bca8364bde51e8fc3f` v1；各角色 timeout=30s。Rerank 不属于这四个持久 Model Profile 角色，必须同时保留环境和 live profile 收据，不能只凭 Model Catalog hash 判定配置相同。

Embedding 为 `BAAI/bge-m3`，Revision `5617a9f61b028005a4858fdac845db406aefb181`，CPU、1024 维。检索 top_k=8、candidate_k=30，最多 4 个子查询、并行度 2；Grader/Answer 证据预算仍使用原配置。

| 身份 | 本轮真实值 |
| --- | --- |
| Dataset（20 dev） | `7a2fde984e24ca3f7d2fe1a96bbaa82a20a6c92cbd4979e0ade3effb038155c2` |
| Corpus | `9c8144131a4d9a93be3621d80cd14691ee858b086f9a8650497dde5459ab049e` |
| Catalog Index | `6832df8a828ce611f321023be9e92ba78c377e14609ef36d9a789c7118ed9954` |
| Build | `ecd83a43735338e2f909223457682bffa7326b6abd589304b95190262b4a9f03` |
| Model Catalog | `11164a28bef4fd7b19c61e6764807fea9f18bb55d7a2fc6c0afed28351657469` |
| Source | `992b88cd8dc138198fc49ebfe0cecca0b2f6a0387ef5a1d1c0e90f0d98297f1c` |
| Live Profile | `5ce33b00b5ba65bc2e12ff2008ff0979bccdcfb629eda39155d3591b25e80afc` |

Profile ID 为 `nebula-s4d-healthy-rerank-dev-v1`。原生 Report 的 `retrieval_index_ids=[catalog-v1]` 是标签，不能冒充上面的真实 Catalog Index hash。前后 Source/Index 不变，详细身份在实验目录保存。

## 原生指标与引用审计

| 指标 | 实测 | 分母/说明 |
| --- | ---: | --- |
| Document Recall@5 | 82.35% | 17 个有 Gold Document 的 Case；原生逐题平均 |
| Document Recall@10 | 94.12% | 17 |
| Case Pass Rate | 70% | 14/20；包含 Outcome/HITL/Judge 等检查 |
| Answer correctness | 0.95 | 原生 Judge 平均分，20；不是人工答案准确率 |
| Groundedness | 0.93 | Judge，20 |
| Answer relevance / completeness | 0.965 / 0.945 | Judge，20 |
| Context relevance | 0.76875 | 原生可评样本 16 |
| Unsupported claim rate | 0.06 | Judge 平均分，20；不是六成或六个回答发生幻觉 |
| Retrieval / Generation / Judge Provider Failure | 均 0% | 各 20 |
| 请求耗时 Mean / P50 / P95 | 9501 / 7802 / 14626 ms | 20；原生 Case duration，非纯 Rerank 耗时 |
| Chunk Recall、MRR、nDCG | 未测 | 没有完整真实 Gold Chunk 映射 |
| 引用标号合法性 | 33/33 | 原生 Answer 数字标号与 EvidencePack 来源绑定审计；不等于 claim 蕴含准确率 |
| Excel 来源完整性 | 60/60 | 最终检索 XLSX chunk 的已知叶子来源完整 |
| 严格行级引用匹配 | 11/12 | Gold Excel 行集合与所引叶子行集合严格相等 |
| 行级 Precision / Recall | 11/11、11/12 | 来源身份集合，不是答案事实评分 |
| Citation recall（所有文档） | 未测 | 缺少完整非 Excel claim/section-to-chunk 映射 |

原生 Citation Precision/Recall 仍显示不可用；上面的辅助来源审计不替换原生 Evaluation Contract。缺失引用的可回答 Gold Case 为 `table_query_001`，没有过宽行级引用 Case。没有在本轮重新执行浏览器、SSE 历史重放或 Checkpoint 恢复；这些行为以此前独立 Smoke 的证据为边界，不能由本次 Worker Job 推断已全部验证。

| 题型 | Case Pass | Rerank 成功/回退 |
| --- | ---: | ---: |
| simple_fact | 5/5 | 5/0 |
| table_query | 4/5 | 5/0 |
| cross_document | 5/5 | 10/0 |
| no_answer | 0/3 | 3/0 |
| version_policy | 0/2 | 8/0 |

## 真实排序、延迟与安全边界

31/31 个阶段至少有一个输出候选改变排名，所有输出身份来自各自输入候选；Tenant、知识库、Document Version 均通过已保存索引身份检查。这里只证明当前授权数据上的隔离一致性，没有实施恶意 ACL 负向攻击测试。

RerankStage 耗时最小 176.2ms、中位 567.8ms、最大 1873.9ms（n=31），均小于配置 5s。不是先前独立 Stage 的 101ms，候选规模、准备及网络均会影响延迟；有限样本无超时不能证明未来不会发生 Timeout。没有人为故障注入，错误降级能力以既有测试/历史回退为证据，不计作本轮 live 回退成功。

代表排序变化来自 `ranking-analysis.json`，是 Parent 合并后的真实 Rerank 输入/输出，不用文件名替代 Chunk ID：

- `table_query_003`：库存 Parent `docver_f515043826194db68855bdd7aa3c3a96::inventory.xlsx::p0::l1::0` 保持 1→1、score=0.99489861；另一个叶子 `::p0::l3::102` 为 4→2、score=0.60726890。Stage 506.5ms，最终答案为 NX-003 可用库存 88 台、上海测试仓、更新日期 2026-10-01，精准来源物理行 4。排序中的叶子 102 并不等于最终引用行，必须查看 EvidencePack 的真实叶子归因。
- `cross_document_001`：功率子查询参数 Parent `docver_0c8b6bd223db4f8ab4c6637bea269583::product_specs.xlsx::p0::l2::6` 为 3→1、score=0.96196511；保修子查询新政策 `docver_87b8e52aad484ed9bde66d68c472ff92::aftersales_policy.html::p3::l3::0` 保持 1→1、score=0.87938153。分别 593.3/596.3ms，最终 Case Pass；但最终 Document Recall@5 仍为 0.5，不可把答对等同于前五全部必要文档覆盖。
- `table_query_001`：版本公告 `docver_1f639e93301d48b884d112d99823be42::release_notes.html::p2::l3::0` **本来就排第一**，重排仍 1→1、score=0.99831088；参数 Parent `::product_specs.xlsx::p0::l2::0` 为 4→2、score=0.99226739。不能声称 Rerank 把公告从低位提升第一而导致失败。

## 六个失败 Case 与源码定位

### table_query_001：版本澄清与下游证据缺失

问题“NX-001 的额定功率是多少？”，Gold 为当前参数 120 W。实际返回“硬件 1.0 为 130 W、2.0 为 120 W”，询问硬件版本；route=clarify、HITL=clarify、Outcome=INSUFFICIENT_EVIDENCE。初始 trace 中已有参数和版本公告，最终 `retrieved_chunks=[]`，缺少引用。

源码 `backend/rag/pipeline.py::grade_documents_node` 在 clarify/scope_select 下清空最终 docs/context/公开 retrieved_chunks；`backend/evaluation/runtime.py::_generate_answer` 直接返回 hitl_prompt，`_judge_answer` 使用最终 documents 构建证据。因此 Judge 对此题 groundedness=0.2、unsupported_claim_rate=0.8；它看到的是空证据，不能据此认定最初文档没有 130/120 W 及日期，更不能把该分数直接称为真实幻觉发生率。后续可单独设计澄清证据契约与当前版本选择规范，本轮不修改。观测没有完整 Grader 决策细节，排序变化与失败仅为同轮现象，尚无因果证明。

### no_answer_001 / 002 / 003：未编造数值，但拒答 Outcome 不符

问题对应不存在的 NX-901/902/903。三题实际都为 clarify、HITL=clarify、INSUFFICIENT_EVIDENCE，Gold 预期明确无知识拒答，Outcome/HITL 检查均失败。001/002 表述为找到相关内容但缺少对应参数记录；003 明确未找到型号并请求确认。没有生成不存在型号的功率值。

定位 `pipeline.py::_resolve_route`、`grade_documents_node` 与 `backend/rag/outcomes.py::outcome_for_status`；区分检索到相似型号与存在目标实体。Judge 对 001 的“找到相关内容”也指出最终空证据下的支撑不足。后续需独立讨论 NO_KNOWLEDGE/澄清边界，不以“0/3”误报三题均编造答案。

### version_policy_001 / 002：答案正确，Outcome 仍不符

两题明确询问硬件 2.0；实际分别回答 120 W、90 W，解释公告 130 W/100 W 对应旧版，并引用参数表与公告。原生 Judge 所有 Case checks 中 Judge 项均通过；Document Recall@5 均为 1.0。失败项仅 `outcome=false`，实际 route=answer、HITL=none，却为 INSUFFICIENT_EVIDENCE。

源码 `pipeline.py::synthesis` 对有文档但存在未完整覆盖子结果的情况保留 partial；`outcomes.py::outcome_for_status` 将非 answerable/no_knowledge 状态映射为 INSUFFICIENT_EVIDENCE。应进一步读完整子结果判定覆盖状态为何未提升，当前记录不足以断言具体哪个子问题触发 partial。不能把这两题称为版本回答错误，也不把 Outcome 强改为 ANSWERABLE 消除失败。

## 与 S4-B 历史结果的关系

S4-B Document Recall@5 为 73.53%，本轮为 82.35%；@10 均 94.12%。Case Pass 均 14/20，但旧 `table_query_003` 的 Snapshot Timeout 本轮未出现，新的 `table_query_001` 进入澄清。P50/P95 从 7924/16099ms 变为 7802/14626ms（两轮各 n=20）。旧 Rerank 全部回退，本轮 31 次成功零回退。

这是**描述性历史对照，不是严格单变量 A/B**：Rerank 网关与 Source 指纹已与 S4-B 不同，模型调用存在随机性。没有绕过 fingerprint 校验，也没有覆盖旧 baseline 来合并比较。历史 Snapshot Timeout 发生于 Rerank 之前，本轮不复现只能记为“未复现”，仍需独立调查 Milvus/快照读取链路，不能标为已修复。

## 执行与产物

使用 WSL Ubuntu-24.04 的锁定环境 `/home/lenovo/.local/share/supermew/venv/bin/python`，不是冲突的全局 Python。以下脚本由绝对路径执行；从 WSL `/` 调用即可，实验脚本内部切换仓库根目录。

```text
python .artifacts/synthetic-enterprise/s4d-rerank-baseline/inspect_environment.py environment-before.json
python .artifacts/synthetic-enterprise/s4d-rerank-baseline/run_evaluation.py
python .artifacts/synthetic-enterprise/s4d-rerank-baseline/summarize.py
python scripts/audit_rag_citations.py --artifacts .artifacts/synthetic-enterprise/s4d-rerank-baseline
python scripts/evaluate_rag.py validate --dataset evals/rag/synthetic_enterprise/dataset_dev_v1.json
python scripts/generate_rag_eval_schemas.py --check
python .artifacts/synthetic-enterprise/s4d-rerank-baseline/restore_services.py
python .artifacts/synthetic-enterprise/s4d-rerank-baseline/inspect_environment.py environment-final.json
```

上面给出仓库相对路径表示，实际 WSL 命令使用完整 Linux 路径；原生 Validate 退出 0、20 cases、指纹匹配，Schema check 退出 0，正式引用审计成功。此前两次辅助 WSL 命令因 `Wsl/Service/0x8007274c` 未启动，改为 `--cd /` 后成功；不是 Dataset 错误，也没有据此重跑模型 Job。本轮未重跑完整 pytest，不冒充此前测试数量为本轮测试结果；没有新业务代码需要回归。历史 fingerprint 测试问题未通过改指纹或关校验处理。

产物独立放在 `.artifacts/synthetic-enterprise/s4d-rerank-baseline/`：

- `persistent-job.json`、`persistent-cases.json`、`persistent-report.json/.md`：正式 API 获取的 Job、实际问题/回答、Judge、指标及原生渲染报告。
- `worker-observations.json`：同一次 Worker 输出转为原生 Observation Bundle；`stages.jsonl`、`ranking-analysis.json`：阶段前后排名、分数、延迟和身份，不含私有推理。
- `citation-audit.json`：正式 `scripts/audit_rag_citations.py` 的来源审计，不是第二套 RAG 框架。
- `environment-before.json`、`runtime-during-evaluation.json`、`environment-final.json`、`profile.json`、`index-identities.json`、`excel-index-diagnostics.json`：环境/配置/真实身份收据。
- `execution-receipt.json`：只创建一次完整 Job、20/20、冻结集未执行、Source/Index 未变。
- `final-verification.json`：原生 Observation/Report Schema 校验、Dataset Validate 与 Schema check 两项命令退出 0，恢复后的环境/配置不变量核验通过；`artifact-sha256.json` 保存 32 个静态产物的 SHA-256，不包含持续追加的当前服务日志。
- `comparison.json`：标明历史来源差异的描述性比较；`historical-integrity.json`：150 个旧 S4-A/B/Smoke 文件 hash 未变，排除会随旧 launcher 退出追加的标准服务日志及 Python 缓存。
- 只新增忽略目录中的实验脚本与本报告；临时观测已移除，正式服务保持运行。不保存密码、Token、私有网关地址或 reasoning_content。

当前已具备健康 Rerank 的新开发集基线。下一步需要用户选择要调查的契约问题；本轮到此停止，不自行修改算法、运行冻结集或再启动付费评测。
