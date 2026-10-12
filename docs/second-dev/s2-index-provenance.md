# S2：版本化索引与 Excel 来源

日期：2026-10-12。解析规则见 [Parser 设计](s2-excel-parser-design.md)，指标见 [A/B 报告](s2-ab-evaluation.md)。采用 Milvus Dynamic Metadata，不增加 PostgreSQL 字段。

## 来源数据流

```text
原生上传 → DocumentPublication / Candidate Document Version
 → DocumentLoader._load_excel（L1/L2/L3 + 原身份）
 → ParentChunkStore（原 L1/L2 正式字段，不增加 provenance）
 → MilvusWriter（L3 正文 + 4 个动态来源字段）
 → 原 Exact Verification + 额外 Strong 来源核验
 → 原 Manifest → CAS Publish → READY
 → Dense/BM25/Hybrid 共用输出投影 → 严格来源校验
 → 原 Parent Merge + 有界实际命中叶子来源 → 原 Rerank
```

Milvus 最小字段为 `sheet_name: str`、`row_start: int`、`row_end: int`、`source_anchor: str`。`column_headers` 不重复存储：字段语义已包含在叶子正文内。`excel_provenance` 对全部缺失的旧记录返回空来源；部分缺失、bool/string 行号、越界范围、错误锚点直接报错，不放宽旧格式校验。

Writer 在 Embedding/删除/写入前验证来源。`RETRIEVAL_OUTPUT_FIELDS` 和 `_format_retrieval_hit` 共同覆盖 Dense 与 Hybrid 投影。原 Collection 开启 dynamic fields，无新增固定 Milvus Schema、Collection 双读或生产迁移。

## 真实 Milvus 验证，不仅 Mock

`tests/test_excel_milvus_integration.py` 在本地真实 Milvus 创建唯一临时 Collection，使用原 Writer 和查询实现；本地确定性 16 维 Embedding fixture 只隔离来源存储测试，不用于声称 RAG 质量。

实际验证：动态字段写入；Dense 查询；BM25 查询经正式 formatter；Hybrid/RRF 查询；Tenant、ACL、Document Version 过滤；旧记录无来源兼容；Strong 查询精确核验；删除指定 Version 后另一 Tenant/Version 仍存在。运行结果 1 passed。首次运行因 fixture 缺少既有必需字段 `file_type` 失败，补全 fixture 后通过，未绕过生产字段检查。

测试 `finally` 只删除本次随机生成且验证名称的 Collection。没有清空共享 Collection 或用户业务数据。Rerank 的 metadata 保持由单元测试验证；真实模型实验的 Rerank 请求错误后原生回退，不能称为真实成功 Rerank。

## Parent Merge：覆盖范围不等于命中证据

`_parent_matches_child_scope` 继续检查 Tenant/Knowledge Base/Document/Version/Index/filename，同时检查 ACL 列表一致性。`_merge_to_parent_level` 保留父块原文、content_hash、身份，添加：

```json
{
  "matched_leaf_sources": [
    {"chunk_id": "<真实Version>::<filename>::p0::l3::<编号>",
     "sheet_name": "产品参数", "row_start": 2, "row_end": 2,
     "source_anchor": "sheet:%E4%BA%A7%E5%93%81%E5%8F%82%E6%95%B0:row:2"}
  ],
  "matched_leaf_sources_truncated": false
}
```

示例身份占位符不是可导入 Gold Chunk。实际身份存于忽略的 `s2/leaf-source-identities.json` 和 `retrieval-sources.jsonl`。

只聚合真正检索到的 L3 来源；L2→L1 时继承同一集合。按真实 chunk_id 去重并排序，冲突来源报错，校验叶子属于当前 Document Version。最多 32 个来源、UTF-8 JSON 最多 16384 字节，超限显式设置截断标志。`dedupe_documents` 对同父块来源取并集，不把未命中的父块所有行加入集合。不得把 `[2,6]` 的命中改写成 `2–6` 的全范围证据。

真实 `table_query_001` 观测中参数父块保留命中的多个物理行（含 NX-001 的第 2 行）。父块本身不被标记为“第 2 行的一条记录”。元数据不是对模型引用正确性的自动保证。

`_copy_jsonable_doc`、`normalize_rag_trace` 的正式白名单不扩展，新来源不无条件进入持久 Checkpoint/公开 Trace；新增测试证明此边界。Checkpoint 恢复后来源可能不可见，是 S3 正式投影设计需解决的问题，不在 S2 假装贯通。

## Version、Manifest 与发布

新版本：`document-loader-excel-v3` / `three-level-excel-row-v3`。`from_runtime` 拒绝其他 Parser/Chunker 标签，防止新二进制用旧标签发布；回滚应采用匹配的原代码/配置部署和正式版本发布，不通过热切换环境变量伪装 Parser。

API 和 Indexing Worker 启动采用同一 BuildProfile，heartbeat 无不兼容 Worker。B Build Fingerprint：

```text
ecd83a43735338e2f909223457682bffa7326b6abd589304b95190262b4a9f03
```

只为四份 XLSX 经正式上传新建 Candidate；八份 HTML 的旧 READY Version 不变。没有原地覆盖 READY 数据。四个 Index Job 均第 1 次尝试 completed，全部 12 个当前 Version READY：

| 文档 | 真实新 Document Version ID | L3 |
| --- | --- | ---: |
| inventory.xlsx | docver_f515043826194db68855bdd7aa3c3a96 | 200 |
| product_prices.xlsx | docver_5551578bd75e449084cd1608d22f558a | 200 |
| product_specs.xlsx | docver_0c8b6bd223db4f8ab4c6637bea269583 | 200 |
| repair_records.xlsx | docver_c057ae23c2f644b4b9b6883541882924 | 100 |

`verify_receipt` 原 Manifest ID/content_hash 精确核验保留；新增 `verify_provenance` 在 Manifest/PUBLISH 前按完整 Version Scope、Strong consistency 查询每个叶子的四字段并比较。**Manifest 自身未新增 provenance hash**，不能声称其已有 hash 覆盖来源 metadata；额外核验填补发布时校验缺口，后验 `provenance-audit.json` 另保存内容摘要。

持久化审计对不可变四份 XLSX 以真实 Version ID 重解析，700 个 chunk_id、正文 content_hash、四字段逐项匹配。当前全部文档的 Manifest/PG/Milvus 身份核验记录在 `index-identities.json`；不人为构造 Version ID 或 Chunk ID。原 Candidate 清理、lease ownership、CAS 和原 Version 可读流程复用不变。

失败核验单元测试证明不发布、不创建成功 Manifest、旧 READY 保留且清理精确 Candidate。真实环境验证了成功上传/Worker/发布及临时 Collection 精确删除；未进行生产进程崩溃或并发 lease takeover 的新 live 故障注入，不能把单元测试说成这些故障的端到端证明。

## A/B 隔离与清理边界

此前 default Tenant 中已核验只有 12 个测试文档、单独测试 Knowledge Base；本轮再次断言原 owner=3、文档集合完全匹配 allowlist。经用户授权仅重设此账号随机密码，正式登录/上传/创建 Evaluation Job，最后 logout；不落盘密码/Token，不改变角色或所有权。

A 使用 S1.5 已保存且发布前核验的真实结果，不在 B Catalog 下重跑 A。B 当前 Catalog Index ID 与 A 不同，见 A/B 报告。旧四 Version 遵循系统固定一小时保留/cleanup，不延长保留、不越过 ACL 手动切换、不清空共享数据。

知识库上传仅四份 allowlisted XLSX；八份 HTML 保持已索引内容。source_records、Dataset、Reference Answers、ground_truth、实验 JSON 均未上传。allowlist 每份原文件 SHA-256 与 S1 manifest 一致。

## S3 可消费接口与尚未覆盖

叶子内部四字段、父块 `matched_leaf_sources` 和截断标志可直接作为 S3 输入。建议正式 RetrievedChunk 使用有界来源结构，明确“块覆盖位置”与“命中叶子位置”两种语义，并对 EvidencePack、Citation、Checkpoint 安全投影分别设计兼容和测试。必须继承 Tenant/Version/ACL 约束，不将 source_anchor 当业务身份。

暂不增加 PG provenance JSON：当前反例（多行父块仅命中部分叶子）已能由真实叶子集合处理。如果未来要求无叶子上下文的持久父块全范围恢复，再以具体需求与 migration 设计讨论 PG；不提前实现第二来源权威。
