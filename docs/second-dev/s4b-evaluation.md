# S4-B：真实开发集对照评测

日期：2026-10-12。**跨文档目标已验证：三个原失败 Case 均完整回答，002/004 正例保持通过。完整正式 Job 已执行20/20，但质量 Gate 未通过；存在1次真实 Snapshot Provider 超时，不能宣称全量无回归或完全验收。** 本轮调用与仅 account_id=3 密码重设已获明确授权。没有执行冻结60题，没有进入S4-C/S4-D。

## 执行与失败记录

历史 A：原生 Job `rag_eval_3f17a6b0366d43bb817689e6906479ec`；38份历史资产SHA-256未变，不重跑、不覆盖。最终 B：`rag_eval_fedf90faa60c4754817def69d6d43c7e`，正式上传Dataset API→持久 Job→原 Evaluation Worker，20条状态completed。Observation、Answer、Judge、Report均来自原工作流，Job succeeded不等于Report passed。

首轮 `rag_eval_afecca7914de459c80e60027d229e137` 完成14条后在005 ValidationError中断，具体字段当时未捕获；单题原生CLI和Worker重跑成功，不能因此隐藏中断。第二轮 `rag_eval_c2d47c51103b41b19aaa9261d563f6a5` 完成10条后在001中断，脱敏诊断明确定位synthesis→EvidencePack：重复L3被附加父块来源，严格校验拒绝。修正现有dedupe边界、单测先红后绿、重启官方服务、重新3条Smoke后执行最终完整Job。**没有把失败轮部分结果拼成20条，也没有用重试成功值替换最终Job内失败Case。**

初次页面Run/SSE/历史重载Smoke通过：table_query_003的库存引用为真实Excel行来源；页面历史投影与事件来源一致。它不代表所有跨文档页面均经过浏览器复核，也不能替换最终Job的Provider超时。前两轮、单题诊断、前后Smoke、所有阶段观察均独立保存在ignored目录。

## 环境、索引与控制变量

官方Ubuntu-24.04锁定环境：`/home/lenovo/.local/share/supermew/venv/bin/python`，不是全局Python。Alembic current、PG/Redis/Milvus与API/Index Worker readiness实际核验，原12份文档全部READY，Parent/Milvus IDs/count/content_hash精确等于Manifest，无新增上传/版本/清理。专用知识库及12文档全部属于account_id=3，没有其他文档污染。密码/Token仅内存，不保存到资产。

Model Catalog `11164a28bef4fd7b19c61e6764807fea9f18bb55d7a2fc6c0afed28351657469` 与A相等。Answer/Grader/Evaluator deepseek-flash、Fast deepseek-v4-pro，原Profile v1/timeout30s；Embedding BAAI/bge-m3、revision `5617a9f61b028005a4858fdac845db406aefb181`、CPU/1024。程序逐字段确认模型、Embedding、RAG、Retrieval、Rerank原生配置与A相同：top_k8/candidate30、最多4子问题/并行2、Grader4800/每块1200、Answer12000字符代理预算。没有改Gold或原0.95 Gate。

| fingerprint | B |
| --- | --- |
| Source | e0e3d7ffc248c7708df70abeb480cedd8df0802a2a24540b14f987bffa56d5eb |
| Index（真实Catalog聚合身份） | 6832df8a828ce611f321023be9e92ba78c377e14609ef36d9a789c7118ed9954 |
| Corpus | 9c8144131a4d9a93be3621d80cd14691ee858b086f9a8650497dde5459ab049e |
| Dataset | 7a2fde984e24ca3f7d2fe1a96bbaa82a20a6c92cbd4979e0ade3effb038155c2 |
| 原生Profile | 63c71af39c61a714c93c9a768d710c3f174536b48eff282f1fe531681654a3fb |

Source因真实修改而改变；Profile包括新的实验profile_id，不能因hash不同就称基础配置改变。`catalog-v1`是原生Report标签，不冒充上表Index hash。包装器独立SHA清单在s4b-source-manifest.json，不混入正式Source计算。实际重新加载后执行，非仅磁盘hash推定进程代码。

重新加载时遇WSL Windows路径入口0x8007274c超时；一次启动因旧API仍占端口而自动停止。改用Linux绝对路径入口，核对无活动Run/Job、精确PID并正常停止旧launcher后恢复；未重置整个WSL或清理数据。另一次驱动从/启动导致Alembic相对migrations目录报错，修正实验驱动cwd为仓库根，未修改Migration。最终评测没有与pytest并行。

## 真实结果：不同指标分别解释

| 指标 | S4-A | S4-B |
| --- | ---: | ---: |
| Document Recall@5，17个Gold-doc Case | 70.59% | 73.53% |
| Document Recall@10，同17题 | 82.35% | 94.12% |
| 全部Gold文档在Top5，17题 | 10/17 | 9/17 |
| 全部Gold文档在Top10，17题 | 14/17 | 16/17 |
| 全部Gold文档实际入选Pack，17题 | 14/17 | 16/17 |
| 跨文档全部Gold文档入选，5题 | 2/5 | 5/5 |
| 跨文档全部Gold文档Top5/Top10，B | — | 0/5、5/5 |
| Case Pass Rate，20题 | 12/20（60%） | 14/20（70%） |
| 跨文档Case Pass，5题 | 2/5 | 5/5 |
| Judge correctness/groundedness | 0.92/0.94（n20） | 1.0/1.0（n19） |
| Judge completeness/unsupported_claim_rate，B | — | 0.9947/0.0026（n19） |
| Strict Row-level Accuracy，12Gold-row Case | 9/12 | 11/12 |
| Row Precision / Recall | 9/9、9/12 | 11/11、11/12 |
| Citation Validity（数字身份合法性） | 30/30 | 34/34 |
| 错误/过宽行Case | 0/12 | 0/12 |
| 缺少任何引用的预期可回答Case | 3/17 | 1/17（table_query_003超时） |
| 最终检索XLSX来源完整性 | 24/24 | 34/34 |
| P50/P95，n20，原生Report口径 | 6752/12870ms | 7924/16099ms |
| Retrieval Provider Failure | 0/20 | 1/20 |
| Generation / Judge Provider Failure，B | — | 0/20、0/20 |

Macro Document Recall不是“全证据覆盖率”；全部Gold文档实际入选也不是所有声明均被支持。跨文档5题的10个必需事实经最终答案、真实引用与既有合成语料人工复核均有支持，缺失事实0/10；此局部复核不是全20题正式Claim Accuracy指标。Chunk Recall/MRR/nDCG、完整Claim-to-Citation Recall、精确Token/费用均未测（没有Gold Chunk或充分归因标注/账单）；Judge均分和Case Pass均不叫回答准确率。

## 每题真实结果与开销

“检索请求/耗时”是已完成的授权Retriever调用次数与调用耗时之和ms，并行和不等于墙钟时间；Snapshot超时Case未进入Retriever，因此0不是健康空结果。全部完整身份/阶段/查询见stage-analysis.json。

| Case | 原生Case判定 | Outcome | Provider | 全程ms | 检索请求/累计ms |
| --- | --- | --- | --- | ---: | ---: |
| simple_fact_001 | 通过 | ANSWERABLE | — | 11569 | 1/2511 |
| simple_fact_002 | 通过 | ANSWERABLE | — | 6116 | 1/1265 |
| simple_fact_003 | 通过 | ANSWERABLE | — | 6183 | 1/1243 |
| simple_fact_004 | 通过 | ANSWERABLE | — | 5335 | 1/1100 |
| simple_fact_005 | 通过 | ANSWERABLE | — | 5149 | 1/416 |
| table_query_001 | 通过 | ANSWERABLE | — | 9377 | 1/1006 |
| table_query_002 | 通过 | ANSWERABLE | — | 7781 | 1/1160 |
| table_query_003 | 失败 | INSUFFICIENT_EVIDENCE | PROVIDER_TIMEOUT | 23130 | 0/0 |
| table_query_004 | 通过 | ANSWERABLE | — | 8549 | 1/926 |
| table_query_005 | 通过 | ANSWERABLE | — | 6035 | 1/708 |
| cross_document_001 | 通过 | ANSWERABLE | — | 9610 | 2/2154 |
| cross_document_002 | 通过 | ANSWERABLE | — | 8723 | 2/2165 |
| cross_document_003 | 通过 | ANSWERABLE | — | 10731 | 2/3720 |
| cross_document_004 | 通过 | ANSWERABLE | — | 7924 | 2/1947 |
| cross_document_005 | 通过 | ANSWERABLE | — | 9059 | 2/2185 |
| no_answer_001 | 失败 | INSUFFICIENT_EVIDENCE | — | 4952 | 1/764 |
| no_answer_002 | 失败 | INSUFFICIENT_EVIDENCE | — | 4190 | 1/505 |
| no_answer_003 | 失败 | INSUFFICIENT_EVIDENCE | — | 4528 | 1/733 |
| version_policy_001 | 失败 | INSUFFICIENT_EVIDENCE | — | 16099 | 4/6133 |
| version_policy_002 | 失败 | INSUFFICIENT_EVIDENCE | — | 12390 | 4/5288 |

分类通过：简单5/5、表格4/5、跨文档5/5、无答案0/3、版本0/2。最终Snapshot超时发生于table_query_003：run_rag_graph→_initial_state→get_or_resolve_rag_retrieval_snapshot→resolve_retrieval_snapshot→Provider checkpoint；尚未进入Fusion、Rerank或Grader，耗时23130ms，原生归类retrieval/PROVIDER_TIMEOUT。不是Excel行错引或政策编造，未把它归为NO_KNOWLEDGE。此前同题在本轮Smoke和真实页面成功，不能认定超时与新增逻辑存在因果关系，也不能把失败从分母剔除。

另5项失败是原无答案/版本Outcome策略：无答案证据不足仍clarify，版本题有事实但partial；没有出现新增虚构功率或期限，策略本阶段未改。详见原生Case答案/Judge。原生Gate仍0.95，当前0.70，Report passed=false。

## 资源预算与实际限制

最终20题记录30次已完成检索请求，平均1.5/Case；19个进入检索的健康Case均仅初始一轮，平均1轮/健康Case，缺失证据补检0次。5道跨文档均为2个既有子问题，37次完成的Planner/Grader结构化调用。对原001/003/005的single初检，B各增加1个初始子检索、1次Grader，Planner仍1次；新增实际Answer生成是完整回答相对原HITL的成本。全A没有同口径全部调用日志，不编造全20题差值。

本轮Live改善来自独立事实规划，不是“一次补检已在线验证”。补检成功/耗尽/日期歧义/空结果/错误适用政策/Provider故障仅由离线生产seam回归覆盖，仍有真实调用路径验证缺口。2025/2026离线测试验证日期进入Planner约束，不等于对所有真实购买日期业务准确性的穷举。

30次Rerank阶段全部fallback，记录PROVIDER_REQUEST_INVALID，未改网关协议；它们不是30个RAG Provider失败。Grader Pack最大4197字符，累计1块省略/20块截断，5跨文档关键证据仍入选；Answer Pack审计重组n16，最大11929≤12000字符，context最大8003；选取耗时均值0.786ms/最大2.001ms。此耗时是实际审计重组，不声称所有线上Pack调用延迟；其extra数据库/模型/Milvus=0仅限引用选择本身，不代表全RAG无额外调用。独立Dense/BM25、精确SDK重试次数及账单未测。

历史A与B不是随机因果实验；所有Rerank回退、网络波动、模型随机性及一次Snapshot超时限制结论。Top5全覆盖依然0/5，合成后政策可排在后部；尽管Pack完整支持答案，不能宣称排序问题已完全解决。

## 实际测试命令

以下从仓库根、官方锁定Python执行，输出置ignored s4b目录：

```sh
python -m pytest tests/test_excel_provenance.py -q -k duplicate_leaf
# 首次新增回归实际失败；修正后包含在下列扩大回归。
python -m pytest tests/test_rag_cross_document_coverage.py tests/test_evidence_attribution.py tests/test_excel_provenance.py tests/test_rag_provenance_contract.py tests/test_rag_evidence.py tests/test_rag_trace_schema.py tests/test_native_checkpoint_hitl.py tests/test_rag_evaluation_judge_runtime.py tests/test_rag_eval_adapters.py tests/test_rag_eval_cli.py tests/test_rag_citation_audit.py tests/test_rag_short_circuit.py tests/test_rag_fault_injection.py tests/test_rag_retrieval_targets.py tests/test_rerank_stage.py tests/test_agent_runtime.py tests/test_rag_evaluation.py tests/test_rag_evaluation_jobs.py tests/test_rag_evaluation_routes.py tests/test_run_agent_execution.py tests/test_run_event_contract.py tests/test_rag_parent_scope.py tests/test_rag_latency_guards.py tests/test_run_routes.py tests/test_run_service.py tests/test_provider_loop_bridge.py tests/test_provider_retry_policy.py -q --junitxml=.artifacts/synthetic-enterprise/s4b/backend-after-dedupe.xml
ruff check backend/rag/pipeline.py backend/rag/utils.py tests/test_excel_provenance.py tests/test_rag_cross_document_coverage.py
ruff format --check backend/rag/pipeline.py backend/rag/utils.py tests/test_excel_provenance.py tests/test_rag_cross_document_coverage.py
python scripts/generate_contract_types.py --check
python scripts/generate_rag_eval_schemas.py --check
python scripts/evaluate_rag.py validate --dataset evals/rag/synthetic_enterprise/dataset_dev_v1.json
python scripts/audit_rag_citations.py --artifacts .artifacts/synthetic-enterprise/s4b
```

最终27文件：**337 passed、2项历史failed、28 subtests passed，66.30秒**。新增15跨文档主用例+1去重回归无最终失败。前次25文件313 passed/2历史failed/19 subtests与最终集重叠，不累加；中间补丁误锚点造成3项失败已纠正，记录在实现文档。历史2项始终为CLI原baseline corpus/source fingerprint不匹配；未改hash、未关校验、未覆盖baseline。

前端此前本轮实际4文件40项通过：`npm run test:unit -- src/utils/ragSources.spec.ts src/components/Chat/References.spec.ts src/events/runEventReducer.spec.ts src/events/runEventStream.spec.ts`（cwd frontend），另有真实页面Smoke通过。两类生成Schema、20-dev Dataset验证、changed-file Ruff均通过；不宣称全仓库coverage/mypy或全量前端构建已执行。

实际模型执行驱动为ignored run_live.py：官方CLI run选3-dev→正式Dataset/Job API；observe.py只记录同一原图/Worker阶段。需要凭据时仅临时重设授权账号，重跑会真实计费，不应将该驱动当作日常无成本测试。资产包含persistent-job/cases/report、worker-observations、index-identities、stage-analysis、citation-audit、comparison、fingerprints、前两轮独立结果和SHA清单；不进入Git。问题/GT未上传到知识库，Judge使用参考答案是原Evaluation流程，不参与Retriever/Grader业务检索。

## 验收与下一阶段

已达到三个目标Case完整回答、两正例不退化、合法叶子/政策引用、离线无新增最终失败、冻结快照与授权Retriever复用；但**不标记全部验收通过**：全量Gate失败、存在新轮Snapshot可用性失败、Top5全覆盖不足，以及补检/2025边界的真实调用验证不完整。先复核Snapshot阶段可用性，再决定阶段验收；不能通过重复挑选成功结果或修改Gate解决。

已有足够证据制定S4-C无答案/版本Outcome改进任务；S4-D保留Rerank400兼容，均需用户下一阶段授权。停止在S4-B，不自行实现。引用身份/行规则与原baseline保持不变。
