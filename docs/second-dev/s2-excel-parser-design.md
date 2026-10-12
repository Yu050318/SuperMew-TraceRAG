# S2：Excel 表格感知解析

日期：2026-10-12。实施范围限于 XLSX 表示、三级分块、来源保存和版本发布；未修改 LangGraph 拓扑、检索排序算法、模型协议、数据库 Schema、正式 API 或前端。实验结果见 [A/B 报告](s2-ab-evaluation.md)，来源与发布见 [索引 provenance](s2-index-provenance.md)。

## 实际修改位置

| 文件 | 类 / 函数 | 本阶段职责 |
| --- | --- | --- |
| `backend/indexing/excel_parser.py`（新增） | `parse_excel_rows`、`_display` | openpyxl 只读解析、资源边界、逐行字段语义文本 |
| `backend/indexing/excel_provenance.py`（新增） | `source_anchor`、`excel_provenance`、`matched_leaf_sources` | 来源校验与有界聚合 |
| `backend/indexing/document_loader.py` | `DocumentLoader.__init__`、`_load_excel`、`load_document` | XLSX 专用三级组织，复用既有身份和哈希 |
| `backend/indexing/milvus_writer.py` | `MilvusWriter.write_versioned_documents`、`verify_provenance` | 动态字段写入、发布前实际持久化核验 |
| `backend/indexing/milvus_client.py` | `RETRIEVAL_OUTPUT_FIELDS`、`_format_retrieval_hit` | 查询投影与严格类型恢复 |
| `backend/rag/utils.py` | `_parent_matches_child_scope`、`_merge_to_parent_level`、`dedupe_documents` | ACL 一致性和命中叶子来源保留，不改变合并阈值 |
| `backend/documents/publication.py` | `DocumentPublicationConfig.from_runtime`、`DocumentPublication._run_once` | 新 BuildProfile，核验后沿用 Manifest/CAS |
| `backend/evaluation/rag_adapters.py` | `rag_source_fingerprint` | 将两个新解析模块纳入源码身份；不改 Evaluation Contract |
| `.env.example`、`README.md` | Parser / Chunker 配置说明 | 部署使用新版本，不把新语义标记为旧版本 |

既有 `.gitignore`、Docker、启动脚本和 S1.5 的模型修改不是本阶段重新实现的功能。忽略的本地 `.env` 只调整两项非 Secret Parser/Chunker 版本。未修改 `ParentChunk` ORM 或 `ParentChunkStore`。

## 为什么不用第二套解析或索引框架

按 ponytail 的复用原则，新增一个小解析模块和一个来源校验模块；依赖已有 openpyxl，沿用 `DocumentLoader`、`DocumentPublication`、MilvusWriter、ParentChunkStore、原生 Worker 和 Evaluation。没有新增依赖、业务数据库、客户端或正式 Evidence 类型。

旧 XLSX 经 `UnstructuredExcelLoader` 输出大段表格文本。旧块中出现全部列名，不代表每一行独立绑定列名和值；不能把所有旧块都描述成“完全没有表头”。S1.5 实际有些命中父块含表头，但检索叶子缺少可靠的行级对应和来源。

## 数据结构与例子

示意输入 `型号 / 功率W / 重量kg`，数据行 `NX-002 / 180 / 3.1`，生成：

```text
Sheet：参数；型号：NX-002；功率W：180；重量kg：3.1
```

`parse_excel_rows` 每项为 `{text, sheet_name, row_start, row_end}`。行号从 1 开始，表头位于第 1 行，第一条业务记录位于第 2 行。跳过空行不重新编号；同名型号不去重；空值显示 `（空）`，不是数字零。零、负数、小数、布尔和日期分别保留确定性的字符串/ISO 表示。单位来自原列名或原值，不从 Excel 显示格式猜测单位。

超过 L3 预算的行分成多个片段，重复 Sheet 和第一列身份，每个字段片段保留列名；多个片段均对应同一物理行，不误报成连续多行。第一列用于重复上下文，不推断其唯一性。拒绝超过半个片段预算的第一列，避免无界身份复制。文本经过现有 `sanitize_text`。

来源示例：`sheet:%E4%BA%A7%E5%93%81%E5%8F%82%E6%95%B0:row:2`。`sheet_name` 保留原 Unicode 名称，锚点采用 UTF-8 percent encoding，范围采用 `row:2-4`。不含路径，不替代版本化 `chunk_id`，不把 Sheet 编造为 PDF 页。

## 三级分块

`_load_excel` 按 Sheet、字符预算组装 L2，再组成同 Sheet 的 L1；L3 为行或有界行片段。没有跨 Sheet 的父块和人为 overlap。默认 L3=800、L2=1600、L1=2400 字符，沿用现有配置下界。`_build_chunk_id`、`_content_hash` 继续使用正式实现：

```text
<Document Version ID>::<filename>::p0::l3::<文件内该层计数>
```

三个层级分别使用文件范围计数，避免多 Sheet 重复 Chunk ID；`root_chunk_id`、`parent_chunk_id`、`chunk_idx`、Tenant、Knowledge Base、Document、Document Version、Index Version、ACL、content_hash 均保留。`page_number=0` 是无页码哨兵，不携带行号。`section_id` 为编码后的 Sheet 身份。

解析内存中的父块有真实覆盖范围；PG 父块不新增来源字段。检索合并后恢复的是“实际命中叶子集合”，不是完整父块行级 provenance。具体边界见来源文档。

四份不可变 S1 Fixture 实际解析为参数 200、价格 200、库存 200、维修 100 个叶子；全部字段标签存在，700 条真实身份、内容哈希和来源与 Milvus 精确比对成功。PDF、Word、HTML 仍经 `_load_from_langchain_docs` / `_split_page_to_three_levels`；XLS 仍经旧 `UnstructuredExcelLoader`，绝不交给 XLSX parser。

## 支持边界与失败方式

| 项目 | 实际策略 |
| --- | --- |
| 文件 | 仅 XLSX；压缩 20 MiB，展开 50 MiB，最多 2048 ZIP entry；拒绝重复 entry、VBA |
| Sheet | 最多 32；仅解析可见 Sheet；不摄取隐藏数据 |
| 规模 | 每 Sheet 最多物理行 10000、列 100；可见 Sheet 声明范围面积合计最多 200000 单元格 |
| 表头 | 第 1 行非空、唯一、每列名最多 128 字符；不推断多级表头 |
| 文本 | 单元格最多 10000 字符；片段预算 600–4000 |
| 合并单元格 | 第一版整本拒绝，包括隐藏 Sheet 中的合并；明确错误，不平铺猜测 |
| 公式 / 错误值 | 可见单元格全部拒绝；即使存在缓存也不认定其新鲜可靠，要求先导出计算后的值 |
| 异常尺寸 | XML 检查实际物理坐标；缺失/无效尺寸或声明尺寸不足以覆盖实际单元格时拒绝，避免只读迭代静默漏行 |
| 空工作簿 | 无可见业务行时拒绝 |

第一版不实现公式计算、跨 Sheet 引用、格式化单位推断、合并表头、多级表头或无限工作簿。失败走原生 Index Job/Candidate 失败流程，不静默补值。资源限制不是完整恶意 OOXML 安全审计证明。

## 测试与后续边界

新增 `tests/test_excel_parser.py` 30 项，含真实四份 S1 Fixture、数据类型、空行、多 Sheet、隐藏 Sheet、重复记录、长行、资源上限、合并、XLS 和异常尺寸。测试命令和总结果由 [A/B 报告](s2-ab-evaluation.md#测试与命令) 统一维护。

评测完成后补了尺寸不足的 fail-closed 加固和等价类型收窄，重新执行离线/存储核验；未重复调用模型。报告明确区分实验源码和最终交付源码身份。

S3 可使用内部四字段及 `matched_leaf_sources`，但应另行设计正式 RetrievedChunk、Evidence、Citation 的投影和版本兼容。当前前端、Checkpoint、公开 RAG Trace 不自动携带这些字段，本阶段没有实现 UI 引用。
