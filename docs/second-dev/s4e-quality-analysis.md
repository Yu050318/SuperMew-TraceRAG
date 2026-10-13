# S4-E：冻结测试集质量复盘

日期：2026-10-13。分析在唯一正式 Job `rag_eval_64d66d2ec2aa4d2bb047e1df01f0d7b6` 完成之后开展。原生统计与配置的唯一主报告是 [最终评测](s4e-final-evaluation.md)；本文件解释真实失败，不修改自动结果。没有因冻结题复盘修改任何执行代码、数据、Prompt、Gate 或模型配置。

## 1. 自动失败与业务解释

60 题原生通过 40、失败 20：简单事实 1、表格 1、跨文档 3、无答案 7、版本政策 8。全部 20 个失败均含 Outcome 不符；其中还可能有 Provider、HITL、Judge 失败，不能重复求和成更多失败 Case。

| 现象 | 观测与解释 |
| --- | --- |
| Provider 可靠性 | simple_fact_012 超时，无最终答案；是真实失败，不是知识库无答案 |
| 表格可见证据不足 | table_query_016 初始命中参数 Parent，最终被 Clarify 清空；不是从未命中文档 |
| 跨文档漏事实 | cross_document_010/014 没有回答协议，最终缺参数表，Doc Recall@10=0.5 |
| 文本正确但状态不符 | cross_document_011 与全部 8 个版本/政策 Case 回答主要标准事实正确，仍为 INSUFFICIENT_EVIDENCE |
| 无答案边界 | 6 个 Clarify，1 个 route=answer / Outcome=ANSWERABLE；均不满足原 NO_KNOWLEDGE 预期 |

无答案 7 条文本没有把相似型号的功率直接冒充不存在型号的功率；这一人工观察不等于自动拒答通过、完整无幻觉证明或二元准确率。no_answer_005 还把检索片段的覆盖描述为产品表覆盖范围，可能过度概括，需要保留措辞风险。no_answer_006 明确说不能用 NX-096 推断 NX-906，但自动 Outcome 仍是 ANSWERABLE；业务文本与正式状态必须分别解释。

版本/政策回答正确识别生效日期和 2.0 参数，部分明确拒绝编造政策调整/技术变更的原因，符合谨慎业务回答。但 Grade/Synthesis 仍可能因为某一子问题缺证据保留 partial Outcome。原生检查保持失败，不以人工认可改写 Pass。完整 sub_traces 未持久化，不能指定某次 Planner/Grader 的具体决策为已证明根因。

## 2. 九个代表性失败 Case

完整问题、参考答案、真实答案、Judge、检查项、初始/最终排名、叶子身份与行集合在 `.artifacts/synthetic-enterprise/s4e/` 的 `case-review.json`、`persistent-cases.json`、`citation-audit.json`。下列实际回答是摘录/概括，未使用临时 Judge。

| Case / 用户问题 | 预期 | 实际与关键证据 | 失败解释 / 后续检查点 |
| --- | --- | --- | --- |
| simple_fact_012：NX-052 的复位方法？ | 断电 30 秒后上电 | 答案为空，PROVIDER_TIMEOUT/retrieval，10918ms，最终 Chunk 0 | Provider 故障；`RagEvaluationRuntime.execute_case` 只保存 retrieval 分类，不能把它归为 NO_KNOWLEDGE 或断言 Snapshot 已定位 |
| table_query_016：NX-016 与 NX-036 的功率和大小？ | 175 W / 140 W，前者大 | “还缺少…NX-016 的额定功率数值”；初始 rank1/2 为参数 Parent `p0::l2::0/2`，最终 Chunk 0 | 初始文档命中，Grader 可见范围与 Clarify 清空证据是重点；无引用，缺第 17/37 行 |
| cross_document_010：NX-090 的协议与安装要求？ | MQTT；断电接线、DIN 导轨 | 回答安装要求，声称协议证据不足；引用 manual/selection `p91::l3::0`，最终无参数表；初始参数 Parent `p0::l2::6` 已在 rank1 | 真正漏掉必要事实；rewrite=true，最终文档召回 0.5，缺参数第 91 行。需区分 Parent 打包截断、Rewrite 与最终证据流失 |
| cross_document_014：NX-094 的协议与安装要求？ | Modbus RTU；同上安装要求 | 回答安装要求但不给协议；引用 manual/selection `p95::l3::0`；初始参数 Root `p0::l1::3` rank1，最终无参数表 | 与上项类似，缺第 95 行；不能称为从未命中参数文档 |
| cross_document_011：2026-02-01 购买 NX-091 的功率/保修？ | 60 W / 24 个月 | 真实答案给出 60 W [5]、24 个月 [1]；参数叶子 `p0::l3::90` / 第 92 行，售后 `p3::l3::0` | Doc Recall=1、行引用通过、Judge 检查通过，仅 Outcome 错；未来核对 partial 子问题状态，不在本轮改规则 |
| no_answer_004：NX-904 的额定功率？ | 知识库未提供，NO_KNOWLEDGE | “没有 NX-904…请确认…型号”；Clarify / INSUFFICIENT_EVIDENCE | 可合理解释为防止型号误输入，但 hitl/outcome 不满足原契约；不自动改判 |
| no_answer_006：NX-906 的额定功率？ | 同上拒答 | “无法…确定…相近 NX-096 为 175 W [1]…不能据此推断”；参数真实叶子 `p0::l3::95` / 第 97 行 | 文本未把相似型号功率冒用，Outcome 却为 ANSWERABLE，且 context_relevance 检查失败；引用合法不等于目标型号证据正确 |
| version_policy_003：NX-003 公告/参数不同，硬件 2.0 取何值？ | 120 W；旧 1.0 为 130 W，按日期/版本区分 | 真实答案正确使用 120 W，引用公告 `p4::l3::0`、参数叶子 `p0::l3::2` / 第 4 行，说明不能推断技术原因 | Doc Recall=1、行通过，Judge 检查通过；仅 Outcome=INSUFFICIENT_EVIDENCE。可能为复杂问题 partial 聚合，缺 sub_trace 不能进一步定因 |
| version_policy_006：2026-06-01 购买保修多久，旧政策为何不同？ | 24 个月；旧 2025 政策 12 个月 | 正确给出新旧日期与周期，并说明证据不含变更原因；引用售后 `p2/p3`、保修 `p202` 的 l3 叶子 | 自动失败仅 Outcome；谨慎解释政策原因与事实判断不应混为“错误答案” |

表中 `p…::l…` 是真实 Chunk ID 的展示后缀，不是构造的新身份。参数 Version 为 `docver_0c8b6bd223db4f8ab4c6637bea269583`，manual 为 `docver_6bac446c19bf4571bb2fec466216b074`，selection 为 `docver_5c585861bd5d4bf68ab9ce8cc0e632df`，release 为 `docver_1f639e93301d48b884d112d99823be42`，售后为 `docver_87b8e52aad484ed9bde66d68c472ff92`，保修为 `docver_0b51166dee4642a286d7c3087454b6e2`；完整 ID 在原生导出，不把后缀当 Gold Chunk。

正例对照 table_query_017：135 W / 200 W，正确判断 NX-037 更大，精确引用第 18/38 行，两叶子 ID 后缀 `p0::l3::16/36`，严格行通过。表头/数值/单位及来源在这个真实样本完整，不意味着所有表格题全通过。

## 3. Parent 与 Grader 打包的真实边界

使用 `diagnosing-bugs` 收窄证据链，而不是把最终空结果直接归因于检索器。`inspect_parent_evidence.py` 是忽略目录中的测试后只读诊断：通过 ORM 读取实际初始命中的 Parent，校验正文 SHA 与存储哈希，复用正式 `pack_evidence` 和当前 `grader_max_document_character_budget=1200`，不执行 RAG 或模型。

| Case | 初始真实 Chunk 后缀 | 正文字符数 | 目标型号 offset | 正式单文档 Pack 是否保留型号 |
| --- | --- | ---: | ---: | --- |
| table_query_016 | product_specs.xlsx::p0::l2::0 | 1572 | NX-016：1399 | 否 |
| table_query_016 | product_specs.xlsx::p0::l2::2 | 1566 | NX-036：937 | 是 |
| cross_document_010 | product_specs.xlsx::p0::l2::6 | 1567 | NX-090：1218 | 否 |
| cross_document_014 | product_specs.xlsx::p0::l1::3 | 2311 | NX-094：1582 | 否 |

offset 为 Python 字符索引，不是物理 Excel 行号。三个目标在当前真实 Parent 正文中存在，但生产单文档 Pack 截断后不可见，输出见 `parent-evidence-diagnostic.json`。这是实际窄范围复现，不是凭设计推测。

命令从仓库根运行：

```text
wsl -d Ubuntu-24.04 --cd / /home/lenovo/.local/share/supermew/venv/bin/python /mnt/d/develop/项目/企业级rag平台/SuperMew/.artifacts/synthetic-enterprise/s4e/inspect_parent_evidence.py
wsl -d Ubuntu-24.04 --cd / /home/lenovo/.local/share/supermew/venv/bin/python /mnt/d/develop/项目/企业级rag平台/SuperMew/.artifacts/synthetic-enterprise/s4e/inspect_parent_evidence.py --assert-target-preserved
```

第一条退出 0、约 3.22s；第二条约 3.38s，**退出 1（预期红断言）**：NX-016 在正文 offset1399，但未保留在正式 1200 字符单文档 Pack。它是诊断复现，不是新增后端 pytest 的通过/失败数量；没有修复后绿断言，也不能宣布缺陷已解决。

`pipeline._pack_grader_docs` 调用 pack_evidence 时不传 question，而当前 `grade_documents_node` 在 clarify/scope_select 后清空 docs。这与 table_query_016 的初始 8 Chunk / 最终 0 / Clarify 现象一致。完整运行时 Prompt/sub_trace 已丢失，单文档复核不能重建每次完整 Prompt 或证明截断是唯一原因；候选 leaf/Parent 选择、总预算和 Grader 判断仍需新数据的专门集成测试。

本轮按用户冻结约束只到复现/定位，跳过修复和改参阶段。**不能通过提高预算或改 Outcome 后重跑这 60 题来冒称独立测试结果**。

## 4. 引用与跨文档限制

已有来源链在已导出证据上保持：702 个身份匹配、139 个 Excel retrieval_context 记录来源完整；33 个 Gold 行 Case 中 30 个严格通过，未观测到过宽引用或 Parent 合并后来源不可恢复。但三条缺行失败仍保留，文档命中不保证具体行可见。

跨文档全部必要文档@5 仅 3/15，@10 为 13/15；更后面的补充证据有帮助，但两条协议事实最终丢失。当前不能仅靠 Doc Recall 证明 Claim Coverage，也不能以来源完整证明答案完整。59 个 Judge 的平均分对超时缺样本及部分回答的 0.5 阈值要明确交代。

版本类 8/8 的文档召回、3/3 的严格行引用和较高 Judge，与自动 0/8 Pass 并不矛盾；它们衡量不同层次。无答案文本的安全表述也不能替代 NO_KNOWLEDGE 状态契约。

## 5. 可靠性与未完成测量

已观测 1 次 retrieval-stage PROVIDER_TIMEOUT，保留分母，不将 Rerank 修复等同于 Snapshot 修复。完整阶段时序缺失，因此无法把本次超时进一步定位到 Snapshot；历史独立风险仍在。

Rerank fixture 成功 486ms、无回退，正式运行配置相同，最终 score/排名留存；但原生持久导出不保存 Stage 计数、before/after 完整排名和耗时，无法报告 60 题全程成功/回退次数或无 HTTP 400 保证。实际调用数/Token/账单未测。为保持无实验包装器和正式 Worker，本轮没有临时补遥测后再跑一次。

本轮没有新 API/SSE/历史消息浏览器 Smoke；只能报告离线测试对相关契约的覆盖，不能把 Evaluation Worker 等同于完整 Chat/SSE/Checkpoint 端到端验收。Milvus 当前环境映射在容器重建时会丢失，冷启动未重新测试；工程风险详见准备报告第 10 节。

## 6. 后续方向与真实源码位置（仅建议）

| 方向 | 当前正式位置 | 未来验证要求 |
| --- | --- | --- |
| Grader 叶子优先、目标行保留 | `backend/rag/pipeline.py::_pack_grader_docs`、`grade_documents_node`；`backend/rag/evidence.py::pack_evidence` | 新合成边界 fixture 同时保留两个目标；预算、Parent 上下文与行来源均可断言，不能只加大所有文本预算 |
| Parent/Leaf 证据流失诊断 | `backend/rag/utils.py::_merge_to_parent_level`、`_auto_merge_candidates`、`retrieve_documents` | 区分 Leaf 命中、Parent 合并、Grader 可见行、Rewrite 后最终行；不能从父正文包含目标推断命中叶子就是目标 |
| 多事实与 partial 状态解释 | `backend/rag/pipeline.py::_resolve_route`、`synthesis`；`backend/rag/outcomes.py` | 先设计业务语义/评测契约；不得为 Gate 提升强改 NO_KNOWLEDGE/HITL；保留已有用户认可的谨慎回答 |
| Provider/Snapshot 时序 | `backend/rag/utils.py::resolve_retrieval_snapshot`；`backend/evaluation/runtime.py::RagEvaluationRuntime.execute_case` | 有界真实时序与错误来源；新专门可靠性测试，不伪造知识缺失 |
| 原生遥测持久化 | `backend/evaluation/runtime.py::_execution_result`、`_retrieved_identities`；`backend/evaluation/worker.py::_report_metadata`；`backend/rag/reranking.py::RerankStage` | 沿正式 Evaluation 设计兼容扩展，保存公开 Trace 和请求计数，不记录私有推理/Secret，不新建并行评测框架 |
| 冷启动与离线门禁 | Milvus 部署映射、正式 launcher、`start.sh`、ModelRegistry 测试环境隔离 | 不重写历史 fingerprint；稳定支持声明的依赖和启动入口，补全未运行的发布门禁 |

## 7. README/简历与 S5 建议

可客观使用：固定 seed 的 12 文档/80 问答、20-dev/60-frozen 分离；一次原生 60-test 的 Doc Recall@5=84.91% / @10=94.34%（n=53）；严格行引用 30/33=90.91%；139/139 已检索 Excel 记录来源完整；P50/P95=7.201/11.947s（n=60，含 Judge/失败）。必须同时交代 Case Pass 40/60、Gate 未通过和 Provider 超时，不能写成“回答准确率 96.1%”“引用事实准确率 100%”或“冻结集 A/B 提升”。本地 CPU/单次样本延迟不是并发 SLA。

工程能力已有事实支撑，冻结基线与质量缺口已可交付；**有条件具备进入 S5 工程化收尾的依据，不具备宣称生产质量达标的依据**。S5 应优先处理遥测、部署恢复、测试环境/门禁和说明文档；算法改善需另行授权、重新界定评测数据的独立性。冻结 60 题现在已使用，未来若据此优化，不能再次称为 untouched test set。

本轮只修改三份 S4-E 报告，运行脚本/产物置于忽略的 `.artifacts/`；不改生产代码或业务 Schema，不覆盖 S4-B/S4-D，不保存凭据、不 Commit/Push/Merge，未进入 S5。
