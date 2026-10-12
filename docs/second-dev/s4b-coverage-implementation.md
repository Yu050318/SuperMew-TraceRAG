# S4-B：受控证据规划、补检与来源保持

## 修改范围

本轮生产改动为 `backend/rag/pipeline.py` 和 `backend/rag/utils.py` 中现有去重函数的一处来源类型边界，没有改 Graph 节点/边、召回/排序算法、Rerank 协议、数据库/Milvus Schema、模型客户端、Evaluation Contract、Excel Parser、前端、Gold 或 Gate。保留原有脏工作区中的 S1.5/S2/S3/S4-A 变更，没有 Commit/Push/Merge。

| seam | 改动 |
| --- | --- |
| `_explicit_multi_fact_question` | 保守识别“分别”加并列连接词，仅约束显式多事实路径；普通查询/版本比较仍走原策略 |
| `classify_complexity` | 上述路径补充独立事实规划说明；原 ComplexityResult 和2–4子问题上限不变，不强制伪造模型规划 |
| `EvidenceGrade` | 内部增加300字符 `missing_evidence_query`，不是公开 API 字段 |
| `grade_documents_node` | 多事实路径区分用户缺条件与缺检索证据；普通路径忽略意外补检建议；保持 Pydantic 校验 |
| `_resolve_route` | 真正 missing_slot/multiple_candidates 仍优先澄清；用户条件明确且 partial + 缺失证据查询时复用一次 rewrite，耗尽后澄清 |
| `rewrite_question_node` | 使用 Grader 已产出的独立查询，作为既有 step_back 请求；不额外调用 Fast，不把虚构答案当证据 |
| `retrieve_rewritten` | 仅补检路径按轮转合并原事实与新结果，用原 dedupe、64项上限和相同 Grader/Answer预算复评；普通 Step-back/HyDE 原行为不变 |
| `rag_sub_agent` | 在原 retrieve→grade 内允许上述同一个一次性补检/复评，不建第二 Runner |
| `_fanout_sub_questions` | 显式继承原 RetrievalSnapshot、原问题；同 Tenant/Model Snapshot 与 Retriever过滤仍生效 |
| `utils.dedupe_documents` | 只有 L1/L2 父块合并 `matched_leaf_sources`；重复 L3 保持直接行来源，不把叶子转换为父块元数据 |

采用 ponytail 复用原 rewrite/regrade seam，不增加配置框架、第二检索器或业务数据库；diagnosing-bugs 的失败回归先实际变红，再修复。暂不根据文件名判定业务充分性，不硬编码型号、日期或保修答案。

## 预算与错误

每路径最多一次补检；简单多事实问题最多初检+补检两次，复杂问题最多4个子问题、每个最多两次。共享 Run 绝对 deadline/cancellation；基础 top_k=8、candidate_k=30、Grader4800/每块1200、Answer12000字符代理预算保持不变。字符不是精确 Token。

补检增加一次 Embedding/授权检索/可选 Rerank/Grader复评，使用原 ProviderExecutor 重试所有权；没有额外 Fast 调用。Rerank失败只保留原回退语义，不自动声明完整覆盖。Timeout/429/400等 typed error 不转为健康空结果；子问题错误仍交给原 synthesis 的 partial/coverage_gap_codes，全部失败传播异常。

第一次支持的事实在重检后不被替换为空；新结果轮转排在前部，减少原证据独占 Grader预算。该策略不证明某一事实在最终 Answer Pack 中仍完整保留，必须实测。补检健康为空仍保留旧事实送复评，partial不得自动变 sufficient。

## 自动化验证与限制

新增 `tests/test_rag_cross_document_coverage.py` 15个主用例：缺证据补检成功、日期缺失澄清、一次预算耗尽、完整证据无补检、普通路径兼容、零额外Fast、空补检保留事实、三种Provider故障、query长度、日期/适用范围提示、错误适用政策不自动充分、Snapshot继承、补检证据前置、多意图边界、Rerank回退不覆盖partial。另在 `tests/test_excel_provenance.py` 新增重复叶子去重→正式 RetrievedChunk→EvidencePack 回归，实际先红后绿。

2025/2026用例验证问题日期和约束进入真实 Planner prompt，不声称离线 Fake 验证了真实模型的期限判断。补检前置测试不是 Milvus“低排名政策一定召回”的协议证明。S4-A引用/hash/身份、原生Checkpoint、Provider、Agent/Event、SSE/历史投影由扩大回归覆盖。实际在线22项验收尚未全部完成。

早期测试修正：原普通 partial/无歧义路径本来会 generic rewrite，测试不能误要求 clarify；Provider enum/构造参数按现有 ProviderCode 和 ProviderCallContext 修正。没有吞错误或放宽业务充分性断言。

相关命令与最终结果见 [评测](s4b-evaluation.md)。授权后已用官方 launcher 重启，原 CLI/LiveRagEvalAdapter、正式 API 和持久 Evaluation Worker 实际执行。仅附加 ignored 诊断包装器，原函数参数/结果/异常不变，不构建另一 RAG Runner；函数计时和公开身份有界记录，不记录正文或模型私有推理。包装器单独 SHA 清单不冒充原生 Source fingerprint。

## 真实联调发现的来源去重错误

补丁前两个全量 Job 分别在第15/11题中断。第二次保留的脱敏错误为 `matched sources must belong to a merged parent`，定位为 synthesis→_format_docs→pack_evidence→RetrievedChunk 校验。两个独立事实子问题可命中同一 L3；原去重函数通过 `matched_leaf_sources([leaf, leaf])` 得到直接叶子来源后，把它附加回 L3，违反已有契约。该错误此前就存在于来源去重实现，但本轮更多事实子问题触发了它。

修正保留直接 sheet/row/anchor/hash，不剥离无效输入、不关闭 Pydantic、不吞 ValidationError；父块来源并集仍由原函数负责，扩大回归包含原父块 union/hash/Checkpoint 测试。首次失败的具体字段未捕获，不能把它与第二次错误认定为已逐项证明的同一原因。

中间一次补丁锚点误匹配到父块 merge，导致3项聚焦测试失败；已恢复父块 merge 原代码并将条件限定到 dedupe，最终27文件为337 passed、2项历史failed、28 subtests passed。没有将中间失败隐藏为从未发生，也没有遗留该 NameError。
