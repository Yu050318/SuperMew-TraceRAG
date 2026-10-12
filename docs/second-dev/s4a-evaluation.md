# S4-A 真实开发集对照

日期：2026-10-12。结论：本轮已实现并实测细粒度来源；严格行级引用从 1/12 到 9/12，未产生额外引用行，但仍有 3 个 Gold-row Case 漏引，整体质量 Gate 未通过，延迟有回退。建议后续经授权进入 S4-B，不能声称原版 RAG 问题全部解决。

## 1. 实验身份与环境

A 是保存的 S3 原生 Job `rag_eval_b321507f308e4d3eb5b4aee1c8260900`；B 是唯一一次正式 20-dev Job `rag_eval_3f17a6b0366d43bb817689e6906479ec`，2026-10-12 16:57:35～17:00:10（UTC+8），20/20 succeeded。没有重新执行 A，没有运行冻结 60 题，没有覆盖原 baseline 或 S3 文件；S3 资产 SHA-256 前后相等。

先通过原生 `LiveRagEvalAdapter`/CLI 执行 table_query_003、cross_document_002、no_answer_001 三条检索 Smoke，再经正式登录/API/Index 校验、真实 Agent Run/SSE/Vue Smoke，最后通过正式 Evaluation Worker 生成 Answer/Judge/Observation/Report。仅重设授权的 account_id=3；密码、Token 只在内存，不存盘。

官方 Ubuntu-24.04 锁定虚拟环境；API、Indexing Worker、Evaluation Worker 经 `scripts/start-wsl.ps1` 重启。重启前查询确认无活动 Run/Job。PostgreSQL Schema current、Redis/Embedding/readiness 正常。12/12 原 Document Version READY，Manifest 的 count/IDs/metadata/content_hash 与 PostgreSQL、Milvus 精确一致；700 Excel L3 来源未改变。测试 Tenant=default 当前只有 allowlist 这 12 份，无其他业务语料。没有上传/重建文档，没有触碰 Questions/Answers/GT。

| 身份 | 值 |
| --- | --- |
| Dataset | `7a2fde984e24ca3f7d2fe1a96bbaa82a20a6c92cbd4979e0ade3effb038155c2` |
| Catalog Index ID（A/B 相同） | `6832df8a828ce611f321023be9e92ba78c377e14609ef36d9a789c7118ed9954` |
| S3 Source | `9a384a8b8b57f90532296f6dc49d0cce6a5c9b2dfd0df58ddb0efa5dbfa460b4` |
| S4-A Source | `c63a9853786012dd6d5378e1a6f3791b24376803bc6bece7c0d5e752379f747a` |
| 当前 Excel Build | `ecd83a43735338e2f909223457682bffa7326b6abd589304b95190262b4a9f03` |
| 冻结 Model Catalog（A/B 相同） | `11164a28bef4fd7b19c61e6764807fea9f18bb55d7a2fc6c0afed28351657469` |

Answer/Grader/Evaluator=deepseek-flash，Fast=deepseek-v4-pro，Profile v1/30s；Embedding=bge-m3 锁定 revision/1024 维；Rerank=qwen3.7-text-rerank。具体角色 Profile ID、完整 Snapshot、各格式历史 Build、Corpus/Profile hash 与源码 SHA-256 在 s4a 的 profile/index/receipt 中。原生 Report 的 `retrieval_index_ids=[catalog-v1]` 是 index_version 标签，不冒充上表 Catalog Snapshot hash。

真实 UI Run `run_8f220e7b3b9e46b8af5119e4af790d12`：NX-003 库存 88 台 [1]，来源为库存第 4 行真实 L3，点击可见；实时和刷新历史一致。观察到 Rerank `PROVIDER_REQUEST_INVALID`、attempts=1、fallback=true；不修复此独立问题。原生 Job Observation 没有逐 Case Rerank Trace，因此不能声称 20 条均成功 Rerank。

## 2. 实际指标

| 指标/样本 | S3 A | S4-A B |
| --- | ---: | ---: |
| 严格 Excel 行集合准确率，12 Gold-row Case | 1/12，8.33% | 9/12，75% |
| Citation Validity，原始数字 marker | 26/27，96.30% | 30/30，100% |
| 行级 Precision（已知来源集合，不是事实蕴涵） | 8/88，9.09% | 9/9，100% |
| 行级 Recall（同 12 个 Gold 行） | 8/12，66.67% | 9/12，75% |
| 至少一个直接叶子引用的 Gold-row Case | 1/12，8.33% | 9/12，75% |
| 过宽来源 Case（至少一额外行），分母全部 12 | 7/12，58.33% | 0/12，0% |
| 应回答 Case 无合法引用，分母 17 | 4/17 | 3/17 |
| 原 XLSX 检索单元 Provenance Coverage | 22/22 | 24/24 |
| 原生 Document Recall@5，17 eligible | 64.71% | 70.59% |
| 原生 Document Recall@10，17 eligible | 76.47% | 82.35% |
| Case Pass Rate，20 | 55% | 60% |
| Judge answer_correctness 均分，20 | 0.88 | 0.92 |
| Judge groundedness 均分，20 | 0.88 | 0.94 |
| Judge completeness 均分，20 | 0.875 | 0.91 |
| Judge answer_relevance 均分，20 | 0.91 | 0.9225 |
| 全请求 P50，n=20 | 5404ms | 6752ms |
| 全请求 P95，n=20 | 10899ms | 12870ms |

Precision 不因漏引变成“全部正确”：三个漏引仍在 Recall、严格行集合、精确覆盖和应回答 Case 分母中。过宽比例同时报告全部 12 及有 Excel 引用 Case 的口径（A 7/8，B 0/9）。Claim-to-citation Precision/Recall、完整 Citation Accuracy、Chunk MRR/nDCG/Recall 均未测：Gold 无完整真实 Chunk/事实标注，不能用文件名代替 Chunk ID。Judge 均分不是二元 Answer Accuracy，Case Pass 也不是回答准确率。

原生质量 Gate 的 case_pass_rate≥0.95，本轮实际 0.60，仍 failed。Generation/Judge/Retrieval provider failure 各 0/20；该统计不包含健康回退的远端 Rerank 请求错误。无答案 3 题没有为不存在型号编造功率，但仍 clarify/INSUFFICIENT_EVIDENCE 而非预期 NO_KNOWLEDGE；不称正确拒答策略已修复。

## 3. 全部 12 个有 Gold Row 的 Case

表中 `参数`=product_specs.xlsx/产品参数、`价格`=product_prices.xlsx/价格、`库存`=inventory.xlsx/库存；版本 ID 沿用 S2/S3 核验映射，完整四元组与真实 Chunk/hash 见 citation-audit/comparison/native export。`∅` 不是通过。

| Case | Gold | B 实际行 | 正确行 | 额外行 | 缺失行 | A→B 严格 | B 降级 | 最终答案复核/Judge correctness |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| table_query_001 | 参数2 | 参数2 | 参数2 | ∅ | ∅ | 失败→通过 | 否 | 2.0=120 W，1.0=130 W；1.0 |
| table_query_002 | 价格3 | 价格3 | 价格3 | ∅ | ∅ | 失败→通过 | 否 | 2850 CNY；1.0 |
| table_query_003 | 库存4 | 库存4 | 库存4 | ∅ | ∅ | 失败→通过 | 否 | 88 台；1.0 |
| table_query_004 | 参数5 | 参数5 | 参数5 | ∅ | ∅ | 失败→通过 | 否 | 2.0=60 W，1.0=70 W；1.0 |
| table_query_005 | 价格6 | 价格6 | 价格6 | ∅ | ∅ | 失败→通过 | 否 | 3550 CNY；1.0 |
| cross_document_001 | 参数82 | ∅ | ∅ | ∅ | 参数82 | 失败→失败 | 未进入回答 Pack | 只给155 W，未给24个月；0.5 |
| cross_document_002 | 参数83 | 参数83 | 参数83 | ∅ | ∅ | 失败→通过 | 否 | Modbus RTU+断电接线/DIN导轨；1.0 |
| cross_document_003 | 参数84 | ∅ | ∅ | ∅ | 参数84 | 失败→失败 | 未进入回答 Pack | 只给165 W，未给24个月；0.5 |
| cross_document_004 | 参数85 | 参数85 | 参数85 | ∅ | ∅ | 失败→通过 | 否 | MQTT+断电接线/DIN导轨；1.0 |
| cross_document_005 | 参数86 | ∅ | ∅ | ∅ | 参数86 | 失败→失败 | 未进入回答 Pack | 只给10 W，未给24个月；0.5 |
| version_policy_001 | 参数2 | 参数2 | 参数2 | ∅ | ∅ | 失败→通过 | 否 | 2.0取120 W、解释旧130 W；1.0 |
| version_policy_002 | 参数3 | 参数3 | 参数3 | ∅ | ∅ | 通过→通过 | 否 | 2.0取90 W、解释旧100 W；1.0 |

有编号回答共 14 个 Case，本轮 Pack 降级数为 0，不代表降级路径不存在：无正文/hash异常/截断场景已自动化验证。三个保修 Case 进入澄清，没有 Answer Pack；“未进入”不能写成“安全降级精确定位成功”。

## 4. 类型结果与剩余失败

| 类型 | Case数 | A→B Case通过 | A→B Document Recall@5 |
| --- | ---: | --- | --- |
| simple_fact | 5 | 5→5 | 100%→100% |
| table_query | 5 | 4→5 | 80%→100% |
| cross_document | 5 | 2→2 | 20%→20% |
| no_answer | 3 | 0→0 | 无 Gold Document，未测 |
| version_policy | 2 | 0→0 | 50%→50% |

重点十例（原问题、完整原始回答、citation ID/Chunk、Gold 与 Judge 均在 comparison.json）：

1. table_query_002：价格答案完全相同 2850 CNY；引用从20行/19多余改为真实价格第3行。根因/修复在 Parent Merge + Answer Pack，非价格计算优化。
2. table_query_003：仍88台；24行/23多余改为库存第4行；另有真实 SSE/历史点击验证。耗时12870ms，不能忽略该性能样本。
3. table_query_004：仍60 W及旧70 W；原引用额外参数第15行不再关联。旧版本解释由 HTML 公告编号支撑，不将两版本假定成一个行。
4. cross_document_002：仍 Modbus RTU 和安装要求；原参数82/83/86/89行集合改为83行，并独立引用安装 HTML。未漏掉第二文档事实。
5. version_policy_001：仍120 W及旧130 W；16行改为参数第2行，公告独立引用；outcome仍INSUFFICIENT_EVIDENCE，Case未通过，来源优化不能掩盖分类问题。
6. version_policy_002：原已严格通过，本轮仍参数第3行、90 W和旧100 W；没有牺牲已正确来源；outcome仍失败。
7. table_query_001：原 clarify，本轮 answer并引用参数2行。Grader/版本澄清未改，这部分 Recall/Case Pass 增益不能归因于引用补丁，存在模型随机性。
8. cross_document_001/003/005：初始检索有各型号功率，缺保修政策；原 `grade_documents_node` / `_resolve_route` 走 clarify并清空 final docs。Worker返回 Grader HITL prompt，无独立来源编号。仅部分答案，保修24个月和引用均缺失；留给 S4-B 的跨文档覆盖/澄清决策，不在 S4-A 扩检索。
9. no_answer_003：没有编造 NX-903 功率，但澄清提示“是否指NX-003（130 W，硬件1.0）”。这是 Grader prompt 中未经最终 EvidencePack 引用核验的业务建议，不把它称为本阶段已验证事实；应在 S4-B 检查拒答与澄清输出约束。
10. 三无答案及两版本冲突 Case：实际失败检查分别是 hitl/outcome、outcome；不是新增 Provider 故障。来源严格通过并不能使领域决策自动通过 Gate。

## 5. 成本与实验限制

本轮来源选择零额外 Milvus 查询、零数据库查询、零模型调用；无 N+1，Provider 边界测试验证一次原 Hybrid、一次原父块查询即可完成。

14 个编号回答的实际审计重组：selection_ms 均值0.618、最大1.873；额外保留的无编号父块上下文累计27191字符、均值1942.21、最大4784；完整 Pack 最大7001字符，未超12000字符代理预算。该均值只统计实际 audit reassembly，不涵盖 Answer/Judge 所有 pack 调用，也不是运行总延迟或 Token 数。S3 未持久化同口径 Pack 字符成本，不能伪造 A/B 精确 Token 差值或费用节省。

P50 增加1348ms（24.94%），P95 增加1971ms（18.08%）；本轮真实性能没有改善。n=20、模型随机性、远端网关/Rerank回退及前几个 Case 与本地验证短时重叠，均限制因果推断。只报告受控开发实验，不声称生产因果效果；后续需独立重复/并发/Token观测，不能据此调整 Gate。

## 6. 测试与可执行命令

后端扩大最终：298 passed、2项历史 fingerprint failed、16 subtests passed；新增21个归因主用例及1个审计回归已包含，不另累加。前端全量230 passed/27 files；41个来源/SSE聚焦测试是重叠子集。typecheck、lint、build:check及bundle gate通过，初始JS gzip73.64KiB。Ruff changed-file check/format check、Dataset Validate、Evaluation/Contract Schema check、原生 Offline Contract Score通过；Offline Score只是contract_smoke，不冒充这次Live质量。

两历史失败：`test_cli_scores_offline_baseline_and_writes_sanitized_reports`、`test_cli_returns_one_for_a_quality_regression`，原因 corpus/source fingerprint 与旧baseline不同。保留失败、原baseline和fingerprint检查。完整命令与早期失败过程见 [实现验证](s4a-citation-optimization.md)。没有声称全仓库coverage/mypy或在线并发清理/HITL故障注入已通过。

```bash
# 仓库根，使用上述锁定虚拟环境；已授权且仅开发集
python scripts/evaluate_rag.py run --dataset .artifacts/synthetic-enterprise/s4a/dataset_smoke_dev.json --corpus-path evals/rag/synthetic_enterprise/upload_corpus --gates evals/rag/live_gates_v1.json --observations .artifacts/synthetic-enterprise/s4a/smoke-observations.json --report .artifacts/synthetic-enterprise/s4a/smoke-report.json --profile-id nebula-s4a-leaf-citations-dev-v1 --index-id 6832df8a828ce611f321023be9e92ba78c377e14609ef36d9a789c7118ed9954 --timeout-seconds 60
# 20条通过官方 /v1/rag-evaluations/datasets + jobs 提交原生Worker，不是简化RAG
# 已完成数据的离线辅助审计，不发模型请求
python scripts/audit_rag_citations.py --artifacts .artifacts/synthetic-enterprise/s4a
```

Smoke与正式Job已经执行，请勿为复核再次运行批量模型。Observer `run_live.py`、浏览器驱动、Job/Case/Report、worker-observations、comparison、Source manifests、截图、readiness、索引身份、JUnit、final-receipt均放在 `.artifacts/synthetic-enterprise/s4a/`，被.gitignore忽略；运行资产只在仓库文档中保存脱敏说明。

## 7. S4-B 建议（未实施）

有可信来源优化结果与9个准确定位例子，可以在另行授权后进入 S4-B，但不能宣称质量验收通过。优先处理保修跨文档覆盖、健康无答案的拒答/澄清边界、版本冲突 outcome；分别定位 `pipeline.grade_documents_node`/`_resolve_route`/`_grade_update`、复杂问题 synthesis 的覆盖缺口，与 Rerank 网关400独立处理。补充正式 Evaluation 的每 Case route/Rerank 公开遥测与claim-to-citation Gold，再做原生开发集实验；冻结60题继续封存。本阶段停止，不提交、推送、合并、不进入下一阶段。
