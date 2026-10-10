# SuperMew 二次开发源码分析与实施方案（S0）

> 分析日期：2026-10-10。本文根据当前工作树源码、测试、仓库约束文档和 `SuperMew_Codex_Implementation_Plan.md` 编写。计划文档中的 `suggested/...` 路径、类名和字段是设计建议，不视为现有实现。

## 1. S0 结论

计划总体可行，且不需要重建 SuperMew 的核心架构。当前项目已经具备：

- 持久化 Thread/Run/Event、PostgreSQL 事实源、Redis 通知、Milvus 检索和独立 Indexing/Evaluation Worker；
- 不可变 Document Version、候选构建、Manifest 校验、CAS 发布和版本清理；
- 三级文本分块、父子 Chunk、Dense + Milvus 原生 BM25、RRF、Auto-merging、可选 Rerank、Grader、Step-back/HyDE、复杂问题子问题合成和 HITL checkpoint 恢复；
- RAG Trace 中的检索身份、Chunk 身份、版本、hash、评分、降级和覆盖缺口；
- Vue 引用展示组件和离线/Live RAG Evaluation contract。

当前最明确的产品缺口是：`.xlsx` 通过 `UnstructuredExcelLoader` 被转换为普通文本，现有 `RetrievedChunk` 没有 Sheet、物理行、列头或稳定 source anchor；因此无法可靠展示计划要求的“Excel Sheet + Row”。引用展示也已有基础实现，后续应扩展既有 contract，而不是另建 References 或 `/chat` 路径。

## 2. 已阅读的约束和事实来源

已阅读：

- 根目录 `AGENTS.md`、`CONTEXT.md`、`README.md`；
- `backend/AGENTS.md`、`backend/rag/AGENTS.md`、`frontend/AGENTS.md`、`frontend/src/events/AGENTS.md`；
- `contracts/AGENTS.md`、`tests/AGENTS.md`、`docs/AGENTS.md`、`evals/rag/AGENTS.md`；
- 架构图 `docs/architecture/supermew-system-architecture.html`；
- RAG 相关 ADR：0011、0012、0013、0014、0024，以及文档版本、索引 Worker、引用和 canonical implementation 相关 ADR；
- `evals/rag/README.md`、测试清单和相关源码；
- 根目录 `SuperMew_Codex_Implementation_Plan.md` 全文。

必须保持的不变量：上传 API 只创建 durable Index Job；解析、Embedding、Milvus 写入由 Worker 持有；候选版本必须在 PostgreSQL CAS 发布前完成 manifest 校验；旧 READY 版本不能被失败候选污染；一次 Run 使用冻结的 Retrieval/Model Snapshot；RAG provider failure 不能伪装成 NO_KNOWLEDGE；RAG Trace 不保存 chain of thought、Secret 或无必要正文；Contract 修改必须同步后端 schema、前端类型、生成物和测试。

## 3. 当前真实数据流

```mermaid
flowchart LR
  U[Vue Chat / Documents] --> API[FastAPI routes]
  API --> PG[(PostgreSQL)]
  API --> RUN[Thread -> Run -> AgentExecutor]
  RUN --> GRAPH[backend/rag/pipeline.py]
  GRAPH --> RET[backend/rag/utils.py]
  RET --> CAT[DocumentRetrievalScope]
  RET --> MV[(Milvus Dense + BM25)]
  RET --> PCS[(ParentChunkStore / PostgreSQL]
  GRAPH --> TRACE[RAG Trace / EvidencePack]
  TRACE --> EVENT[Run Event / Message]
  EVENT --> UI[References.vue / KnowledgeContextPanel.vue]
  API --> JOB[Index Job]
  JOB --> W[IndexingWorker]
  W --> LOAD[DocumentLoader]
  LOAD --> SPLIT[3-level text chunks]
  SPLIT --> EMB[MilvusWriter + ParentChunkStore]
  EMB --> MAN[Manifest verify]
  MAN --> CAS[DocumentCatalog.publish]
  EVAL[Evaluation Worker / scripts/evaluate_rag.py] --> GRAPH
  EVAL --> REPORT[JSON + Markdown report]
```

### 3.1 文档解析、分块和索引

真实入口是 `backend/indexing/document_loader.py:DocumentLoader.load_document`。当前行为：

- PDF 使用 `PyPDFLoader`；Word 使用 `Docx2txtLoader`；HTML 使用项目自己的 `html_processor`；XLSX/XLS 使用 `UnstructuredExcelLoader`；
- `_load_from_langchain_docs` 统一生成带 `filename`、`file_type`、`page_number`、Tenant/KB/Document/Version/Index scope 的基础字典；
- `_split_page_to_three_levels` 通过三个 `RecursiveCharacterTextSplitter` 生成 L1/L2/L3，并写入 `chunk_id`、父子关系、`root_chunk_id`、`chunk_level`、`chunk_idx`、`content_hash`；
- chunk ID 是 `document_version_id + filename/page/level/index`，版本隔离已经存在；
- `DocumentArtifactMetadata` 已经是稳定身份和 ACL 元数据的入口。

XLSX 的实际缺口是 `UnstructuredExcelLoader` 没有把工作表、物理行和表头作为受控 provenance 带入基础字典。计划中的 `TableRowEvidence` 可以作为内部规范化概念，但不应直接复制成第二个正式数据对象；更小的改动是让 Excel 专用解析器输出与 `_load_from_langchain_docs` 相同形状的 raw document，并额外带 `sheet_name`、`row_start/end`、`column_headers`、`source_anchor`。

`backend/indexing/milvus_writer.py:MilvusWriter.write_versioned_documents` 已经：

- 校验所有文档共享同一完整版本 scope；
- 校验 `text`、`filename`、`file_type`、`chunk_id`、`content_hash` 和版本身份；
- 按 batch 生成 embedding，写入 dense vector、text、文件/页、chunk 层级、Tenant/KB/Version、ACL 和 content hash；
- 返回可精确校验和按版本删除的 `IndexWriteReceipt`。

Milvus schema 当前明确存有 `page_number` 和 chunk/version metadata，但没有 Sheet/row/anchor。大字段或结构化 provenance 不应直接塞进 Milvus；优先评估复用 ParentChunkStore 的权威记录，只有查询返回链路确实需要时才扩展 Milvus schema。

`backend/indexing/parent_chunk_store.py:ParentChunkStore` 负责 parent 文档 upsert、按 chunk ID 回查、按 Version 校验和删除，是保存扩展 provenance 的首选现有 seam，需先确认 ORM `ParentChunk` 的 JSON/字段能力，再决定是否需要 migration。

### 3.2 Index Job、版本和发布

`backend/documents/catalog.py` 提供：

- `BuildProfile(parser_version, chunker_version, embedding_model, index_version)` 和 fingerprint；
- `VersionBuild`、`IndexJobExecution`、lease/fence；
- `DocumentCatalog.claim_index_job`、`record_manifest`、`publish`、retry/dead-letter 和清理流程；
- `DocumentVersionRecord` 中已有 parser/chunker/embedding/index version、build fingerprint、collection、chunk counts 和状态。

`backend/documents/worker.py:IndexingWorker._run_index` 只负责领取、续租、调用 publication service、错误分类和重试。真正的解析/写入顺序由 `backend/documents/publication.py` 持有，应在该模块定位 `DocumentLoader`/`MilvusWriter` 调用点后插入 Excel parser。不能在 API route 解析文件，也不能绕过 Worker/Manifest/CAS。

因此计划中的“parser version/chunker version 改变后建立隔离新索引、旧 READY 版本继续服务”可行，并且是现有 BuildProfile/Document Version 设计的直接用法。

### 3.3 LangGraph RAG、Evidence 和引用

正式图在 `backend/rag/pipeline.py`，检索实现和 Auto-merging/Rerank 在 `backend/rag/utils.py`，恢复/持久化投影在 `backend/rag/checkpoint_runner.py`。当前链路已经包含：

1. 复杂度分类和简单/复杂路由；
2. `retrieve_documents`，Dense + BM25、RRF、候选池和版本/租户过滤；
3. Auto-merging、可选 Rerank 和显式降级 trace；
4. `pack_evidence` 预算裁剪；
5. Grader、Step-back/HyDE、一次重写和复评；
6. 子问题合成、确定性去重、HITL 和 `rag_trace`。

`backend/rag/evidence.py:EvidencePack` 当前将每个证据渲染为 `filename (Page N)`，并保留被选中的 document dict；这是最小的 Evidence seam。`pipeline.py:_copy_jsonable_doc` 是 resume 快照的裁剪 seam，不能把所有新元数据无界地放入 checkpoint。

`backend/schemas/rag.py:RetrievedChunk` 已要求 `chunk_id`、`document_id`、`document_version_id`、`section_id`、`index_version` 和 SHA-256 `content_hash`，并由 `normalize_rag_trace` 严格过滤字段。这里是 F2 的正式 contract seam：新增 sheet/row/source_anchor 后必须同时改 Pydantic schema、归一化逻辑、前端 `types/chat.ts`，并补 schema/trace 测试。

当前“引用来自命中证据”的基础条件已经存在：`rag_trace.retrieved_chunks` 来自检索/合成结果，前端引用按该列表展示；但没有 Excel provenance，也没有单独的 citation ID 合法性校验。P0 应先把 provenance 与命中 chunk 身份贯穿，再决定是否需要引用 marker 校验；不应另建 RAG 图或独立 citation store。

### 3.4 前端引用展示

计划文档所示的 `frontend/src/components/Chat/References.vue` 实际存在。它展示 `filename`、`page_number`、RRF/rerank 分数和 excerpt，并通过 `cite-click` 定位消息内引用。`KnowledgeContextPanel.vue` 也展示 retrieved chunks 和位置摘要。前端类型定义在 `frontend/src/types/chat.ts`，Event reducer 在 `frontend/src/events/runEventReducer.ts` 读取 `rag_trace`。

所以 F2 前端不是“新增组件”，而是：

- 扩展 `RetrievedChunk` 为可选 `sheet_name`、`row_start`、`row_end`、`source_anchor`（字段名最终以实际后端 contract 审查为准）；
- 更新 References/ContextPanel 的位置渲染，并对旧 PDF/HTML page 字段保持兼容；
- 增加组件、类型和事件投影测试；
- 不把未授权的绝对路径、源文件内容或 Secret 传给浏览器。

### 3.5 Evaluation

正式评测实现已存在于：

- `backend/evaluation/rag.py`：`RagEvalDataset`、`RagEvalCase`、gold document/chunk、Observation、Metric、Gate、Report、fingerprint 和评分器；
- `backend/evaluation/rag_adapters.py`：`PredictionFileAdapter`、`LiveRagEvalAdapter`、Observation 投影、RAG source/profile/corpus fingerprint；
- `scripts/evaluate_rag.py`：`validate`、离线 `score`、调用正式 RAG 的 `run`；
- `evals/rag/`：版本化 dataset、corpus、offline observations、gates、baseline 和 schema；
- `backend/evaluation/worker.py`、repository、API routes：持久 Evaluation Job 生命周期。

现有 Evaluation 已覆盖 case pass rate、document/chunk recall、MRR/nDCG、复杂度/route/outcome/HITL、provider failure 等指标，并严格区分 `contract_smoke` 与 `live_rag`。计划中的 80 条 synthetic dataset 可以适配现有 `RagEvalDataset`，但不能按示例 JSON 另建第二套正式 Dataset contract；Excel row/sheet 引用质量需要先确认是扩展 gold chunk identity，还是作为现有 Observation 的安全附加指标。

## 4. 功能盘点

| 计划能力 | 当前状态 | 判断 |
|---|---|---|
| FastAPI Thread/Run/Event/SSE | 已有 | 不改接口；沿用 `/v1/threads`、runs、events stream |
| PostgreSQL/Redis/Milvus 三进程架构 | 已有 | 不新增业务 Redis/MySQL |
| Document Version、Index Job、Manifest、CAS publish | 已有 | 复用 `DocumentCatalog`/publication/worker |
| 非 XLSX 文档解析 | 已有 | 保持 PDF/Word/HTML 路径不变 |
| 三级分块、parent/child、chunk hash | 已有 | Excel 只接入既有 DTO/索引流程 |
| Dense + BM25、RRF、Auto-merging、Rerank | 已有 | 不写第二套检索 |
| Grader、Step-back/HyDE、复杂问题 synthesis、HITL | 已有 | 不改图拓扑，除非 provenance 需要最小字段传播 |
| RAG Trace / Evidence budget / 检索身份 | 已有 | 扩展 metadata，保持 fail-closed schema |
| 引用 UI | 已有基础能力 | 改字段渲染和测试，不新建 References 页面 |
| 离线/Live Evaluation contract | 已有 | synthetic 数据适配现有 schema |
| XLSX 单行表头、Sheet/物理行 provenance | 缺失 | F1 主要二开 |
| 行级语义文本和稳定 source anchor | 缺失 | F1 二开，复用现有 chunk ID 并增加 anchor |
| 引用 provenance 校验 | 部分已有 | F2 在 RetrievedChunk/trace seam 补强 |
| 80 条企业合成语料与 A/B 报告 | 缺失 | F3 复用评测执行器，新增资产/生成脚本 |

## 5. 方案可行性与需要修正的计划点

### 可行部分

- 用 Excel 专用 raw-document parser 接入现有 `DocumentLoader`/publication 流程，可保留非 Excel 行为；
- 用现有 BuildProfile fingerprint 和 Document Version 隔离 parser/chunker 版本；
- 用现有 Milvus scope/filter、ParentChunkStore 和 `RetrievedChunk` 传播 provenance；
- 用现有 `References.vue` 和 `rag_trace` 展示 Sheet/Row；
- 用现有 Evaluation Adapter 调正式 RAG 生成 live observations，并用 dataset/corpus/source fingerprint 保证可比性。

### 必须在 S1/S2 设计阶段确认

1. `ParentChunk` ORM 的可扩展字段/JSON 能力，以及 Milvus schema 是否必须同步加入 sheet/row；优先不新增表，只有权威回查无法承载时才做 migration。
2. Excel provenance 应挂在每个 L3 行 chunk 上，还是在 L1/L2 父块上同时聚合。建议叶子保留单行 anchor，父块保留子行 anchor 集合或通过 ParentChunkStore 回查，避免合并后丢失行号。
3. 现有 publication service 的实际调用点和 `BuildProfile` 注入点；必须用源码确认后再修改，不凭计划文档猜路径。
4. `page_number` 当前 Pydantic 是 `str | int`，前端是 `number`；sheet/row 新字段的类型和旧文档兼容策略需统一。
5. citation “合法引用”与“事实支持引用”是两个指标。P0 先实现证据身份合法性和 provenance 展示；事实级 entailment/judge 若超出现有 Evaluation contract，应作为明确的 P1/实验指标，不阻塞 F1。
6. Excel 公式缓存、隐藏 Sheet、合并表头、文件大小和行列预算的现有上传/解析限制。P0 只接受计划约定的单行表头和常规值，异常要清晰失败或警告，不能静默错位。

## 6. 真实建议修改位置

### F1：Excel 表格感知解析与版本索引

优先检查并可能修改：

- `backend/indexing/document_loader.py`：按扩展名选择 Excel parser，并把 raw document/provenance 接入现有三级分块；保留现有 PDF/Word/HTML 分支；
- `backend/indexing/`：新增最小 Excel parser 模块（只有确认没有现成 helper 后才新增），使用已安装 `openpyxl`；
- `backend/documents/publication.py`：确认并接入 parser 输出、BuildProfile 版本和 chunk/parent 统计；
- `backend/documents/catalog.py`：仅在需要传播 parser/chunker fingerprint 或 manifest 字段时修改；
- `backend/indexing/milvus_writer.py`、`parent_chunk_store.py`：扩展 metadata 传播/回查；
- `backend/indexing/milvus_client.py`：仅在已有 schema 无法承载必要检索 metadata 时改 schema；
- `tests/`：新增最小离线 xlsx fixture 测试，补空行、0、日期、重复型号、多个 Sheet、公式缓存缺失和确定性 anchor；复用 `test_milvus_writer.py`、`test_parent_chunk_store_versions.py`、`test_indexing_worker.py`、`test_document_version_artifacts.py` 的既有 seam。

### F2：Evidence、引用和前端展示

- `backend/schemas/rag.py`：扩展 `RetrievedChunk` 和 trace normalization；
- `backend/rag/evidence.py`：渲染 Sheet/Row 时保持 EvidencePack 的预算和排序语义；
- `backend/rag/pipeline.py`：只在必要处扩展 `_copy_jsonable_doc`、trace 组装，禁止引入第二条图；
- `backend/rag/utils.py`：确认 Auto-merging/dedupe 不丢 provenance；必要时对合并文档做确定性 anchor 聚合；
- `frontend/src/types/chat.ts`：同步类型；
- `frontend/src/components/Chat/References.vue`、`KnowledgeContextPanel.vue`：展示 Excel 位置并兼容 Page；
- `frontend/src/events/runEventReducer.ts`：通常无需逻辑改动，若 contract 归一化要求则补投影测试；
- `tests/test_rag_trace_schema.py`、`test_rag_evidence.py`、`test_rag_retrieval_targets.py` 及前端组件/类型测试：验证旧文档回归、命中身份、版本隔离和新位置字段。

### F3：合成数据和评测

- `evals/rag/`：新增 synthetic enterprise 资产，严格标注 synthetic、seed、hash、split；不要把 questions/gold 上传到知识库；
- `scripts/`：新增生成器和报告适配器前，先复用 `scripts/evaluate_rag.py`、`backend/evaluation/rag.py`、`rag_adapters.py`；
- `backend/evaluation/`：只有现有 gold/Observation 无法表达 row/sheet 引用质量时才扩展 contract，同时更新 schema 生成物、测试和评测 ADR；
- `.artifacts/`：只保存未提交运行结果，不污染 committed baseline；
- 测试复用 `test_rag_evaluation.py`、`test_rag_eval_adapters.py`、`test_rag_eval_cli.py` 和 `evals/rag/AGENTS.md` 规定的 fingerprint/provenance 门禁。

## 7. 分阶段实施和依赖

### S0（本次，已完成）

- 完整阅读计划、仓库规则、架构/ADR/Runbook、源码入口和相关测试；
- 确认现有能力、实际缺口、正式 seam 和不变量；
- 输出本文；
- 不修改核心业务代码、不改数据库、不改索引、不提交/推送。

### S1：合成语料与初始基线

依赖：S0，且先确认现有 Dataset contract 的 gold identity 字段。

建议动作：新增确定性 `source_records.json` 驱动的生成器、少量 xlsx/md 语料、questions/splits/manifest；先用现有离线 `validate`/`score` 建立 contract smoke，再决定是否运行隔离 live profile。S1 不应先改生产 RAG。

### S2：Excel parser 与版本索引

依赖：S1 fixture/ground truth；S2 是 F2 的前置。

建议动作：实现单行表头、跳过空/隐藏 Sheet 策略、受控值格式化、行级文本、anchor、预算和错误语义；接入现有 publication/worker/Milvus/ParentChunkStore；用新的 parser/chunker version 触发 candidate rebuild，验证旧 READY 版本不变。

### S3：Evidence provenance、引用校验和 UI

依赖：S2 产出的真实 row/sheet metadata。

建议动作：扩展 `RetrievedChunk`/trace contract 和 EvidencePack 展示；保证 RRF、Rerank、Auto-merging、复杂 synthesis 后不丢 anchor；前端引用显示 Excel Sheet/Row；加入合法引用与版本/权限测试。

### S4：隔离 Live A/B 评估

依赖：S1 数据、S2 可检索索引、S3 provenance/引用字段。

建议动作：调用正式 `LiveRagEvalAdapter`，分别使用原版/改进 parser 的隔离 index/profile，比较相同 corpus/问题 split 下的 document/chunk recall、MRR/nDCG、answer/outcome、evidence coverage、引用合法性/质量、延迟和成本；报告必须保留 source/index/profile fingerprint，不凭空宣称提升。

### S5：收尾

依赖：S4 结果和已解决风险。

建议动作：补 ADR/README/Runbook（若用户可见能力或运行流程变化）、完整门禁、简历材料；只陈述已实际测得的指标和边界。

## 8. S0 最小验证命令

本次只做文档分析，未运行需要外部服务/模型的 live index 或 live RAG。后续 S1 可先运行：

```bash
cd SuperMew
uv run --no-sync python scripts/evaluate_rag.py validate --dataset evals/rag/rag_smoke_v1.json
uv run --no-sync python scripts/generate_rag_eval_schemas.py --check
uv run --no-sync python scripts/evaluate_rag.py score \
  --dataset evals/rag/rag_smoke_v1.json \
  --observations evals/rag/offline_smoke_observations_v1.json \
  --gates evals/rag/gates_v1.json \
  --report .artifacts/rag-eval/s0-report.json \
  --fail-on-regression
```

这些命令是建议的最小离线基线命令；本次没有把未运行命令写成已通过。S2 修改后还需按实际变更运行 document/indexing、Milvus contract、RAG trace/evidence 和前端类型/组件测试；涉及 PostgreSQL/Milvus schema 或锁语义时必须增加真实 integration/smoke。

## 9. 开始 S1 前需要解决的问题

1. 先确认 `publication.py` 的实际解析调用点和 `ParentChunk` ORM 字段，决定 provenance 是否无需 migration。
2. 决定 `source_anchor` 的稳定格式和公开字段最小集合，例如 `file::sheet::<url-encoded-sheet>::row::<n>`；不要包含绝对路径。
3. 明确旧版 baseline 的职责：原版与改进版必须通过不同 parser/build/index identity 区分，不能覆盖现有 `evals/rag` baseline。
4. 确认 synthetic corpus 是否按 12 个文档起步，并把 80 个问题的 gold 映射到现有 `RagGoldChunk`/Observation，而不是复制示例 contract。
5. 选择 P0 的公式/隐藏 Sheet/合并表头语义并写成测试：建议公式无缓存时受控拒绝或明确缺失，复杂多级表头暂不支持。
6. 统一前后端 row 类型（建议正整数 `int`，row range 用 `row_start`/`row_end`），并定义旧 page-only 文档的兼容显示。

## 10. 结论

S0 不建议修改核心业务代码。最小且安全的二开路径是：在现有 DocumentLoader → publication → MilvusWriter/ParentChunkStore → RetrievedChunk/RAG Trace → References.vue → Evaluation Adapter 链路上增加 Excel provenance 和确定性评测资产。当前没有发现计划必须推翻的架构设计；需要避免的主要风险是误以为引用 UI、RAG、Evaluation 或版本发布尚不存在，从而重复实现或破坏现有正式接口。
