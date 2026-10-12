# S3：正式来源契约

日期：2026-10-12。范围仅来源投影、恢复、引用展示与审计；S2 parser、publication、
Milvus/数据库 Schema、DeepSeek 适配、检索算法及 LangGraph 拓扑均未改动。

## 数据流和身份

S2 `excel_provenance.py` → Milvus L3 metadata → `rag/utils.py` 原有 RRF/Parent Merge/Rerank
→ `RetrievedChunk` → EvidencePack → RAG Trace → Run/Event/Message → Vue。
`utils.py` 本轮不修改；正式投影不再丢掉它已有的来源。

| 结构 | 语义与校验 |
| --- | --- |
| `ExcelSource` | Sheet 1–31 字符，禁止控制/Excel 非法字符；row 严格 int 1–10000，拒绝 bool/字符串；end≥start |
| `MatchedLeafSource` | 同一来源字段与真实 L3 `chunk_id`，禁止额外字段 |
| `RetrievedChunk` | 可选四个直接来源字段，或 `matched_leaf_sources` + truncated；继承原 Document/Version/index/hash 身份 |
| L3 | `version::filename::p0::l3::n`，非 merged，四字段必须齐全 |
| L1/L2 | 必须 merged；只能携带实际命中 L3 来源，不能冒充直接叶子 |

`backend/schemas/rag.py:valid_excel_sources` 复用 S2 `excel_provenance` 与
`matched_leaf_sources`：32 条、16 KiB、去重和排序一致。跨版本/文件叶子、错 anchor、
部分字段、绝对路径文件名均拒绝。旧 PDF/HTML/Word/XLS/无来源 XLSX 保留正式身份
但不强制新增位置。未知顶层数据只通过归一化白名单，嵌套来源严格拒绝额外属性。

## 兼容扩展

`RagTraceFields` 增加 `evidence_chunks`（最多 64）、omitted/truncated 计数、
`cited_evidence_ids`（最多 64，严格正整数）、引用总数/非法数。
入选集合与候选的 document/version/chunk/index/hash 和来源一致；文本可因预算变短。
旧 Trace 没有入选集合时只标记旧检索记录，不声称原回答已使用它。

正式 Schema 由 `scripts/generate_contract_types.py` 从 Pydantic 生成
`contracts/rag_trace_v1.schema.json`，`--check` 检查陈旧生成物。既有 RunEvent v1
envelope 不变，公开 data 增加可选 Trace 字段；TS 在原 `types/chat.ts` 同步，未引入
第二个 RetrievedChunk。历史响应中的 null 与缺省都表示没有位置。

## 修改位置

- `backend/schemas/rag.py`：三个来源模型、RetrievedChunk、Trace 校验与归一化。
- `scripts/generate_contract_types.py`、生成 Schema、`frontend/src/types/chat.ts`。
- `tests/test_rag_provenance_contract.py`、原 Trace/Excel provenance 测试：合法/拒绝、
  错版本、不连续父块、去重、有界、旧格式。

测试汇总及真实身份见 [引用评估](s3-citation-evaluation.md)。模型事实支持不是这个
Schema 的保证；复杂子问题去重仍使用原版本化身份，不加入按文件名跨版本合并。
