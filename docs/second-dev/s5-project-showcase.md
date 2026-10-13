# S5：项目展示与面试 Demo

日期：2026-10-13。展示定位：在开源 SuperMew 上实现 Excel 行级可追溯 RAG，而非从零实现完整平台。本轮按 ponytail 复用已有源码、报告和真实案例，不增加业务抽象或展示页面。

## 1. 一句话与业务背景

**SuperMew-TraceRAG：面向企业 Excel 参数、库存与售后政策问答，将真实文档版本和物理行贯穿索引、Evidence、引用 UI，并以原生评测保留质量边界。**

虚构企业星云智能科技有限公司（Nebula Industrial）管理工业传感器、控制器和智能网关。产品参数、价格、库存、维修可通过 NX-001～NX-200 关联；不同硬件版本与保修政策有明确生效条件。普通文本化 Excel 的问题不只是“有没有表头”，而是叶子是否可靠绑定表头、行值、单位以及物理来源。

建议开场 30 秒：平台基础来自上游；我负责表格表示与证据链的增量开发。能展示真实 Sheet/Row 引用，也能解释为什么文档召回和正确引用身份仍不足以保证答案完整。冻结结果不是全绿，保留失败是项目的一部分。

## 2. 贡献边界

上游基点 `e2ebabe` 已有 FastAPI、模型控制面、LangGraph、三级 Chunk、Milvus Hybrid/RRF、Parent Merge/Rerank、Document Version/CAS、Worker、EvidencePack、SSE/Vue、Evaluation。二开集中在：

- 唯一事实源、确定性生成器与原生 80 Case 适配。
- XLSX 多 Sheet/行语义、动态来源写入和发布前读回。
- 来源 Contract、冻结 Snapshot 恢复、叶子正文身份校验、父块/引用分离。
- Vue 入选证据定位与历史一致性、引用编号审计。
- 原节点内跨文档独立事实规划和受控缺证补充。
- DeepSeek 结构化策略、Rerank 协议兼容与真实评测复盘。

完整文件级范围在 [最终总结](s5-final-summary.md#完整技术改动清单)，不要将“参与扩展原生 Evaluation”讲成“自研第二套评测框架”。

## 3. 架构与流程讲解

[README 的两幅 Mermaid](../../README.md#技术架构) 分别展示正式索引与提问链路，作为唯一对外架构图，不重复维护第二幅不同拓扑。

入库：上传 → durable Index Job → Worker → XLSX 行语义/三级块 → PostgreSQL 父块 + Milvus 叶子/来源 → Manifest 和来源读回 → CAS 发布。

问答：durable Run / Model Snapshot → Fast 规划 → 冻结版本 Scope → Dense/BM25/RRF → Parent Merge → Rerank → Grader/一次补充 → EvidencePack → Answer/引用审计 → Event/历史 → Vue。

关键说明：Redis 是缓存/通知；PostgreSQL 是持久事实源。来源由真实叶子给出，不从模型字符串或父块正文推造身份；Rerank 排在 Parent Merge 之后。Evaluation Worker 复用图，但不等于浏览器 SSE/HITL 全链路验收。

## 4. 四个最有价值的技术难点

### 难点一：行语义与版本化索引

**原始问题**：旧 XLSX 文本块有时含表头，但叶子未必保持列值关系；没有可靠 Sheet/Row，不应凭 filename/page 构造行来源。

**方案**：已有 openpyxl 逐行字段绑定；物理行不重编号；长行分片重复首列标识；L1/L2 不跨 Sheet；沿用版本化 Chunk ID、正文 hash 和 Worker/CAS。动态四字段单独写后读回，不能假称 Manifest 已覆盖来源 hash。

**源码**：[excel_parser.py](../../backend/indexing/excel_parser.py) `parse_excel_rows`；[document_loader.py](../../backend/indexing/document_loader.py) `_load_excel`；[milvus_writer.py](../../backend/indexing/milvus_writer.py) `verify_provenance`。

**验证**：[parser 测试](../../tests/test_excel_parser.py)、[来源测试](../../tests/test_excel_provenance.py)、[真实 Milvus 集成测试](../../tests/test_excel_milvus_integration.py)、[S2 索引报告](s2-index-provenance.md)。四 Fixture 共 700 叶子，真实 scope/hash/source exact；多 Sheet 单测而非宣称企业 Fixture 都是多 Sheet。测试的 16 维存储向量不冒充真实 bge-m3 效果。

**取舍**：无需 Schema migration，但不支持合并表头、公式、隐藏 Sheet 摄取。不能把“支持 XLSX”概括为任意复杂 Excel 可解析。

### 难点二：父块理解与叶子引用分离

**原始问题**：S3 有行来源却仍将多个命中行聚合为一个父块 Evidence；引用编号合法不保证只引用目标行。

**方案**：保留有界真实 `_citation_leaves` 载体（每父块最多 32、16KiB）；校验 Tenant/KB/Document Version/Index/ACL、叶子 ID 和正文 SHA；父块无编号，可靠叶子独立编号。来源标题与理解上下文计入预算；缺载体时明确父级降级。

**源码**：[utils.py](../../backend/rag/utils.py) `_merge_to_parent_level / dedupe_documents`；[evidence.py](../../backend/rag/evidence.py) `citation_leaves / pack_evidence / audit_citations`；[knowledge.py](../../backend/tools/knowledge.py) `_render_rag_result`。

**验证**：[归因测试](../../tests/test_evidence_attribution.py)、[引用审计测试](../../tests/test_rag_citation_audit.py)、[S4-A 设计](s4a-evidence-attribution-design.md)。冻结严格行引用 30/33、错行 0、缺行 3；仍不等于逐 Claim entailment。

**取舍**：不增 Citation Store/额外叶子查询/逐行模型调用；身份可信不是语义支持证明。Grader 前缀 Pack 截断目标行的窄范围复现仍未修复。

### 难点三：跨端来源与冻结恢复

**原始问题**：检索来源可能在正式 Trace、Evidence 选择、Checkpoint 或 Vue 投影丢失；候选顺序不是 Answer 编号，恢复不能重新选择最新 current Version。

**方案**：扩展既有 RetrievedChunk/Trace optional 来源，生成 Contract；数字引用映射实际入选 Evidence；有界 Snapshot 持久化与恢复，撤销/清理检查 fail-closed。实时消息最终态和历史消息读同一公开 Trace；不连续命中行按集合呈现。

**源码**：[rag schema](../../backend/schemas/rag.py)、[retrieval.py](../../backend/documents/retrieval.py)、[checkpoint_runner.py](../../backend/rag/checkpoint_runner.py)、[ragSources.ts](../../frontend/src/utils/ragSources.ts)、[References.vue](../../frontend/src/components/Chat/References.vue)。

**验证**：[来源契约测试](../../tests/test_rag_provenance_contract.py)、[前端测试](../../frontend/src/utils/ragSources.spec.ts)、[真实 Vue/SSE/刷新 Smoke](s3-frontend-citations.md)、[ADR-0027](../adr/0027-rag-provenance-and-frozen-resume.md)。

**取舍**：旧已完成消息支持文件级展示；缺 Snapshot 的旧暂停 Checkpoint 不能静默恢复。真实替换/清理并发 HITL 未完整在线演练，不将 fake 契约测试说成真实生产竞态验收。

### 难点四：跨文档缺证诊断与可信评测

**原始问题**：参数和政策可能只命中一份，Planner/Grader 会把缺证和缺用户条件混淆；Provider 回退还会混杂实验结论。

**方案**：原 Fast 规划独立事实；内部 `EvidenceGrade.missing_evidence_query` 指向缺失证据；沿用一次 Rewrite/再检索，确定性保留旧证据合并新证据。兼容模型只修改统一 Adapter；评测沿用 Dataset/Job/Worker，保留 provenance/Gate 与 20-dev/60-frozen 分离。

**源码**：[pipeline.py](../../backend/rag/pipeline.py) `classify_complexity / _resolve_route / rewrite_question_node`；[models.py](../../backend/agent/models.py)；[evaluation runtime](../../backend/evaluation/runtime.py)；[生成器](../../scripts/generate_synthetic_enterprise.py)。

**验证**：[覆盖测试](../../tests/test_rag_cross_document_coverage.py)、[DeepSeek 测试](../../tests/test_deepseek_structured_output.py)、[S4-B](s4b-evaluation.md)、[S4-D](s4d-healthy-rerank-baseline.md)、[S4-E](s4e-final-evaluation.md)。

**取舍**：不无限检索、不强改 NO_KNOWLEDGE/HITL；Document Recall 不证明必要行可见，Judge 均分不叫回答准确率。冻结全必要文档覆盖@5仅39/53，跨文档仅3/15，不能只展示较高@10掩盖Top5缺口。

## 5. 十分钟真实 Demo 路径

本节是**未来演示操作说明**；S5 不启动服务、不新调用模型。先确认模型授权与预算，检查无活动任务后才按 [快速开始](../../README.md#快速开始) 启动既有正式服务。

1. 0–1 分钟：展示上游署名、两幅架构图，说明本人的增强节点。
2. 1–2 分钟：只读查看 manifest 的 12 文件 allowlist、200 产品和 dev/frozen 划分；答案资产不上传。
3. 2–3 分钟：在专用知识库展示 12 READY、真实 Document Version/Index Job；不删共享知识库、不复制历史 Version ID 到新环境。
4. 3–5 分钟：优先回看已有真实 `table_query_003` Chat/SSE：NX-003 库存88台、上海测试仓、2026-10-01；点击引用显示 inventory Sheet 物理第4行，刷新同一 Thread 对照历史来源。S3/S4-D 各自证据不混为同一次 Run。
5. 5–6 分钟：回看健康开发 `cross_document_001`：NX-081、2026-02-01、155W/24月；对照参数与政策身份，说明 Top5 只覆盖一半 Gold。
6. 6–7 分钟：回看 `table_query_001` 版本澄清，解释业务谨慎与自动 Outcome 失败。若有暂停 Run，恢复必须同一 Run/Checkpoint，不新建问题冒充 HITL。
7. 7–9 分钟：展示唯一冻结 Job 摘要，Case Pass、引用和 latency 分别解释；选 `table_query_016` 缺行失败讲预算诊断。
8. 9–10 分钟：展示测试记录、已知风险与下一步，明确 Gate FAIL 和无严格冻结 A/B。

如历史 Run/前端消息已不可用，使用正式脱敏报告与真实 Case 导出摘要，不制造浏览器截图。需要重新现场问答时只选已公开开发题，经另行授权调用；不重复冻结题做“演示调参”。

冻结 `table_query_017` 的135W/200W、第18/38行可用于已有结果展示，不能偷偷重跑当新的独立测试。实际案例口径统一见 [README](../../README.md#实际使用示例)。

## 6. 截图建议与发布条件

已有真实资源记录在忽略的 `.artifacts/synthetic-enterprise/s3/`：`live-citations.png`、`history-citations.png`；报告亦保存真实 SSE/DOM 对照。本轮未复制到公开目录，也没有生成示意界面或伪造答案截图。

| 建议画面             | 应展示                                  | 发布前必须检查                                  |
| -------------------- | --------------------------------------- | ----------------------------------------------- |
| Excel 单题来源卡片   | 型号、单位、真实 Sheet/物理行和选中引用 | 不出现个人账号、私有 URL、Token、浏览器敏感页签 |
| 同一 Thread 历史来源 | 刷新前后入选 Evidence 一致              | 匿名化主体，不能把不同 Run 拼成一致性证明       |
| 跨文档回答           | 参数与售后两份来源及真实答案            | 不裁掉缺证/澄清警告，不用手写答案替换           |
| 版本澄清             | 新旧硬件值、确认版本动作                | 标出原生自动失败，非“全通过”                    |
| Evaluation 摘要      | 60/60执行、40/60 Pass、Gate FAIL、分母  | 隐藏网关/账号/敏感配置，不隐藏失败              |

经用户或资产所有者确认脱敏可公开后，再放 `docs/second-dev/assets/` 并加相对链接；该目录/图片**本轮未创建**。Git ignored 不等于自动安全，公开前要独立审查。

## 7. 成果与限制

唯一冻结指标与定义由 [正式报告](s4e-final-evaluation.md) 维护：

- 12 文档、80 Case；20-dev 与60-frozen互斥；冻结运行60/60，Pass40/60=66.67%，Gate FAIL。
- Doc Recall@5=84.91%、@10=94.34%（n=53）；按最终Chunk截断，非去重文档排名。
- 引用身份合法120/120；严格行集合30/33=90.91%；已导出Excel记录来源139/139。
- P50/P95=7.201/11.947s（n=60，含Judge/失败）；1 retrieval Provider Timeout。
- Judge correctness0.9610（n=59）为连续分数，不能叫96.1%回答准确率。
- Gold Chunk和Claim不足；冻结Rerank全过程计数/Token/费用未测；无原版冻结同集结果，不称A/B提升。
- Grader打包截断、Outcome分歧、Milvus容器重建恢复和生产SLA仍有缺口。

历史20-dev数据不是冻结对照。开发期Rerank31阶段全部成功的事实只能归属S4-D，不可扩大为冻结60题成功率。

## 8. 岗位讲解重点

**Python 后端**：先讲版本身份、发布前跨存储核验、动态元数据和fail-closed；再讲复用Worker/事务/CAS、不增Schema的取舍、Checkpoint冻结恢复、公开Contract与测试。明确这些基础设施上游已有，本人负责接入和不变量验证。

**AI 应用**：先讲行语义、Parent理解与Leaf引用、跨文档必要事实覆盖；再讲统一结构化Adapter、Evidence预算、原生评测与失败分析。能解释合法引用、Judge均分、DocRecall、严格行匹配为何是不同指标，比单报漂亮“准确率”更有价值。

完整可用简历草稿见 [最终总结](s5-final-summary.md#简历项目描述草稿)。
