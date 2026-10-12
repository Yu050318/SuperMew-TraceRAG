# S2：真实开发集 A/B 结果

日期：2026-10-12。结论：表格表示和来源链路已实现并真实验证；20 条 CLI 与 20 条正式 Evaluation Job 均执行完成。检索轮表格召回改善，但完整问答仍有版本澄清、政策证据不足和拒答分类问题；原有质量 Gate 未通过。没有运行冻结 60 题，没有自动 Commit/Push/Merge，没有进入 S3。

## 实验定义与约束

A 是 2026-10-11 S1.5 已保存、真实执行的原版结果；B 是 2026-10-12 新 Parser/Candidate 发布后的结果。用户明确授权使用历史 A，不在已切换的 B Catalog 下假装重测 A。原 12 份 upload_corpus 文件 SHA-256、开发集、Embedding Revision、模型 Profile version、模型兼容策略、K 和检索参数保持一致。

这不是同 Source/Index 身份的 CI baseline regression，也不是同时随机分组的严格因果实验：模型别名不代表供应商不可变权重版本，时段、缓存、模型随机性和 Provider 延迟可能不同。不得把全部变化归因于 Parser。

使用原生 `LiveRagEvalAdapter`、`scripts/evaluate_rag.py`、Dataset/Observation/Report 和持久 Evaluation Worker。忽略目录的 `observe_native_cli.py` 只在原 `_retrieve_for_state` 返回后记录有界身份/来源，不改结果或排序，再调用原 CLI；不是第二套 RAG/评测框架。

B 先执行 `table_query_001`、`cross_document_001`、`no_answer_001` 三题 Smoke，再执行 20 题 CLI，再经正式 API 创建持久 Job。Job `rag_eval_dd10090551fc41ea990cfe3aaf4dda0c`：succeeded、20/20；**任务执行成功不等于 Gate 通过**。B CLI 和 Worker 的 `gate_passed` 均为 false，未修改门禁。

## 环境、索引与身份

使用项目 WSL 锁定依赖 Python，不使用冲突的全局 Python。启动时本地 PostgreSQL 容器因前次停止不可达，恢复同一 `local-postgres` 容器后原生 launcher 联合启动 API/Indexing/Evaluation Worker；没有重建库或清理业务数据。Redis、Milvus、数据库当前 Schema、Embedding warmup 和 Worker heartbeat 检查通过。仅按用户授权重设测试 owner=3 的随机密码，未落盘 credential。

12 个当前 Document Version READY，Catalog 仅含原测试集合。四份 XLSX 经正式上传新 Candidate/Worker/Manifest/CAS 发布，八份 HTML 不变；原 READY 数据未原地写入。700 个新 XLSX 叶子的 hash/来源与原文件重解析精确一致。完整身份见 `.artifacts/synthetic-enterprise/s2/index-identities.json`，具体新 Version 见 [索引报告](s2-index-provenance.md)。

| 身份 | A | B（实际评测） |
| --- | --- | --- |
| Catalog Index ID | `82d7c9b3841c28444b43d3d3d6914f53af5e0bf0e816584889f9123612d95bc8` | `6832df8a828ce611f321023be9e92ba78c377e14609ef36d9a789c7118ed9954` |
| Source fingerprint（CLI） | `dde1d8d6dc25330e55aba49bb18e3b5703b5608b9c473bbff3b977117d3553a9` | `bd50192ec47f0f7490fecfcfe55aa644bb453b688904ce8e8cedbb34fc223236` |
| Source fingerprint（Worker） | `dde1d8d6dc25330e55aba49bb18e3b5703b5608b9c473bbff3b977117d3553a9` | `aba625266d5b64342d166fa576f6b43974fc7b78744d63c921aed0d04b32186d` |
| XLSX Build fingerprint | `4bdbfaaf135b67b929a6cb5eeb3aa1d1835886a567709aa33971914f90a9afec` | `ecd83a43735338e2f909223457682bffa7326b6abd589304b95190262b4a9f03` |

共用 Dataset fingerprint：`7a2fde984e24ca3f7d2fe1a96bbaa82a20a6c92cbd4979e0ade3effb038155c2`；Corpus：`9c8144131a4d9a93be3621d80cd14691ee858b086f9a8650497dde5459ab049e`；Worker 模型 Catalog：`11164a28bef4fd7b19c61e6764807fea9f18bb55d7a2fc6c0afed28351657469`。

Embedding 为 BAAI/bge-m3，revision `5617a9f61b028005a4858fdac845db406aefb181`，CPU、1024 维。Answer/Grader/Evaluator=deepseek-flash，Fast=deepseek-v4-pro，Profile version=1，timeout=30s；DeepSeek 适配代码 SHA 与 A 一致。top_k=8、candidate_k=30、max_subqueries=4、并发=2、context budget=12000 tokens、grader budget=4800/每文档1200字符；算法/阈值未调参。

`experiment-profile.json` 是上传前配置快照，其 index_id/embedding_scope 仍为 A、source hash 是当时 preflight；**实际 B 身份以 live Report 和 index-identities 为准**。B 两轮间边界测试/校验收尾使磁盘 Source fingerprint 不同，不能宣称两轮使用完全同一源码快照；四份文档解析结果和同一 B Catalog 身份未变。`experiment-source/` 及 SHA manifest 保存的是 Worker 轮结束时的源文件，不是 CLI 轮的独立源码归档；Fingerprint 是原生磁盘摘要，不是长驻进程已加载模块字节的证明。评测后做等价整数类型收窄及异常 XLSX 尺寸拒绝的加固；最终交付 hash、重启后 readiness、700 个叶子的再次精确比对在 `final-delivery-provenance.json`。没有重写实验 Report 的 Source identity，也没有为这项非语料语义变动重跑模型。

最终交付 Source fingerprint：`83ffebdbe9b565104d904c565844e2a0adad76c963ebbcdafc4a39a689d5ebbf`。原生 launcher 已优雅停止旧进程并重新联合启动；最终 `/health/ready` 返回ready，1个fresh Indexing Worker、0个incompatible Worker，Build fingerprint仍为上述B值，Catalog仍为B。队列16个completed是原12次构建加本轮4次；4个cleanup_pending是旧Excel Version的原生保留期任务，不是索引失败。

## 原生指标：必须分开两轮

Document Recall 的有效样本为 17（无答案 3 题无 Gold Doc）；Case/Judge/延迟 n=20。原 Contract 的 @5 是前五个 RetrievedChunk 的文档覆盖，不是先按文档去重的前五文档。

| 指标 | A CLI | B CLI | A Worker | B Worker |
| --- | ---: | ---: | ---: | ---: |
| Document Recall@5 | 55.88% | 70.59% | 55.88% | 58.82% |
| Document Recall@10 | 61.76% | 82.35% | 58.82% | 70.59% |
| Case Pass Rate | 40% | 60% | 40% | 50% |
| P50，ms（n=20） | 10534.86 | 2499.91 | 11133 | 4673 |
| P95，ms（n=20） | 20867.34 | 4898.24 | 17574 | 20637 |
| 原生主流程 Provider Failure Rate | 0% | 0% | 0% | 0% |
| Judge answer_correctness 均值 | 未测 | 未测 | 0.65 | 0.84 |
| Judge groundedness 均值 | 未测 | 未测 | 0.775 | 0.825 |
| Judge answer_relevance 均值 | 未测 | 未测 | 0.7925 | 0.87 |
| Judge completeness 均值 | 未测 | 未测 | 0.6275 | 0.82 |
| Judge unsupported_claim_rate | 未测 | 未测 | 0.18 | 0.1425 |
| Judge conflict_disclosure 均值 | 未测 | 未测 | 0.825 | 0.845 |

context_relevance：A=0.74545（n=11）、B=0.77083（n=12）。Judge 连续均值 0.84 **不是 84% 的二元 Answer Accuracy**；Case Pass Rate 也不是回答准确率。unsupported_claim_rate 是原 Judge 对传入上下文的评估，不等于逐事实人工核验的语料级幻觉率。

Chunk Recall、Chunk MRR/nDCG、Citation Accuracy、二元 Answer Accuracy 均未测：原 Gold 没有完整 Chunk 标注，合并父块与真实行级 Gold 的匹配语义尚未定义。新增真实叶子映射仅作为辅助来源，未把文件名/锚点冒充 Gold Chunk ID。

### 分类结果

| Worker 分类 | n | A→B Recall@5 | A→B Case Pass | A→B Judge correctness |
| --- | ---: | --- | --- | --- |
| simple_fact | 5 | 1→1 | 1→1 | 1→1 |
| table_query | 5 | 0.6→0.6 | 0.6→0.6 | 0.6→0.8 |
| cross_document | 5 | 0.2→0.2 | 0→0.4 | 0.24→0.7 |
| no_answer | 3 | 未测 | 0→0 | 0.83333→0.76667 |
| version_policy | 2 | 0.25→0.5 | 0→0 | 0.65→1 |

CLI 表格平均 Recall@5=0.6→1、5 题全部通过；跨文档平均=0.1→0.2，但“全部必要 Gold Doc 都在前五”的 Case 比例仍是 0/5→0/5。不能以平均部分召回声称跨文档证据齐全。完整问答轮表格仍两题澄清，不能挑选 CLI 最好结果代替 Worker。

### 延迟、规模与 Rerank 限制

全库叶子 1271→1916（+50.75%），父块 2468→2497（+1.18%）；Excel 叶子 55→700（12.73 倍），Excel 父块 36→65；HTML 叶子1216/父块2432不变。Embedding 数量相应增长，候选池30和上下文预算不变，可能增加同文档竞争/父块扩张；本轮没有逐次 token 消耗测量，不能推算全部成本。

CLI P95 下降但 Worker P95 **上升17.43%**，需要保留长尾结论。B Smoke+CLI 实际记录的31次检索均出现远端 Rerank `PROVIDER_REQUEST_INVALID`、attempt=1并触发原生回退；没有改Rerank算法或吞异常。主流程失败率0不代表Rerank健康。A之前探测有超时，但完整轮未导出同口径回退次数；因此两期延迟/排序比较存在Provider混杂，尚无健康Rerank下的质量结论。

## 逐 Case 对照（CLI，n=20）

缩写：M=product_manual、T=technical_specs、W=warranty_rules、F=product_faq、G=selection_guide、H=troubleshooting、R=release_notes（均HTML）；S=product_specs、P=product_prices、I=inventory（均XLSX）。列出实际最终Observation文档，空集不等于初始阶段没召回；所有初始/最终身份、Chunk和来源详见 `ab-comparison.json`。

表头列：`名/未绑定`=旧命中块含全部原列名，但没有逐行业务字段绑定；`—`=最终无XLSX，不能推断最初解析结果；B的`绑定`表示新Excel正文行级标签和值，`来源✓`表示实际最终Excel hit保留Sheet/Row。原版最终均无可信Sheet/Row。

| Case | A docs → B docs | A表头→B表头/来源 | Recall@5 A→B | 延迟ms A→B | B通过/仍失败环节 |
| --- | --- | --- | --- | --- | --- |
| simple_fact_001 | M,T,W → M,T,W | —→— | 1→1 | 9243→3144 | 通过 |
| simple_fact_002 | F,T,G,W → F,T,G,W | —→— | 1→1 | 6721→1777 | 通过 |
| simple_fact_003 | T,M,G,W → T,M,G,W | —→— | 1→1 | 6688→1565 | 通过 |
| simple_fact_004 | H → H | —→— | 1→1 | 7373→1795 | 通过 |
| simple_fact_005 | M,T,W,G,F → M,T,W,G,F | —→— | 1→1 | 6813→1726 | 通过 |
| table_query_001 | ∅ → R,G,T,S,F | —→绑定/✓ | 0→1 | 18174→1816 | 通过；Worker仍版本澄清 |
| table_query_002 | P,R,T,G,W,I,F,S → P,R,T,G,S,F | 名/未绑定→绑定/✓ | 1→1 | 10372→2681 | 通过 |
| table_query_003 | T,I,R,W,G,H,P,S → I,T | 名/未绑定→绑定/✓ | 1→1 | 6599→1647 | 通过 |
| table_query_004 | ∅ → R,G,T,S | —→绑定/✓ | 0→1 | 8348→2052 | 通过；Worker仍版本澄清 |
| table_query_005 | R,T,P,G,W,F,S,I → P,R,T,S,F | 名/未绑定→绑定/✓ | 1→1 | 6496→1750 | 通过 |
| cross_document_001 | ∅ → ∅ | —→— | 0→0 | 10535→4600 | 政策证据不足/澄清 |
| cross_document_002 | M,T,W,G,F → G,S,W,T,M,F | —→绑定/✓ | 0.5→0.5 | 27879→3668 | 通过，Top5证据不全 |
| cross_document_003 | ∅ → ∅ | —→— | 0→0 | 14779→4568 | 政策证据不足/澄清 |
| cross_document_004 | ∅ → G,S,T,W,M | —→绑定/✓ | 0→0.5 | 15395→3762 | 通过，Top5证据不全 |
| cross_document_005 | ∅ → ∅ | —→— | 0→0 | 15666→4668 | 政策证据不足/澄清 |
| no_answer_001 | ∅ → ∅ | —→— | 未测 | 11908→2500 | 拒答/澄清分类不符 |
| no_answer_002 | ∅ → ∅ | —→— | 未测 | 12251→1926 | 拒答/澄清分类不符 |
| no_answer_003 | ∅ → ∅ | —→— | 未测 | 11823→2649 | 拒答/澄清分类不符 |
| version_policy_001 | R,S,G,T → R,T,G,S | 名/未绑定→绑定/✓ | 0.5→0.5 | 20408→6887 | INSUFFICIENT_EVIDENCE分类 |
| version_policy_002 | R,G,S,T → R,G,T,S,W | 名/未绑定→绑定/✓ | 0.5→0.5 | 20867→4898 | INSUFFICIENT_EVIDENCE分类 |

## 八个重点 Case：观测与定位

1. `table_query_001`：期望NX-001当前功率120W。B初始参数父块rank4保留真实第2行；CLI20答对，Worker列明v1=130W/v2=120W及日期，却仍问用户版本，Judge=0.5。表示/召回部分已修复，`grader`与现有澄清路由仍影响最终行为；不是来源写入失败。
2. `table_query_004`：NX-004当前60W。CLI答对，Worker区分旧70W/新60W但再次澄清，Judge=0.5。与001同类；未为改进Pass修改无答案或版本策略。
3. `cross_document_001`：NX-081、2026-02-01购买，期望155W/24月保修。Worker已确认功率155W，但表示缺少保修证据并澄清；最终文档投影空。参数行改进未解决政策文档召回，不能认定EvidencePack截断是根因。003/005同类。
4. `cross_document_002`：NX-082通信/安装。Worker回答Modbus RTU与DIN导轨并给不同引用，Judge=1，ANSWERABLE/通过；CLI只覆盖一半Top5 Gold，另一必要文档在更后位置。多文档问答改善不是Top5全覆盖。
5. `cross_document_004`：NX-084通信/安装。Worker回答MQTT与DIN导轨，Judge=1/通过；CLI从无最终证据到参数+手册，部分召回改善。实际来源记录能定位参数叶子，正式UI尚不显示行号。
6. `no_answer_001`：不存在NX-901。Worker说“我找到了相关内容，但还缺少…”并要求对应型号/章节，Judge=0.7，INSUFFICIENT_EVIDENCE/clarify，而非Gold预期拒答。不能据此断言编造了NX-901数值；未知产品003还建议NX-003/NX-001，属于不必要替代产品建议风险。
7. `version_policy_001`：NX-001 v2。Worker正确120W，并解释v1=130W和生效日期，Judge=1，但最终标记INSUFFICIENT_EVIDENCE而Case失败。定位复杂问题计划/子结果聚合与outcome映射；不是简单的事实答错。
8. `version_policy_002`：NX-002 v2。Worker正确90W、旧100W及日期，Judge=1，同样partial/outcome未通过。应在后续明确版本问题充分证据的判定，S2不改工作流。

相关未改源码环节：`backend/rag/pipeline.py` 检索/复杂计划调用链、既有 Grader 与HITL分支、`backend/rag/evidence.py:pack_evidence`、`backend/evaluation/rag_adapters.py:_outcome/_chunks_from_trace`。已观测的是答案、路由和最终投影；没有逐字段裁剪审计，EvidencePack预算截断仅为待验证风险。Rerank错误是独立Provider问题，不混同ExcelParser。

## 测试与命令

以下均在仓库根目录、锁定WSL环境执行；本机解释器是 `/home/lenovo/.local/share/supermew/venv/bin/python`。不要采用全局Python，也不要重复执行带上传/密码重设的实验driver当作只读检查。

```bash
python -m pytest tests/test_excel_parser.py tests/test_excel_provenance.py tests/test_milvus_writer.py tests/test_milvus_retrieval_shapes.py tests/test_milvus_filters.py tests/test_document_publication.py tests/test_document_catalog.py tests/test_indexing_worker.py tests/test_parent_chunk_store_versions.py tests/test_document_retrieval_scope.py tests/test_rag_parent_scope.py tests/test_document_version_artifacts.py tests/test_document_catalog_migration.py tests/test_indexing_worker_migration.py -q --junitxml=.artifacts/synthetic-enterprise/s2-index-final.xml
python -m pytest tests/test_rag_short_circuit.py tests/test_rag_fault_injection.py tests/test_native_checkpoint_hitl.py tests/test_provider_loop_bridge.py tests/test_provider_retry_policy.py tests/test_rerank_stage.py tests/test_rag_retrieval_targets.py tests/test_rag_trace_schema.py tests/test_rag_evidence.py tests/test_rag_eval_adapters.py tests/test_rag_eval_cli.py tests/test_deepseek_structured_output.py tests/test_rag_evaluation_judge_runtime.py tests/test_rag_evaluation_jobs.py tests/test_synthetic_enterprise.py -q --junitxml=.artifacts/synthetic-enterprise/s2-rag-regression.xml
RUN_S2_MILVUS=1 python -m pytest tests/test_excel_milvus_integration.py -q --junitxml=.artifacts/synthetic-enterprise/s2-milvus.xml
python scripts/evaluate_rag.py validate --dataset evals/rag/synthetic_enterprise/dataset_dev_v1.json
python scripts/generate_rag_eval_schemas.py --check
python -m mypy backend/indexing/excel_parser.py backend/indexing/excel_provenance.py --follow-imports=skip --cache-dir /tmp/supermew-s2-mypy
git diff --check
```

| 范围 | 实际结果 |
| --- | --- |
| 最终索引/发布/来源14文件 | 154 passed，19 subtests；39条既有依赖/SQLite warnings |
| RAG/Evaluation/S1/DeepSeek15文件 | 190 passed，2 failed，11 subtests；1 warning |
| 真实Milvus | 1 passed（非默认skip） |
| 不重复计数汇总 | 345 passed，2项历史失败；新增41项测试 |
| 评测后最终聚焦复核 | 61 passed；属于上述重复子集，不累加 |
| Dataset validation / Evaluation Schema | 通过 |
| Ruff changed-file check/format check | 通过 |
| 两个新模块mypy | 通过；不是全仓库类型检查 |

345为pytest主用例通过数，不重复累加30个subtests或聚焦重跑；JUnit包含subtests，所以XML tests总数会更大。

两项历史失败是 `test_cli_scores_offline_baseline_and_writes_sanitized_reports`、`test_cli_returns_one_for_a_quality_regression` 的旧baseline source/corpus fingerprint不匹配；不改fingerprint、不关闭检查、不覆盖baseline。首次mypy暴露整数generator guard不能收窄类型，改为等价显式guard后通过；不是吞异常。未运行全仓库coverage、前端门禁或新增live并发崩溃测试，不宣称这些通过。

新增/修改测试：`test_excel_parser.py`（新增30项）、`test_excel_provenance.py`（新增7项）、`test_excel_milvus_integration.py`（新增1项）、`test_document_publication.py`（新增3项）；`test_milvus_writer.py`仅修正fake package路径以导入正式新模块。生产改动完整清单见Parser设计。

实际CLI运行经只读观测wrapper使用原生参数：

```bash
python .artifacts/synthetic-enterprise/s2/observe_native_cli.py run --dataset evals/rag/synthetic_enterprise/dataset_dev_v1.json --corpus-path evals/rag/synthetic_enterprise/upload_corpus --gates evals/rag/live_gates_v1.json --observations .artifacts/synthetic-enterprise/s2/live-dev-observations.json --report .artifacts/synthetic-enterprise/s2/live-dev-report.json --markdown .artifacts/synthetic-enterprise/s2/live-dev-report.md --profile-id nebula-s2-excel-dev-v1 --index-id 6832df8a828ce611f321023be9e92ba78c377e14609ef36d9a789c7118ed9954 --timeout-seconds 60
```

这会调用模型，重复运行前重新确认预算，并采用新输出目录避免覆盖本次证据。Worker经 `/v1/rag-evaluations/datasets`、`/v1/rag-evaluations/jobs` 的正式认证API创建；观察产物存于persistent系列文件，不用简化脚本替代Worker。

## 运行产物与进入S3的条件

忽略目录 `.artifacts/synthetic-enterprise/s2/`：`snapshot-before.json`、`upload-receipts.json`、`index-jobs.json`、`index-identities.json`、`provenance-audit.json`、`leaf-source-identities.json`、`retrieval-sources.jsonl`、`live-smoke-*`、`live-dev-*`、`persistent-job/cases/report.json`、`experiment-profile.json`、`experiment-source-snapshot.json`、`ab-comparison.json`、`final-delivery-provenance.json`。JUnit在父目录`s2-*.xml`；服务日志为`s2-services.log`。这些不是入库语料，也不提交Token、私有reasoning或真实用户资料。

具备进入S3内部来源契约设计/实现的条件：真实叶子来源、父块命中集合和版本发布链路已经可用，边界见[来源报告](s2-index-provenance.md#s3-可消费接口与尚未覆盖)。但尚不具备声称生产问答质量达标的条件。后续需要：正式安全投影/引用与Gold映射语义、Checkpoint恢复来源、政策文档召回调查、版本充分性判定、正确拒答分类、独立修复Rerank兼容、健康Provider下额外评估长尾延迟。必须另行授权进入S3；本次到此停止。
