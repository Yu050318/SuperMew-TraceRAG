# S4-E：60 条冻结测试集正式评测

日期：2026-10-13（Asia/Shanghai）。结论：**唯一一次正式 Job 完成 60/60；原生 Quality Gate 未通过**。未自动重跑或修改冻结实现。逐题解释见 [质量复盘](s4e-quality-analysis.md)，预检、依赖与完整 SHA 见 [冻结准备](s4e-freeze-readiness.md)。

## 1. 执行与独立性

用户批准最小模型预检、一次 60-test Job、仅重设测试账号 `account_id=3`。此前冻结 Dataset 导入和 Job 均为 0；冻结分布为简单事实 15、表格 15、跨文档 15、无答案 7、版本政策 8。与 20-dev ID 不相交，合计 80，内容与原 Dataset 一致，无 HITL 补充答案。正式结束后才逐题复盘。

| 项目 | 实际值 |
| --- | --- |
| Dataset | `nebula_frozen_v1` / `dataset_frozen_v1.json` |
| Dataset ID | `rag_dataset_c9b45ff934ce4accb88f614df778dcfb` |
| Job ID | `rag_eval_64d66d2ec2aa4d2bb047e1df01f0d7b6` |
| 执行 | 原生 Dataset/Job API + 正式 Evaluation Worker |
| 终态 / Observation | succeeded / 60；Worker claim attempts=1 |
| 开始 / 结束 | 2026-10-13 17:01:29 / 17:09:38（北京时间） |
| Job 墙钟时长 | 约 489.16 秒，非单题或首 Token 延迟 |
| baseline_job_id | null；历史 20-dev 仅作参考 |
| Gate | 原生 live_rag + case_pass_rate≥0.95，未变 |

只重设账号 3 的 password_hash，密码和 Token 仅在内存。一次 Dataset POST、一次 Job POST，不重放 mutating POST；无完整 CLI 模型 Round、临时 Judge 或另一套 RAG Runner。未上传答案资产，未改 Gold、Expected Outcome、Gate 或评分算法。

## 2. 源码、配置和索引身份

| 身份 | 实际值 |
| --- | --- |
| Git HEAD | `814cf69e01167669c9efae20c23d61daed61f979` |
| Source Fingerprint | `992b88cd8dc138198fc49ebfe0cecca0b2f6a0387ef5a1d1c0e90f0d98297f1c` |
| Dataset Fingerprint | `3c40675787f2de08ce1690dc2fcadfcb7bdb770aac9951fd44869a55477f6739` |
| Dataset 文件 SHA | `514e1bc0a9b31802fe45600b1d84a9bb5ee95ca37c72f3655a118c840484ff8c` |
| Corpus Fingerprint | `9c8144131a4d9a93be3621d80cd14691ee858b086f9a8650497dde5459ab049e` |
| Catalog Index ID | `6832df8a828ce611f321023be9e92ba78c377e14609ef36d9a789c7118ed9954` |
| 当前 Build Fingerprint | `ecd83a43735338e2f909223457682bffa7326b6abd589304b95190262b4a9f03` |
| Model Catalog Hash | `11164a28bef4fd7b19c61e6764807fea9f18bb55d7a2fc6c0afed28351657469` |
| 本轮配置捕获 Hash | `c2d4c4a77d91cf4f8259a4b05ed950a082858e66086449ef58558f2aa327ee71` |

捕获的 `profile_id=s4e-frozen-v1` 是审计标签，不是新增 Model Profile；标签不同导致 Hash 与历史 dev 不同。排除标签后完整物理配置前后相等，不能强行复用旧 Hash。

Answer/Grader/Evaluator：`model_cca5c8be5c5b42d2b31449a8579aea38:v1` / deepseek-flash；Fast：`model_489cb92681f943bca8364bde51e8fc3f:v1` / deepseek-v4-pro。原 DeepSeek 结构化能力策略、Pydantic 校验及普通 Thinking 行为未修改。Embedding：BAAI/bge-m3，revision `5617a9f61b028005a4858fdac845db406aefb181`，CPU / 1024。

Rerank：qwen3.7-text-rerank，enabled=true，timeout=5s，candidate_limit=30，min_score=0，字符上限 8000/60000。top_k=8、candidate_k=30、leaf_level=3、Parent Merge threshold=2、子问题上限 4/并发 2、上下文字符预算 12000；不是实测 Token。完整参数保存在 `profile.json`、`runtime-profile-after.json`。

前后正式 PID 383/384/385/386 未变，Rerank 环境一致，无观察包装器。最终 Ready=200、12/12 READY；Manifest / 1916 Vector / 2497 Parent 逐版本 exact，700 个 Excel 叶子来源与 S4-B 一致。未上传、重建、迁移或改变 Version；8 HTML 保留旧 Build，4 XLSX 保留 S2 Build，逐版本清单在 `index-identities.json`。

702 条导出检索/证据身份与当前 Document ID、Version、Chunk Manifest 正文哈希及格式标签核验，错配 0。`index_version=catalog-v1` 是格式标签，不是 Catalog Index ID。原 570 文件变化 0，最终活动 Run/Index/Evaluation Job 均为 0。

## 3. 检索与原生 Case 结果

Document Recall 是有 Gold Case 命中文档比例的宏平均；有效样本 53，含超时的 0。7 个无答案 Case 无 Gold。@5/@10 按原生最终 Chunk 排名截断匹配文档，不是独立去重文档 Top-K。

| 类型 | 总数 | 原生 Pass | Doc Recall@5 | Doc Recall@10 | Gold 样本 | 全必要文档@5 / @10 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 简单事实 | 15 | 14/15，93.33% | 93.33% | 93.33% | 15 | 14/15 / 14/15 |
| 表格 | 15 | 14/15，93.33% | 93.33% | 93.33% | 15 | 14/15 / 14/15 |
| 跨文档 | 15 | 12/15，80% | 60% | 93.33% | 15 | 3/15 / 13/15 |
| 无答案 | 7 | 0/7 | 未测 | 未测 | 0 | 未测 |
| 版本/政策 | 8 | 0/8 | 100% | 100% | 8 | 8/8 / 8/8 |
| 合计 | 60 | **40/60，66.67%** | **84.91%** | **94.34%** | **53** | **39/53，73.58% / 49/53，92.45%** |

真实 Gold Chunk 为空，Chunk Recall / MRR / nDCG 未测，不把文档名/行锚点伪装为 Gold Chunk。全必要文档覆盖是 Doc Recall=1 的辅助统计，不保证全部必要事实已命中。

## 4. Judge、Outcome 与 Gate

| 类型 | Judge correctness | groundedness | completeness | Judge n |
| --- | ---: | ---: | ---: | ---: |
| 简单事实 | 1.0000 | 1.0000 | 1.0000 | 14 |
| 表格 | 0.9333 | 0.9333 | 0.9333 | 15 |
| 跨文档 | 0.9333 | 0.9867 | 0.9333 | 15 |
| 无答案 | 0.9571 | 0.9571 | 0.9357 | 7 |
| 版本/政策 | 1.0000 | 1.0000 | 0.9875 | 8 |
| 合计 | **0.9610** | **0.9746** | **0.9568** | **59** |

context_relevance=0.7231（n=52）。连续 Judge 分数不是 60 题二元回答准确率；缺 Judge 的超时 Case 仍留在 60 题 Pass 分母。Native Pass 同时检查 Expected Outcome、HITL、Judge 阈值和 Provider 状态。

Outcome：ANSWERABLE=41、INSUFFICIENT_EVIDENCE=19、NO_KNOWLEDGE=0。Route：answer=52、clarify=7、provider_failed=1。版本类 8 条均 route=answer、Outcome=INSUFFICIENT_EVIDENCE；人工解释不改自动结果。

Gate：live_rag provenance passed；critical_no_regression passed，但 critical Cases=0 且无同集 baseline，不构成关键样本安全性证明；case_pass_rate **failed**，actual=0.666666666667，minimum=0.95。Job succeeded 不等于 Quality Gate 通过。

## 5. 引用与 Excel 来源

复用 `scripts/audit_rag_citations.py` 的 `audit_case` / `source_rows`，仅对原生导出离线审计；不修改其 CLI 的 20-dev guard，不新增 Judge。Gold 行来自原 ground_truth，经真实叶子及 Version 映射核验。

| 指标 | 结果及分母 |
| --- | --- |
| Citation Validity | 120/120=100%，非法 0；仅 Evidence ID/来源合法 |
| Excel Provenance Coverage | 139/139=100%，最终 retrieval_context XLSX 记录来源完整可核验 |
| Strict Row-level Citation Accuracy | 30/33=90.91%，有行 Gold Case 的实际行集合须恰好相等 |
| 行级 Precision（micro） | 39/(39+0)=100% |
| 行级 Recall（micro） | 39/(39+4)=90.70% |
| 过宽 / 缺失 / 不确定 Case | 0 / 3 / 0，n=33 |

表格严格行通过 14/15、合法引用 37 次；跨文档 13/15、36 次；版本类有行 Gold 的 3/3、合法引用 31 次。简单事实/无答案引用 15/1 次，但无行 Gold，严格行未测，不自动算通过。

缺失：table_query_016 的参数第 17/37 行、cross_document_010 的第 91 行、cross_document_014 的第 95 行，共 4 个 Case-行单元。没有发现已导出 Excel 记录的 Parent 来源丢失；不能推断未命中行也被检索。非 Excel 完整 Gold Chunk、逐 Claim entailment 和语义 citation recall 未测；身份合法不能替代事实 Citation Accuracy。

## 6. 性能、异常和遥测缺口

Case duration 含检索、答案和 Judge；n=60，包含失败：mean=7819.02ms、P50=7201ms、P95=11947ms，使用原生分位数算法，非 SSE 首 Token 延迟。

Provider Failure=1/60（1.67%）：`simple_fact_012`，PROVIDER_TIMEOUT，stage=retrieval，10918ms，无答案/Judge/检索身份。Generation/Judge Provider Failure 均 0/60。持久导出只定位到宽泛 retrieval stage，不能认定 Snapshot、Embedding 或 Milvus 哪一处超时；历史 Snapshot Timeout **仍需独立诊断**。

最终候选顺序和 `rerank_score` 已保存；但原生 `RagEvalObservation`/Case 不持久化完整 `rag_trace`。冻结 Job 的 Rerank 成功/回退/错误次数、完整前后排名差、Stage 延迟、实际外部请求数、Token/费用均 **未测**。不将预检 1 次成功称为 60 题全程成功，也不将未记录 HTTP 400 声称为发生次数为零。这是未满足的遥测验收项。

预检实测 Stage=486ms、attempts=1、applied=true、fallback=false；Fast/Grader/Evaluator 各成功一次，未发送冻结题。审批预算含预检 304–544 个逻辑请求、建议额度 1100、静态极端上界 2768 是估计，不是实测账单。无可信单价/账单，人民币费用未测。

## 7. 命令、产物与回归

预检及唯一创建命令见准备报告第 11 节。完成后从仓库根实际执行（退出 0）：

```text
wsl -d Ubuntu-24.04 --cd / /home/lenovo/.local/share/supermew/venv/bin/python /mnt/d/develop/项目/企业级rag平台/SuperMew/.artifacts/synthetic-enterprise/s4e/inspect_environment.py environment-after-frozen-job.json
wsl -d Ubuntu-24.04 --cd / /home/lenovo/.local/share/supermew/venv/bin/python /mnt/d/develop/项目/企业级rag平台/SuperMew/.artifacts/synthetic-enterprise/s4e/analyze_export.py
```

分析可重复离线执行，不调用模型；创建脚本有一次性 guard，不应重跑。后处理最初误比格式标签与 Catalog Index ID，修正为真实 Manifest 身份后 702 条错配 0；只修正忽略目录辅助审计，未改原生结果。

`.artifacts/synthetic-enterprise/s4e/` 保存 persistent-dataset/job/cases/report.json、execution-receipt.json、observations.json、native-report.md、citation-audit.json、case-review.json、summary.json、retrieval-identity-audit.json、final-integrity.json、runtime-profile-after.json，以及前后环境、Manifest、原 SHA 清单。Observation/Report 通过原生 Pydantic Schema，60 个 ID 精确一致，非构造模型输出。

预检回归保留：后端 **670 passed / 4 failed / 62 subtests**；前端 **230 passed / 27 files**，Typecheck/Lint/Build 成功；Ruff check 与 Schema 检查通过，format check 有两个既有文件差异。4 项失败是历史 fingerprint 两项、组合测试环境污染一项、start.sh CRLF 一项，详见准备报告；未绕过、重写 baseline 或声称全绿。授权后无业务修改，也未为了报告重复整套测试。

## 8. 验收边界

已获得独立、真实、一次性的冻结原生基线，异常/自动失败保留，执行身份稳定。**自动 Gate 未通过，重排全链路遥测未完整满足**。没有原版同集基线，不宣称 A/B 提升。

这些证据足以讨论 S5 工程化收尾，但不表示生产质量达标；详见质量复盘的限制及建议。本次停止于 S4-E，未 Commit/Push/Merge，未进入 S5。
