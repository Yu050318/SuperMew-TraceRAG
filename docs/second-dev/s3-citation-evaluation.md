# S3：真实开发集引用审计与验收

日期：2026-10-12。结论：来源链与真实界面联调完成；质量 Gate **未通过**，不将 S3
引用增强称为检索/答案策略优化。仅运行 20 条 dev，60 条冻结题未执行、未调参。

## 真实运行与索引

复用官方 WSL 锁定 venv，FastAPI、Index/Evaluation Worker、PostgreSQL、Redis、Milvus
就绪；本轮外部模型 Smoke/20-dev 已获授权。正式 `LiveRagEvalAdapter` CLI 先运行 3 条
Smoke（table_query_003、cross_document_002、no_answer_001），再通过正式 API 创建
持久 Evaluation Job，由原 Worker 完成 20/20；没有第二个 RAG runner/Judge。

Job：`rag_eval_b321507f308e4d3eb5b4aee1c8260900`，succeeded 只表示执行完成，Report
passed=false。最终 UI Smoke 另用正式 Run/SSE，不与 Worker metrics 混合。

12/12 文档 READY；allowlist 只含 4 XLSX + 8 HTML。每份 source hash、PG Parent/Milvus
leaf 的真实 ID 集合/内容哈希均与 Manifest 精确一致；索引与 S2 相同，没有重新上传。
1916 leaves/2497 parents；Excel 700 leaves/65 parents。问题/答案/GT 均不在 corpus。

- Dataset：`7a2fde984e24ca3f7d2fe1a96bbaa82a20a6c92cbd4979e0ade3effb038155c2`
- Catalog index：`6832df8a828ce611f321023be9e92ba78c377e14609ef36d9a789c7118ed9954`
- Build：`ecd83a43735338e2f909223457682bffa7326b6abd589304b95190262b4a9f03`
- 原生 RAG source：`9a384a8b8b57f90532296f6dc49d0cce6a5c9b2dfd0df58ddb0efa5dbfa460b4`
- Corpus：`9c8144131a4d9a93be3621d80cd14691ee858b086f9a8650497dde5459ab049e`
- Model Catalog：`11164a28bef4fd7b19c61e6764807fea9f18bb55d7a2fc6c0afed28351657469`

Model Snapshot：Answer/Grader/Evaluator deepseek-flash，Fast deepseek-v4-pro；Embedding
为原 BAAI/bge-m3，远端 Rerank qwen3.7-text-rerank。profile.json 与原生 Report 保存
正式版本信息。原 source fingerprint 并不覆盖所有 Vue/Tool/Checkpoint 改动，另保存
`s3-source-manifest.json` 的文件 SHA-256，不伪称单个原生 hash 覆盖整个实现。

## 实际指标

| 指标 | 结果 | 分母/含义 |
| --- | ---: | --- |
| Document Recall@5 / @10 | 0.647059 / 0.764706 | 原生 17 个有 Gold Document 的适用 Case |
| Case Pass Rate | 0.55 | 20；不是回答准确率 |
| Judge answer_correctness / groundedness | 0.88 / 0.88 | 20；原生评分均值，不是二值 Accuracy |
| Judge completeness / answer_relevance | 0.875 / 0.91 | 20 |
| Judge unsupported_claim_rate | 0.09 | 20；不能据此证明没有编造 |
| Generation / Judge / Retrieval provider failure | 0 / 0 / 0 | 20；不等于远端 Rerank 全成功 |
| P50 / P95 | 5404 / 10899 ms | 20；原生 Case duration，非纯网关延迟 |
| Provenance Coverage | 22/22 = 100% | 最终 retrieved XLSX Chunk，有完整合法且真实映射的叶子来源 |
| Citation Validity | 26/27 = 96.30% | 原生 generated_answer 的数字 marker 次数，排除代码/链接 |
| Row-level strict exact accuracy | 1/12 = 8.33% | 12 个有核验 Gold Excel Row 的 dev Case；未引/额外行/缺行/未知来源均不通过 |
| Citation Recall、Chunk Recall/MRR/nDCG | 未测 | 缺少完整 Gold chunk/非 Excel section→chunk/claim→citation 标注 |

辅助 `scripts/audit_rag_citations.py` **只读原生 Job 导出**，不运行模型、不新增正式框架、
不改变 Gate。Gold 来自 S1 GT 中的 dev IDs；先用 S2 真实 L3 映射核验，再绑定本轮 READY
Version。候选、入选位置、回答引用分开；父块只展开 matched leaves，不展开全文覆盖行。
多 Excel 证据使用 version/file/sheet/row 联合集合精确相等判分：正确行与错误行混在一起
仍失败。未引用计失败，来源列表截断/未知映射为 indeterminate 且不计通过。此指标是
**来源行精度**，不是事实 entailment。Worker 导出未记录每块正文裁剪状态；本轮不声称
测过“裁剪后文本仍支持全部事实”，也不把完整行 metadata 当正文事实保证。

## 类型与代表 Case

| 题型 | n | Recall@5 | Case Pass Rate |
| --- | ---: | ---: | ---: |
| simple_fact | 5 | 1.0 | 1.0 |
| table_query | 5 | 0.8 | 0.8 |
| cross_document | 5 | 0.2 | 0.4 |
| no_answer | 3 | 未测 | 0 |
| version_policy | 2 | 0.5 | 0 |

| Case | 实际观测 | 来源/原因与后续建议 |
| --- | --- | --- |
| table_query_001 | 120 W / 130 W 转版本澄清，无最终引用 | 原 Grader clarify；不修改 HITL 策略 |
| table_query_002 | 正确 2850 CNY，但引用价格父块 20 行，Gold 仅 1 行 | 19 额外行；Parent Merge 宽证据不是精确事实归因 |
| table_query_003 | 正确库存 88，引用父块 24 行 | 23 额外行；UI 诚实显示集合，不伪称只有目标行 |
| table_query_004 | 60 W 与旧版 70 W 均说明，Excel 引用集合 2 行 | 1 额外行；不能仅“包含 Gold”就判准确 |
| cross_document_001 | 功率 155 W，但缺保修，转澄清；文本出现片段[4] | 无 Answer selection，1 个非法引用；候选/Grader 编号不等于答案引用 |
| cross_document_002 | Modbus RTU 与 DIN 导轨安装，引用 [2][6] | Excel 父块 4 行含 3 额外行；跨文档内容虽正确，行级来源不精确 |
| cross_document_003 / 005 | 功率可见，缺保修证据，转澄清 | 原政策召回缺口；引用增强不解决召回 |
| no_answer_001 | NX-901 未找到，要求型号/版本确认 | 未编造功率，但 outcome 仍 INSUFFICIENT_EVIDENCE，与预期拒答分类不符 |
| version_policy_001 | 正确 2.0=120 W，仍 insufficient outcome；引用 Excel 16 行 | 15 额外行与原 outcome 分类；不能据 Judge correctness=1 宣称 Gate 通过 |
| version_policy_002 | 正确 2.0=90 W；引用一条 Gold Excel 行 | 唯一严格行集合通过；原 outcome 仍未通过，不等于全 Case 通过 |

完整答案、命中真实 chunk IDs、正确/额外/缺失行和 Judge 见忽略目录的
`persistent-cases.json`、`citation-audit.json`；不在本文复制大段证据。
远端 Rerank PROVIDER_REQUEST_INVALID 回退仍在真实 UI Trace 可见，未修改兼容代码。
本轮不从检索 provider failure=0 推论 Rerank 没有问题。

## 自动化与复现

从仓库根，使用项目 venv 的 `python`/`ruff`（本机经 WSL），不用全局 Python：

```sh
python -m pytest tests/test_rag_provenance_contract.py tests/test_rag_citation_audit.py \
  tests/test_rag_trace_schema.py tests/test_rag_evidence.py tests/test_rag_outcomes.py \
  tests/test_knowledge_tool_outcomes.py tests/test_native_checkpoint_hitl.py \
  tests/test_rag_short_circuit.py tests/test_rag_retrieval_targets.py tests/test_rag_parent_scope.py \
  tests/test_document_retrieval_scope.py tests/test_milvus_retrieval_shapes.py \
  tests/test_rag_evaluation.py tests/test_rag_evaluation_jobs.py tests/test_rag_evaluation_judge_runtime.py \
  tests/test_rag_evaluation_routes.py tests/test_rag_eval_cli.py tests/test_rag_eval_adapters.py \
  tests/test_synthetic_enterprise.py tests/test_excel_provenance.py tests/test_excel_parser.py \
  tests/test_document_publication.py tests/test_milvus_writer.py tests/test_deepseek_structured_output.py \
  --junitxml=.artifacts/synthetic-enterprise/s3/backend-final.xml -q
python scripts/generate_contract_types.py --check
python scripts/audit_rag_citations.py --artifacts .artifacts/synthetic-enterprise/s3
```

大批相关回归最终执行：284 passed、21 subtests passed、2 failed，仅历史
`test_cli_scores_offline_baseline_and_writes_sanitized_reports` 与
`test_cli_returns_one_for_a_quality_regression`，错误为 baseline corpus/source identity
不同。未改旧 baseline 或关闭校验。收尾 Runtime/Run/Event 与最新补丁测试为
115 passed、12 subtests passed、0 failed，另外记录在 `runtime-final.xml/log`。
两组有重叠，不相加冒充独立数量。收尾加入的澄清空入选集合与 Agent 最终输出一致性
补丁由这些测试和最新真实 UI Run 验证；20 条 Job 执行的 RAG/Evaluation 代码未因此变化，
没有为获得更好结果再次运行 20 题。文件 SHA manifest 是最终源码状态，不冒充 Job
创建时的完整代码快照。
Ruff、生成 Schema check 通过。前端目录：

```sh
npm run test:unit
npm run lint
npm run build:check
```

229 passed / 27 files，含 typecheck；初始 JS gzip 73.64 KiB，原 Gate 通过。
运行产物全部在 `.artifacts/synthetic-enterprise/s3/`（gitignored）；模型密钥、密码、Token
没有保存。旧 baseline、数据库/Milvus Schema 未覆盖。源码修改清单在 source manifest
以及其他三份 S3 报告；S1.5/S2 原有脏工作区不计成本轮新开发。

## 下一步与验收限制

S3 来源投影、Schema、前端和原生 Worker 引用审计已具备进入 S4 讨论的依据，但当前
质量 Gate 未通过，不能当作质量优化验收通过。真实并发删除/清理后 HITL 恢复尚未现场
演练；单元/原生持久测试覆盖其拒绝与冻结不变量。

S4 可优先研究宽父块中的目标叶子归因、完整 claim/Gold source 标注、政策召回、版本
澄清与 outcome 分离、Rerank 网关回退，以及 Worker/CLI 差异；需要新的阶段授权，
本轮未实施这些算法改动，也不运行冻结 60 题。
