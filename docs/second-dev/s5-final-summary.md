# S5：最终交付总结

日期：2026-10-13。交付范围为 README 与两份新文档；不修改业务代码、历史报告、Gold/Gate/Schema/部署配置，不启动服务或模型评测。项目名称 **SuperMew-TraceRAG**，基于 icey1287/SuperMew 增量开发。

## 阶段与证据索引

| 阶段 | 已完成工作                                                          | 证据与边界                                                                                                                                               |
| ---- | ------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------- |
| S0   | 源码审计、真实类/函数映射、继承与新增边界                           | [repo-analysis](repo-analysis.md)，不是已实现所有规划功能                                                                                                |
| S1   | 固定种子事实源、200产品/100维修、12逻辑文档、80原生Case、SHA与划分  | [数据设计](s1-data-design.md)、[离线基线](s1-evaluation-baseline.md)；4XLSX+8Markdown源、4XLSX+8HTML正式入库投影；离线不是RAG效果                        |
| S1.5 | 锁定环境、DeepSeek结构化Adapter、12文档READY、原CLI与Worker开发基线 | [Live基线](s1.5-live-baseline.md)；是兼容适配后的原检索基线，非完全未修改平台                                                                            |
| S2   | XLSX行语义、多Sheet三级分块、Milvus动态来源、版本发布核验           | [Parser](s2-excel-parser-design.md)、[索引](s2-index-provenance.md)、[开发对照](s2-ab-evaluation.md)；真实700叶子，Gate未通过，历史A不重跑               |
| S3   | 正式来源Contract、Evidence选择/引用编号审计、冻结恢复、Vue精准卡片  | [Contract](s3-provenance-contract.md)、[Checkpoint](s3-evidence-checkpoint.md)、[前端Smoke](s3-frontend-citations.md)、[评估](s3-citation-evaluation.md) |
| S4-A | 有界真实叶子正文载体、父级上下文与精准引用分离                      | [设计](s4a-evidence-attribution-design.md)、[对照](s4a-evaluation.md)；20-dev严格行1/12→9/12，非冻结A/B                                                  |
| S4-B | 独立事实规划、缺证查询、一次补充召回及L3去重修复                    | [实现](s4b-coverage-implementation.md)、[诊断](s4b-cross-document-diagnosis.md)、[评估](s4b-evaluation.md)；中断轮独立保留，最终20/20，不拼最好结果      |
| S4-D | Rerank协议兼容与健康端到端Smoke、一次20-dev正式Job                  | [Smoke](s4d-rerank-end-to-end-smoke.md)、[基线](s4d-healthy-rerank-baseline.md)；31阶段成功/0回退只属于该轮                                              |
| S4-E | 冻结预检、授权环境恢复、唯一一次60题Job、原生报告与只读复盘         | [准备](s4e-freeze-readiness.md)、[最终](s4e-final-evaluation.md)、[质量分析](s4e-quality-analysis.md)；Gate FAIL，未修复/重跑冻结失败                    |
| S5   | 面向开源与面试的README、真实架构图、贡献地图、Demo和简历草稿        | 本文与[项目展示](s5-project-showcase.md)；仅文档交付，不是生产工程加固                                                                                   |

S4-C 没有独立正式交付报告，不虚构额外阶段。历史总计划部分目标与实际执行不同：没有原版60-frozen对照、没有所有发布门禁全绿、没有所有截图公开。本轮以最新用户“docs-only”范围与真实结果为准，不机械补实现或宣称原计划DoD全满足。

## 完整技术改动清单

依据本地 `git diff e2ebabe..814cf69 --stat/name-only` 与实际符号核验：历史二开涉及117文件（含大批确定性资产/Schema），26931新增行、95删除行。数字描述差异规模，**不用于把所有上游系统计为个人成果**。现有两个二开提交为769b1a2、814cf69，S5未创建新提交。

### 新增业务/辅助模块

| 文件                                                                               | 核心函数                                                                             | 新增职责                                    |
| ---------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------ | ------------------------------------------- |
| [excel_parser.py](../../backend/indexing/excel_parser.py)                          | `parse_excel_rows / _display`                                                        | 行绑定、资源限制、可见Sheet、拒绝复杂结构   |
| [excel_provenance.py](../../backend/indexing/excel_provenance.py)                  | `source_anchor / excel_provenance / matched_leaf_sources`                            | 来源合法性及有界真实命中集合                |
| [generate_synthetic_enterprise.py](../../scripts/generate_synthetic_enterprise.py) | `make_records / make_facts / make_cases / build_assets / validate_assets / generate` | 唯一事实源、文档Gold同源、内容保护          |
| [audit_rag_citations.py](../../scripts/audit_rag_citations.py)                     | `audit_case / source_rows`                                                           | 原生结果离线引用/行集合审计，非第二套执行器 |
| [ragSources.ts](../../frontend/src/utils/ragSources.ts)                            | 来源选择、归一化与展示helpers                                                        | 只用入选Evidence，兼容旧来源，不伪造行      |

### 后端实质修改：全部生产文件范围

| 文件组                                                  | 修改边界                                                                                                                            |
| ------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------- |
| `backend/agent/models.py`、`backend/core/settings.py`   | `DeepSeekStructuredChatOpenAI`、`ModelRegistry.get` 和显式结构化策略配置；复用现有ChatOpenAI，不猜模型字符串能力                    |
| `backend/agent/runtime.py`                              | `_finish` 最终正文/引用审计和Trace一致                                                                                              |
| `backend/documents/publication.py`                      | `DocumentPublicationConfig.from_runtime / DocumentPublication._run_once` 注入新Parser/Chunker，发布前来源核验                       |
| `backend/documents/retrieval.py`                        | `RetrievalSnapshot.to_payload/from_payload / assert_snapshot_available` 有界冻结恢复与可用性检查                                    |
| `backend/indexing/document_loader.py`                   | `DocumentLoader._load_excel / load_document` 专用XLSX路径，其他格式原实现                                                           |
| `backend/indexing/milvus_writer.py`、`milvus_client.py` | 动态写入/查询投影、`verify_provenance`，不迁移固定Schema                                                                            |
| `backend/providers/rerank.py`、`runtime.py`             | 原Httpx Adapter的DashScope input/output协议、重试/错误边界兼容；原RerankStage算法沿用                                               |
| `backend/rag/utils.py`                                  | Parent/Leaf作用域及载体，`dedupe_documents` 仅父块来源合并，重复L3不冒充Parent                                                      |
| `backend/rag/evidence.py`                               | `citation_leaves / pack_evidence / evidence_trace / audit_citations / audit_trace_citations` 来源文本、叶子归因、入选和最终编号审计 |
| `backend/rag/pipeline.py`                               | Snapshot传递；`classify_complexity / EvidenceGrade / _resolve_route / rewrite_question_node` 独立事实与一次补证；无新增图拓扑       |
| `backend/rag/checkpoint_runner.py`                      | `_compact_hitl_state / _compact_resume_result` 有界来源/载体与冻结Snapshot，去无必要正文                                            |
| `backend/runs/request_context.py`、`agent_executor.py`  | `restore_rag_retrieval_snapshot / _resume_answer_prompt` Run绑定恢复和同预算Evidence/Trace                                          |
| `backend/schemas/rag.py`                                | ExcelSource、MatchedLeafSource、RetrievedChunk、RagTraceFields严格来源与入选集合                                                    |
| `backend/tools/knowledge.py`                            | `_render_rag_result` 区分候选与真实Answer EvidencePack，澄清/拒答不伪装入选                                                         |
| `backend/evaluation/rag_adapters.py`、`runtime.py`      | source fingerprint包含新模块，最终答案/来源审计对齐；保留原Dataset/评分Contract                                                     |

不修改ParentChunk ORM/ParentChunkStore Schema，既有ACL JSON不藏来源；不建立新的业务数据库、Citation Store、模型客户端或Evaluation框架。冻结阶段的窄范围Milvus环境映射不是上述Python算法修改，本轮不处理部署恢复。

### 前端、契约与配置

- 前端：`ChatArea.vue / MessageContent.vue / MessageItem.vue / References.vue / KnowledgeContextPanel.vue`、`events/runEventReducer.ts`、`stores/chat.ts`、`types/chat.ts`、`utils/markdown.ts`、新增`utils/ragSources.ts`；统一点击引用、入选来源和SSE/历史投影。
- 契约：`scripts/generate_contract_types.py` 生成 `contracts/rag_trace_v1.schema.json`；RunEvent v1 envelope未替换，旧Trace缺省/null兼容。
- 配置/运行文档：`.env.example / .gitignore / CONTEXT.md / README.md / docker-compose.yml / scripts/start-wsl.ps1 / frontend/scripts/check-bundle-size.mjs / docs/runbooks/persistent-indexing-worker.md`；是历史小范围修改，不称新部署平台。本轮不改这些脚本或质量阈值。
- 决策：新增 [ADR-0027](../adr/0027-rag-provenance-and-frozen-resume.md)，不改旧ADR核心意义。
- 数据：`evals/rag/synthetic_enterprise/` 的source_records、corpus、upload_corpus、三个Dataset、Ground Truth、splits、manual_review、manifest和README；产品/答案事实同源，不上传答案资产。
- 过程文档：本文阶段表所链接的S0～S4报告及相关优化说明；原结果文件保持历史语义。

### 测试文件范围

新增后端测试：

`test_synthetic_enterprise.py`、`test_deepseek_structured_output.py`、`test_excel_parser.py`、`test_excel_provenance.py`、`test_excel_milvus_integration.py`、`test_rag_provenance_contract.py`、`test_rag_citation_audit.py`、`test_evidence_attribution.py`、`test_rag_cross_document_coverage.py`。

扩展原测试：

`test_document_publication.py / test_milvus_writer.py / test_knowledge_tool_outcomes.py / test_rag_evidence.py / test_rag_outcomes.py / test_rag_short_circuit.py / test_reranker_adapter.py / test_settings_security.py`；前端扩展`References.spec.ts / runEventReducer.spec.ts`并新增`ragSources.spec.ts`。均位于现有tests或组件同目录，不新建并行测试框架。

## 复用边界与关键取舍

1. **动态来源而非PG迁移**：既有Milvus dynamic field足够保存叶级位置，Parent只保留实际命中集合。避免改Schema，但必须维护Writer/Projection/Parent Merge全链路校验，不能只“写入成功”就发布。
2. **版本身份而非文件名**：复用Catalog/Manifest/CAS/fencing；source_anchor是位置，不是身份。新Build创建Candidate；失败不污染current。
3. **真实叶子而非生成式归因**：保留32/16KiB载体，在Question阶段按已有首列身份精确收窄，不针对NX硬编码；合法scope/hash才投影。不能证明逐Claim蕴涵。
4. **有界上下文与恢复**：父级无编号、叶级先入选、上下文仅占剩余预算；128KiB Snapshot、256KiB恢复边界。不无限保留旧版本，旧暂停缺Snapshot拒绝恢复。
5. **补证而非重构图**：原Planner/Grader/Synthesis节点内独立事实与一次补充；缺用户条件先澄清，不强改Gate刷分。
6. **显式模型能力**：Profile ID/version选择Function Calling，结构化请求局部Thinking关闭；不影响普通调用和其他Provider原策略，Schema/API失败必须报错。
7. **原生评测而非第二套框架**：固定事实、Dataset/Observation分离、真实Version映射和fingerprint；offline只验证Contract，不拿静态Observation报效果。

## 自动化与真实联调证据

| 层次            | 已有实测                                                         | 不应扩张的结论                                        |
| --------------- | ---------------------------------------------------------------- | ----------------------------------------------------- |
| S1生成器        | 38 passed，含8 HTML投影回归                                      | 固定依赖内容确定性，不是Live质量                      |
| S2索引与RAG相关 | 345 passed、2历史失败；真实Milvus1 passed已包含                  | 不重复加总61聚焦复查/subtests；不是全仓库绿           |
| S3真实UI        | 正式Chat/SSE、点击引用、刷新同一Thread来源一致                   | 不是所有页面、清理竞态或生产并发均验收                |
| S4-A真实UI      | 库存88台、真实第4行叶子来源                                      | Rerank曾回退，不假称健康精排                          |
| S4-B            | 最终20题Job与失败中断轮各自保存；5跨文档Case通过                 | 不隐藏中断，Snapshot超时是独立问题                    |
| S4-D            | 20题正式Job，31 Rerank阶段成功、0fallback                        | 开发期阶段观察不能替代冻结遥测                        |
| S4-E回归        | 后端670 passed/4 failed，另62subtests；前端230 passed/27 files   | 非完整仓库所有测试，不把隔离复跑相加                  |
| S4-E静态        | Ruff check、两种Schema生成检查通过；前端typecheck/lint/build通过 | Ruff format两文件差异、mypy/覆盖率/全部发布门禁未完成 |
| S4-E真实索引    | 12/12 READY、1916向量、2497父块、700Excel叶子、702导出身份0错配  | 当前健康不等于容器重建恢复已演练                      |
| S4-E唯一冻结Job | 60/60、attempts1、40/60 Pass                                     | Job成功不等于Gate通过                                 |

四项后端失败：两项历史source/corpus fingerprint不匹配；ModelRegistry组合环境隔离现象（单独1 passed不抵消）；start.sh CRLF shebang。未关闭fingerprint、覆盖baseline或修复框架来美化结果。完整命令与失败名见[冻结准备](s4e-freeze-readiness.md#6-离线检查与真实结果)。

## 开发与冻结指标口径

| 指标                    | S4-D最后健康20-dev    | S4-E唯一60-frozen       |
| ----------------------- | --------------------- | ----------------------- |
| Case Pass               | 14/20=70%，Gate FAIL  | 40/60=66.67%，Gate FAIL |
| Document Recall@5 / @10 | 82.35% / 94.12%，n17  | 84.91% / 94.34%，n53    |
| Citation Validity       | 33/33                 | 120/120                 |
| Strict Row-level        | 11/12                 | 30/33=90.91%            |
| 已检索Excel来源完整     | 60/60                 | 139/139                 |
| P50 / P95               | 7.802s / 14.626s，n20 | 7.201s / 11.947s，n60   |
| Provider Failure        | 0/20                  | 1/60 retrieval Timeout  |
| Rerank阶段统计          | 31success / 0fallback | 未测                    |
| Judge correctness       | 0.95，n20连续均分     | 0.9610，n59连续均分     |

两列Dataset不同，**不是A/B，也不能计算提升百分点**。DocRecall在最终Chunk Top-K截断匹配文档、eligible Case宏平均；无Gold不入分母，超时0留在eligible分母。CasePass结合Outcome/HITL/Judge/故障，不是二元回答准确率；引用编号合法不是事实支持率；严格行匹配要求有Gold的行集合完全相等，仍非Claim entailment；latency包含Judge和失败。

冻结全必要文档@5=39/53、@10=49/53；跨文档@5仅3/15、@10=13/15。逐题主要事实正确但Outcome失败的版本/拒答例不人工改判。没有原版60-frozen结果，不能把历史dev优化当冻结因果实验。冻结题已使用，后续据此优化需新独立评测数据。

## 当前可展示与未解决风险

可展示：700个真实Excel叶子来源、表头/单位绑定、版本发布兼容、Parent/Leaf分离、SSE与历史来源、真实多文档与澄清案例、固定语料/Gold隔离和失败可追溯评估。[展示步骤](s5-project-showcase.md#5-十分钟真实-demo-路径)不要求本轮重跑题目。

不能宣称生产发布达标：

- CasePass门禁0.95未通过；无答案0/7、版本政策0/8的原生状态失败保留。
- 已复现Grader前缀预算遗漏必要行（NX-016/090/094）；没有完整runtimePrompt，仍需新fixture专门诊断，不在S5修复。
- retrieval Provider Timeout1次；历史SnapshotTimeout未独立修复证明。
- 冻结Rerank完整计数、阶段排序/耗时、请求Token账单未持久，不能报全程无HTTP400或费用。
- 缺完整真实GoldChunk/Claim支持标注，MRR/nDCG及全面Citation事实准确率未测。
- Milvus路径映射在当前容器writable layer，重建会丢失；冷启动未完整演练，S5不修改部署。
- 并发SLA、完整发布门禁、真实替换/清理HITL竞态验证不足。
- 截图尚未公开审查；本轮不复制含个人身份的资源。

后续方向（仅建议，须另行授权）：Grader目标叶子可见性边界测试；Outcome业务语义与评测契约讨论；原生Evaluation公开遥测持久化；Snapshot阶段时序；冷启动恢复与测试环境隔离；新增独立人工GoldChunk/Claim数据。不能通过改Gold、Gate或复跑这60题冒称独立提升。

## 开源、许可与隐私

本地及[上游MIT许可](https://github.com/icey1287/SuperMew/blob/main/LICENSE)已核对，保留icey1287的2026版权声明；本轮不改[LICENSE](../../LICENSE)。合成资产manifest声明CC0-1.0，生成器沿用代码MIT。未完成所有第三方依赖/模型权重的独立法律审计，不作无限许可保证。

**适合有明确限制的开源工程展示；不适合称为通过生产发布验收。** README不含个人测试账号、私有网关、Token、DSN实际凭据或本机绝对路径。历史报告包含本机复现路径与测试身份，S5禁止改旧报告，因此候选公开提交前需自行审查接受其公开范围；不要把“新README脱敏检查”理解为整个仓库已做完秘密审计。

## Git提交建议

本轮仅修改/新增：

1. `README.md`（重写）。
2. `docs/second-dev/s5-project-showcase.md`（新增）。
3. `docs/second-dev/s5-final-summary.md`（新增）。

开始时已存在、未被本轮修改的待提交正式证据：

- `docs/second-dev/s4e-freeze-readiness.md`
- `docs/second-dev/s4e-final-evaluation.md`
- `docs/second-dev/s4e-quality-analysis.md`

建议分两次人工审查提交，顺序为：

1. `docs(evals): document frozen evaluation and quality limitations`：先审查三份S4-E报告，保留真实失败与历史记录。
2. `docs: present SuperMew-TraceRAG architecture and final delivery`：提交README与两份S5文档，保证其S4-E链接在同一分支可用。

历史实现与数据已在769b1a2/814cf69，不重新混进docs提交；若拆分当前文档成多个提交，确保README引用目标先存在。**本轮不执行git add/commit/push/merge。**

不能提交：`.env`、凭据、`.artifacts/`（详细模型/Run/Case导出、截图、日志、身份映射、S5检查工具）、运行data/volumes、venv/node_modules/dist。开始时的未跟踪`.idea/`不是本轮交付，且未被.gitignore自动覆盖，不应误选；没有为隐藏它修改.gitignore。

## 文档级交付检查

仅检查本轮三份文档，原S4-E文件Hash前后保持不变；不启动服务/模型或后端完整测试。

- 相对链接/文件与Markdown目标锚点逐项检查，包括README目录和两份新文档互链。
- 两幅Mermaid以独立忽略目录中的Mermaid parser做语法检查，不修改生产package.json/lock。
- 命令静态对照launcher argparse、生成器/原CLI参数、package.json、.env.example、Compose和正式routes；文档的未来操作命令未在S5启动部署。
- 冻结数字与正式Report及既有citation-audit/summary对照；Source/Index与历史清单保留，不重算/覆写评测基线。
- README凭据/绝对本机路径/个人账号模式检查、MIT署名与上游许可核验；图片引用为空，无未审查图片提交。
- `git diff --check`、生产文件范围和历史报告Hash检查；详细实际结果落在忽略的 `.artifacts/synthetic-enterprise/s5/`。

若某项检查失败，修正文档后复查，不扩展为生产代码/服务修复。检查通过也不抹除上面的历史测试/质量失败。

本轮实际执行结果（2026-10-13）：

| 文档检查                         | 结果                                                                              |
| -------------------------------- | --------------------------------------------------------------------------------- |
| 三份文档相对链接、文件与目标锚点 | 136 项通过，缺失 0                                                                |
| Mermaid 11.12.2 parser           | 两幅 flowchart 通过；工具只安装在忽略目录，不改生产依赖                           |
| 静态与原生导出核对               | 14 项断言通过：隐私模式、许可署名、语料数/hash、划分、命令入口、指标和变更范围    |
| 格式                             | 仅三份本轮文档经现有 Prettier 格式化，check 通过；git diff --check 通过           |
| 历史保护                         | 三份 S4-E 报告 SHA-256 与编辑前一致；历史 baseline、Gold、业务代码未修改          |
| 图片与忽略                       | 新文档未引用图片；.env、.artifacts、既有截图、node_modules、data 均由既有规则忽略 |

检查命令：`node .artifacts/synthetic-enterprise/s5/check-docs.mjs`、`node frontend/node_modules/prettier/bin/prettier.cjs --check README.md docs/second-dev/s5-project-showcase.md docs/second-dev/s5-final-summary.md`、`git diff --check`。工具初稿曾把 URL 的 `s:/` 误识别为盘符、要求历史中文“未通过”必须含英文 FAIL；收窄检测并改用原生 `native_gate_passed=false` 核对后复查通过，没有改评测结果。检查不联网调用模型、不证明所有第三方链接永远可用或仓库全量 Secret 审计通过。

## 简历项目描述草稿

### A. Python后端开发岗位

**SuperMew-TraceRAG｜企业知识库可溯源问答系统（二次开发）**  
基于开源SuperMew，面向产品Excel与售后政策增强版本化索引、来源契约及持久评测；技术栈Python、FastAPI、PostgreSQL、Redis、Milvus、LangGraph。

- 基于openpyxl实现多Sheet行语义解析与三级分块，保留表头/单位/物理行；复用Indexing Worker与Document Version发布，真实核验700个Excel叶子来源。
- 扩展Milvus动态元数据写入、查询投影和发布前读回校验，沿用Manifest/CAS与版本隔离；无需新增数据库Schema或第二套索引链。
- 将来源接入正式Evidence/Trace和有界Checkpoint恢复，校验Tenant/Version/ACL及叶子正文hash，打通Vue实时与历史引用展示。
- 构建固定种子12文档/80问答，复用持久Evaluation Worker完成一次60题冻结验收；DocRecall@10=94.34%（n53），CasePass40/60，保留Gate未通过和失败复盘。

### B. AI应用开发岗位

**SuperMew-TraceRAG｜Excel证据可追溯Agentic RAG（二次开发）**  
在SuperMew原有LangGraph/Hybrid Retrieval基础上，面向表格与跨文档场景增强证据表示、精准引用、模型兼容和可复现评估。

- 实现表头与数据行绑定的XLSX表示，结合原Dense/BM25/RRF与Parent Merge保存真实Sheet/Row/source_anchor，避免将文本页码冒充表格行号。
- 将无编号父块理解上下文与真实叶子引用分离，结合scope/hash校验和确定性引用审计；冻结严格行匹配30/33=90.91%，引用身份合法120/120，不宣称Claim事实正确率100%。
- 在原Planner/Grader/一次重写预算内增强独立事实规划与缺证补召回；按Profile/version适配DeepSeek Function Calling，保留Schema校验和普通Thinking，兼容健康Rerank调用。
- 建立20-dev/60-frozen隔离与真实原生Job评估；冻结DocRecall@5=84.91%（n53），P50/P95=7.201/11.947s（n60含Judge），CasePass66.67%且Gate FAIL，定位缺行预算与Outcome分歧。

简历可按篇幅删减指标，但不可删去上游二开定位、指标分母和质量边界后改称“生产上线/准确率96.1%/冻结AB提升”。
