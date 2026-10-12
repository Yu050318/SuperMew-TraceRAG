# S4-B：跨文档证据缺口诊断

日期：2026-10-12。状态：授权后真实诊断、前后3-dev Smoke、原生20-dev Worker Job与来源审计已执行。三个目标Case完整回答，002/004正例保持通过；全量Gate仍失败，另有Snapshot阶段Provider超时。没有把局部目标通过写成所有门禁通过。最终数据见 [评测](s4b-evaluation.md)。

## 原生历史证据

只读 S4-A Job `rag_eval_3f17a6b0366d43bb817689e6906479ec` 的 Case/Observation/Report；独立导出到 `.artifacts/synthetic-enterprise/s4b/historical-cross-cases.json`。未重跑 A、未覆盖历史资产。SHA-256 初始凭据为 `before.json`，只读核验确认历史文件相等。

| Case | 必需事实 | S4-A 实际行为 | 耗时 ms |
| --- | --- | --- | ---: |
| cross_document_001 | NX-081 功率 + 购买日期适用保修 | simple；155 W 可确认、没有保修期限；clarify/INSUFFICIENT_EVIDENCE | 6842 |
| cross_document_003 | NX-083 功率 + 购买日期适用保修 | simple；165 W 可确认、没有保修期限；clarify/INSUFFICIENT_EVIDENCE | 7276 |
| cross_document_005 | NX-085 功率 + 购买日期适用保修 | simple；10 W 可确认、没有保修期限；clarify/INSUFFICIENT_EVIDENCE | 6752 |
| cross_document_002 | NX-082 通信 + 安装 | complex；Modbus RTU + 断电接线/DIN 导轨，answer/ANSWERABLE | 9102 |
| cross_document_004 | NX-084 通信 + 安装 | complex；MQTT + 断电接线/DIN 导轨，answer/ANSWERABLE | 8731 |

前三题购买日期均为 2026-02-01；不是用户未提供日期。初始 Top8 有产品参数、技术规范、选型等产品片段，没有 `aftersales_policy.html`；最终 Observation 证据为空、rewrite_performed=false。后两题真实通过，必须在新 Live 轮复核，不能用单元测试冒充复测。

## 源码路径与可确定根因

`classify_complexity` → simple → `retrieve_initial` → `grade_documents_node` → `_resolve_route` → `await_hitl`。原 `_resolve_route` 对 missing_slot/missing_slots 优先澄清，早于 partial 的一次 rewrite；澄清分支清空 docs/context/retrieved_chunks。它可以把缺少来源的证据问题当成用户条件问题，跳过现有检索改写机会。

三个问题含“和”，本地 `_simple_question_fast_path_reason` 已排除快速路径；它们的 simple 来自 Fast 模型分类，不是本地“多少”规则短路。现有规划提示允许参数查询被归为简单，未强调同一实体也可有多个独立事实需求。历史 Observation 不保存 Fast 原始理由，不能推测其私有推理。

已观测：A（未分解两个需求）、最终 TopK 的政策缺口，以及 E/HITL 路径清空证据。尚未确定 B/C：历史没有独立 Dense、BM25、原始 RRF、merge 前后、Rerank 前完整候选名单，不能断言政策“从来没有召回”。Milvus 原生 hybrid API 将 Dense/BM25 经服务器 RRF 融合返回，当前正式 Adapter 不暴露两路独立名单；若后续捕获融合名单，仍不能冒称独立两路观测。

D 不是这三题已经证实的根因：它们没有进入 Answer EvidencePack。原 Grader 使用 4800 字符/每块1200的投影；缺少当次具体裁剪正文记录，不能据最终空集认定预算截断。Synthesis 未执行，因此也不能把这三题归因于合成丢失。

F/语料核查：规则在 `upload_corpus/aftersales_policy.html`，明确写有 2025 年购买保修12个月、2026-01-01起购买保修24个月；`warranty_rules.html` 的产品段落是每6个月检查接线端子，末尾只指示按购买日期适用新政策。命中后者不等于获得期限证据。Gold 正确指向售后政策，不能改成维护文档来提高 Recall。上述数字仅是离线语料事实，不进入生产硬编码。

## 可复现离线故障

`python -m pytest tests/test_rag_cross_document_coverage.py -q` 首次实际为 1 failed、2 passed：参数有证据、Grader 判断 partial/clarify，已提供独立缺失证据查询，但原图立即 needs_clarification。测试使用生产图、离线 FakeStructuredModel 和授权 Retriever seam；不是一次真实模型评测。补丁后同一图可使用一次重检并保留原事实。

## 索引与隔离

只读运行 `.artifacts/synthetic-enterprise/s4b/preflight.py`，复用 S1.5 `inspect_index.py`：数据库迁移 current、12/12 READY，Milvus 与 PostgreSQL IDs/count/content_hash 精确等于 Manifest；Index ID 仍为 `6832df8a828ce611f321023be9e92ba78c377e14609ef36d9a789c7118ed9954`。未上传、重建或清理文档；授权后仅重设account_id=3用于正式登录，未改权限、所有权或其他账号。真实身份在 s4b/index-identities.json；没有人为生成身份。

## B：真实分阶段观测

忽略目录中的 `observe.py` 仅包装原CLI/Worker所调用的原函数，参数/返回值/异常保持不变。按原生串行Case结束时间与子问题query digest关联阶段，线程记录避免并行子查询串号；没有全局“当前Case”业务状态。采集公开身份、计数、时间、结构化公开决策，不采集reason、CoT、正文、endpoint或凭据。源码与包装器单独SHA在manifest中，完整阶段在stage-analysis.json。

最终Job `rag_eval_fedf90faa60c4754817def69d6d43c7e` 中三个问题均规划为complex，分别生成参数/购买日期保修两个子问题，购买日期未丢失。两个子Grader均sufficient/answer，synthesis形成ANSWERABLE。没有扩大top_k，三题均没有二次补检；Live提升不能归功于尚未在线触发的补检分支。

| Case/子问题 | 售后政策叶子RRF排名 | Auto-merge后/Rerank前 | Rerank回退后Top8 | 含义 |
| --- | --- | --- | --- | --- |
| 001 参数 | 19、21 | 19、20 | 不在Top8 | B轮确实召回低排政策，但TopK丢失 |
| 001 购买日期保修 | 1、3 | 1、3 | 1、3 | 独立事实查询把政策保留到Grader |
| 003 参数 | 20、22 | 20、22 | 不在Top8 | B轮低排名到TopK裁剪，不是父块吞掉政策 |
| 003 购买日期保修 | 1、3 | 1、3 | 1、3 | 政策完整入选 |
| 005 参数（这轮子问题没有日期） | Top30未出现 | 未出现 | 未出现 | 不能泛称所有查询都会召回政策 |
| 005 购买日期保修 | 1、3 | 1、3 | 1、3 | 独立带日期需求恢复政策 |

以上排名是**B实际子问题**，不是缺失的A原始两路排名。Dense/BM25独立候选仍未暴露；服务器RRF列表不冒充两路列表。30次B Rerank阶段全部PROVIDER_REQUEST_INVALID回退，排序保留原融合/merge顺序，没有成功的Rerank结果或阈值过滤可归因。历史网关连通性已确认HTTP400；本轮有界元数据没有独立http_status，不能只由typed code重新证明每次HTTP状态。

因此A/E是历史直接证据；C在B参数子检索中实际观察到，独立政策查询解决所需来源的TopK缺口。不能声称已经证明A原始Query在Dense/BM25/融合的确切丢失位置。F被语料明确规则排除为这三题的全局事实缺失，但具体日期/产品不适用或缺证据问题仍必须澄清。

## 三个目标Case的最终答案、引用与保留

原始问题依次为：

- 001：“2026-02-01 购买的 NX-081 额定功率和保修期分别是多少？”
- 003：“2026-02-01 购买的 NX-083 额定功率和保修期分别是多少？”
- 005：“2026-02-01 购买的 NX-085 额定功率和保修期分别是多少？”

三者预期均为型号功率与购买日期适用的期限，两事实必须分别有来源；不能从型号参数推导保修。

| Case | B实际最终答案关键内容 | 数字引用→真实来源 | 入选/耗时 | 结论 |
| --- | --- | --- | --- | --- |
| 001 | 155 W；2026-02-01适用2026-01-01起政策，24个月 | [3]参数Sheet“产品参数”物理82行；[9]售后政策 | 13个Pack证据；9610ms；2次检索工作耗时合计2154ms | 两必需事实完整，有独立来源 |
| 003 | 165 W；明确购买日期适用新政策，24个月 | [3]参数84行；[9]售后政策，[15]保修规则指向新政策 | 15个Pack证据；10731ms；检索合计3720ms | 两事实完整，不能仅凭[15]维护规则支持期限 |
| 005 | 10 W；购买日期归属2026-01-01起，24个月 | [1]参数86行；[26]售后政策，[30]保修规则辅助 | 31个Pack证据；9059ms；检索合计2185ms | 两事实完整，不把父块所有行作为引用目标 |

共同真实参数Version为 `docver_0c8b6bd223db4f8ab4c6637bea269583`，三个参数叶子末段分别 `product_specs.xlsx::p0::l3::80/82/84`，不是把物理行号直接编成Chunk ID。售后政策Document为 `doc_538e26763b864e09823c4ea3dc099d05`，新政策叶子完整ID为 `docver_87b8e52aad484ed9bde66d68c472ff92::aftersales_policy.html::p3::l3::0`，原12个月政策为同Version的p2叶子。真实完整ID/hash逐项在原生Case/index-manifest资产中核验，本文仅缩写参数末段用于阅读。

5个跨文档Case的全部Gold文档都实际入选Pack，5题10个必需事实人工核对最终答案/引用/固定合成语料后没有缺失；此局部结果不等于正式全量Claim指标。synthesis后仍按原确定性去重，保留真实子来源；5题Top5全Gold覆盖0/5而Top10为5/5，说明完整回答与全局前5排序不是同一指标。Answer Pack最大11929/12000字符，政策关键事实没有被预算省略；这不证明所有未来多事实查询都不会截断。

002继续回答Modbus RTU+断电接线/DIN导轨，[2]参数83行/[6]使用说明，8723ms；004继续回答MQTT+相同安装条件，[2]参数85行/[9]使用说明，7924ms。两正例native Case仍通过，五题精准行集合均与Gold相等。原无答案与普通版本Outcome策略没有本轮优化，详见评测完整20题表。

## 联调暴露的独立合成错误

前两轮持久Job中断，不是“补检没有找到政策”。第二轮保留了 `matched sources must belong to a merged parent` 的Pydantic错误，堆栈为synthesis→_format_docs→pack_evidence。原 `utils.dedupe_documents` 对重复L3也附加父块 `matched_leaf_sources`，同一叶子同时被两个子检索命中时触发。最小直接去重→正式来源Schema→Pack回归稳定变红；限定父块分支后，最终完整Job不再发生该ValidationError。没有改变Schema、剥离真实叶子来源、吞异常或换评测框架。

最终table_query_003为另一个独立故障：Snapshot解析阶段PROVIDER_TIMEOUT，未进入Retriever/Grader；记录为真实失败，不替换为此前成功Smoke。不能把它归为政策不足、NO_KNOWLEDGE、行来源错引，也不能凭一次超时推断补丁因果。该可用性失败与全量Gate未通过保留在阶段验收结论中。
