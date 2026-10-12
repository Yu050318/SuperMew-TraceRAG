# S4-A：父块上下文与真实叶子引用

## 实测根因

以 `.artifacts/synthetic-enterprise/s3/persistent-cases.json` 与 `citation-audit.json` 为 A，不重跑或覆盖。`table_query_002/003/004`、`cross_document_002`、`version_policy_001/002` 的实际 Excel 引用行数为 20、24、2、4、16、1，Gold 各一行。`utils._merge_to_parent_level` 保留 `matched_leaf_sources`，但丢弃叶子正文；`pack_evidence` 为父块分配单一编号，引用该编号自然关联整个命中集合。最后一例只有一行，因此严格通过。身份没有伪造，问题是把理解上下文误当作独立证据。原审计规则不应降低。

## 两种方向

| 方向 | 正确性与范围 | 成本与兼容 |
| --- | --- | --- |
| A：保留真实 matched leaf 正文 | 可检验正文哈希、身份和行来源，但不自动证明事实蕴涵 | Parent Merge 保留有界正文；零补读，原父块排序保留 |
| B：EvidencePack 仅凭父块归因 | 来源列表不足以恢复原叶子正文/hash；文本反推行号存在歧义 | 小范围，但不能提供可信细粒度身份 |

选择 A 提供正文，复用 B 的正式 `pack_evidence` seam 受控组装。不调用无 Snapshot filter 的 `MilvusStore.get_chunks_by_ids`，不读取未命中行，不新增 Citation Store、检索或 Evaluation。

## 数据流和限制

冻结 Snapshot → 原授权 L3 → 原 Parent Merge、Rerank → 原 Grader/路由 → Answer EvidencePack（无编号父块上下文 + 独立编号叶子）→ 原 Trace/SSE/历史/审计。

- `_citation_leaves` 是内部载体，公开 Trace 不包含它；每父块最多 32 个，正文 UTF-8 合计 16 KiB。恢复原 64 Chunk/256 KiB 上限不变。
- `citation_leaves` 检查 Tenant、KB、Document、Version、Index、section、filename、ACL 相等，真实 matched source 的行位置不变；正文 SHA-256 等于叶子 content_hash。同一身份哈希冲突拒绝。
- 使用 S2 已有 `Sheet：…；首列：值；…` 的首列标识，查询完整命中标识时缩小候选。不硬编码 NX、列名、参考答案或 Gold，不从生成答案数字反查行。
- 同标识多个 Sheet、版本描述、行、拆片全部保留；不假定唯一、不判断业务最新版本。不能识别标识时保留真实叶子候选。
- 这是候选归因，不是事实验证。模型仍需理解字段、单位、版本、日期；不得用叶子编号为父块中任意事实背书。
- 叶子正文缺失/损坏/不完整或来源截断，明确保留父块级引用和降级计数，不虚构行号；权限/身份冲突拒绝。
- 先按原预算选择可引用单元，上下文使用剩余预算；不以隐藏所有来源提升 Precision。Grader 不传 question，保持原上下文与路由语义。

## 正式契约与恢复

`RetrievedChunk` 字段、Event envelope、前端类型未变。`RagTraceFields.citations_belong_to_selected_evidence` 接受原检索单元，或同 Document/Version/Index/section/file 父块已匹配的真实 L3。运行时先验证正文/hash；公开来源校验不声称事实正确。

`pipeline._copy_jsonable_doc`、`checkpoint_runner._compact_resume_result` 保留有界授权正文；暂停状态仍去掉正文。恢复仍用原 Snapshot 可用性检查，不切 current。旧 Trace/消息兼容，缺载体则父块降级。

正式 Worker 的 Answer、Judge 展示与编号导出复用同一确定性 pack。现有 `retrieved_identities` JSON 用 `retrieval_context=true/false` 区分原候选与派生叶子。Document Recall 仍来自原 Observation；Provenance Coverage 分母仍是原检索 XLSX 单元。

## 成本

新增数据库/Milvus/模型请求均为零。Worker identity JSON 记录一次实际审计重组 `selection_ms`、上下文/总字符、降级数；不是整个检索/生成阶段计时。Provider 调用计数测试检查 N+1。最终运行指标、Snapshot、Source Fingerprint 见 `s4a-evaluation.md` 和忽略目录运行资产。
