# S4-D：健康 Rerank 端到端 Smoke 与只读诊断

日期：2026-10-12。**健康 Rerank 已在正式 LangGraph / Evaluation Worker / Run-SSE 中执行；具备创建新20题开发集基线的技术条件，但尚未获得或启动该轮完整评测。** 本次没有修改生产源码、检索参数、Gate、语料、Schema、Outcome/HITL/规划算法，没有运行冻结60题或创建Git提交。使用 ponytail 的复用原则，沿用正式 launcher、Worker、API、来源校验和引用审计函数；没有创建另一套RAG。

## 1. 配置检查与安全重新加载

先检查 `/proc/<pid>/environ`，仅比较字段是否相等，不输出地址、密钥或Secret hash。旧API **9248**、Indexing Worker **9249**、Evaluation Worker **9250** 的 `RERANK_BINDING_HOST` 与新配置不同；模型名称仍相同。此前Health返回200及相同模型名不能证明地址已重新加载。launcher自身在import后加载 `.env`，其initial `/proc/environ` 不一定反映后加变量，判断旧配置以三个实际子进程为准。

确认活动Run（包括waiting_input）、Index Job、Evaluation Job均为0后，仅向已核验的旧launcher **9243** 发SIGTERM，通过原监督器正常关闭。使用原launcher临时给原Evaluation Worker加**只读观察包装**，不改变调用参数、返回结果、状态机、重试或评分。4题Job结束且补充Run完成后，再确认活动工作为0，移除包装，恢复标准入口：

```sh
# Ubuntu-24.04，仓库根，锁定依赖的Python；非全局Python。
/home/lenovo/.local/share/supermew/venv/bin/python -m backend.launcher --no-reload --shutdown-timeout-seconds 30
```

最终launcher **10395**、API **10396**、Index Worker **10397**、Evaluation Worker **10398**，所有Rerank环境字段逐项一致，Health **200**，Index Worker ready、无不兼容fresh Worker；Evaluation heartbeat新鲜，无活动Job。没有强行打断活动工作或手动SIGKILL。正常关闭耗时超过诊断脚本25秒等待，第一次恢复检查停止；等待原进程实际退出后启动标准服务。恢复期间两次readiness检查遇到启动窗口的connection refused，最终ready后重新核验成功；它们不是本次Case的Provider失败。

**Rerank配置的正式来源是 `RerankSettings` / `.env` 与进程级ProviderRuntime，不是Model Profile。** 当前Model Control只有Answer/Fast/Grader/Evaluator四角色，不能编造一个Rerank Profile/version：

| 配置 | 有效值 |
| --- | --- |
| Rerank | qwen3.7-text-rerank，enabled=true |
| deadline / score threshold | 5秒 / 0.0 |
| 候选 / 单文档 / 总字符限制 | 30 / 8000 / 60000 |
| 并发 / connections / keepalive | 4 / 20 / 10 |
| circuit threshold / reset | 5 / 30秒 |
| Rerank endpoint identity | SHA-256 `50cf7e65f93208727b24a2f3611d3a873b3b4eeede31a972e19f63b12af3c224`；不保存明文地址 |
| Answer、Grader、Evaluator | deepseek-flash，Profile `model_cca5c8be5c5b42d2b31449a8579aea38`，v1，30秒 |
| Fast | deepseek-v4-pro，Profile `model_489cb92681f943bca8364bde51e8fc3f`，v1，30秒 |

实际Job冻结的Model Catalog hash与S4-B相同：`11164a28bef4fd7b19c61e6764807fea9f18bb55d7a2fc6c0afed28351657469`。Job模型身份与控制面匹配；真实Worker profile与独立新进程解析的profile逐项匹配。已有DashScope request/response envelope适配是本轮开始前就存在的工作区变更，本阶段未实施或修改该补丁。

## 2. 原索引与控制变量

复用已有 `s1.5/inspect_index.py` 做真实PostgreSQL / Milvus核验，不上传任何文件。12/12当前Document Version **READY**，Manifest的parent/vector chunk集合精确匹配，正文hash与Manifest一致，内容SHA与原allowlist一致。Document ID、Version ID、Build Fingerprint、每个Manifest身份与S4-B相同；结束后再次核验。全部运行候选前后身份在这12份已核验Manifest内，没有新增Document Version。详细映射保存在独立目录，不覆盖旧资产。

| 身份 | 本轮值 |
| --- | --- |
| Catalog Index ID | `6832df8a828ce611f321023be9e92ba78c377e14609ef36d9a789c7118ed9954` |
| Corpus | `9c8144131a4d9a93be3621d80cd14691ee858b086f9a8650497dde5459ab049e` |
| 原20题dev Dataset | `7a2fde984e24ca3f7d2fe1a96bbaa82a20a6c92cbd4979e0ade3effb038155c2` |
| 4题Smoke Dataset | `9d5e4ea103edf29f58f1837dd34ede6fb4d47e22fbb162105b8ff5ecf71af2f1` |
| RAG Source | `992b88cd8dc138198fc49ebfe0cecca0b2f6a0387ef5a1d1c0e90f0d98297f1c` |
| Native Smoke Profile | `7bba99b2034f84f14e15a859c1478f8f58647df8e22837343a3e40f073993d61` |
| Build | `ecd83a43735338e2f909223457682bffa7326b6abd589304b95190262b4a9f03` |

本轮Source在开始/结束及原生Report内一致；与S4-B的 `e0e3d7...` 不同，反映此前工作区现状，不能偷偷沿用旧hash或当成严格同源门禁对照。Rerank地址hash变化；Embedding/RAG/Retrieval参数逐字段与S4-B相同。`catalog-v1` 是原生Report内的index_version标签，不冒充上表真实聚合Index ID。实验profile_id参与Profile hash，不把不同hash都解释为参数差异。

## 3. 正式端到端执行和实际结果

用户单独授权仅重设account_id=3临时密码。凭据仅内存、经正式登录API使用，未修改其他账号、角色、归属或ACL。从dev抽取原4题，不改问题、Gold、预期Outcome或Gate；新建独立Smoke Dataset，正式Dataset API→Job API→原Evaluation Worker→原生产LangGraph→Answer→Evaluator Judge。

正式Job：**`rag_eval_54809a070eeb44fab8e47c846465e64b`**，4/4 completed，Job succeeded；原Gate 0.95，Case Pass **2/4=50%**，Report passed=false。Job完成与质量Gate通过是不同事实。

| Case | Rerank成功/回退 | 阶段耗时ms | Case全程ms | 实际答案 / 原生结果 |
| --- | --- | --- | ---: | --- |
| table_query_003 | 1 / 0 | 738 | 9254 | NX-003可用库存88台，上海测试仓、2026-10-01；ANSWERABLE，Case通过 |
| cross_document_001 | 2 / 0 | 680、928 | 10022 | NX-081额定155 W；2026-02-01购买适用24个月保修；ANSWERABLE，Case通过 |
| no_answer_001 | 1 / 0 | 549 | 5411 | 未编造NX-901功率，要求核对型号；clarify / INSUFFICIENT_EVIDENCE，Case失败（预期NO_KNOWLEDGE/拒答） |
| version_policy_001 | 4 / 0 | 717、595、652、766 | 13887 | NX-001硬件2.0使用120 W，旧1.0的130 W不适用，披露版本冲突；仍INSUFFICIENT_EVIDENCE，Outcome检查失败 |

**8次有完整阶段观察的Rerank全部applied=true、fallback=false、error=null，模型均为新配置qwen3.7-text-rerank，attempts均1。** 没有未触发而算成功的Case。Provider调用和Stage调用分别记录；Stage包含bridge/本地处理，不能把它叫纯网络时间。阶段median **699ms**，min **549ms**、max **928ms**（n=8），均未超过5秒；样本很小，不能保证未来尾延迟或服务SLA。

4题Document Recall@5 **83.33%**、@10 **100%**（n=3 Gold-doc eligible），Case Pass不是回答准确率。Native Judge correctness/groundedness均 **0.975**（n=4）；无答案题unsupported_claim_rate为 **0.1**，它的澄清文本列举型号/提出替代型号不能视为严格证据充分的拒答。版本题Judge correctness=1仍未通过原生Outcome检查。Chunk Recall/MRR/nDCG**未测**，没有Gold Chunk标注。Case latency P50 **9254ms**、P95 **13887ms**，n=4，沿用原生Report口径，不推算20题指标。

### 实际排序变化

前后排名来自同一次正式 `_rerank_documents` 的真实列表，不从文件名伪造Chunk。完整chunk_id、版本、hash、候选列表和Provider分数见 `ranking-analysis.json` / `stages.jsonl`。分数是实际Rerank分数，不是已校准的可回答概率；未采集前序RRF的完整数值分数，不进行不同评分体系的数值对比。

- 库存：L1父块1→1（0.9949），一个无关型号叶子4→2（0.6073），L2块2→3（0.5931）；最终引用并非这些宽父块，而是S4-A的真实NX-003行投影。
- 跨文档参数子查询：产品参数L2块1→1（0.9652）、技术规范3→2（0.8281）；政策子查询：新政策1→1（0.8502），旧政策3→2（0.5317），保修规则2→3（0.4339）。最终答案引用[1]参数与[17]新政策，跨文档Document Recall@5仍0.5；**子查询内健康Rerank不等于全局合并Top5必然覆盖全部文档**。
- 无答案：其他产品参数父块15→1（0.6602）。模型语义相似评分不证明NX-901存在，不能仅据高分或min_score=0推导拒答正确。
- 版本：初始参数父块7→2（0.9385），另一子查询2→1（0.9439）；补充/后续子查询中7→1（0.9848），发布说明1→2（0.9679）。排序改善没有自动改变原生覆盖/Outcome语义，本阶段不修该算法。

### Run / SSE / 历史与Checkpoint边界

为验证正式用户入口，用同一库存题另执行一次原Run/SSE，不混入4题Job指标：Run **`run_f68f04028e74464e8a8e755279283ba4`**，succeeded，7.236秒；返回88台，17个连续Event，包含tool.completed、message.completed、run.completed。API Trace明确applied=true、fallback=false、attempts=1、新模型身份。

所以本次**共观测9次成功重排、0次回退**：8次Worker有完整前后排序和分阶段时间；额外1次API Run只有正式Trace与最终排序，**其重排前完整列表与独立阶段耗时未测**，不拿7.236秒冒充Rerank耗时，不将它混入n=8的阶段延迟统计。这是观测覆盖限制，不是一次失败。

初始实验脚本误用Thread响应的 `id` 而非正式 `thread_id`，在创建Run前停止；修正实验脚本后只补跑SSE，**没有重跑或替换4题Job**。第一次以原始字典比较历史Trace得false；只读复核显示HTTP response_model会补nullable默认字段。使用原RagTrace校验、exclude_none及相同正文脱敏后，**live SSE、Journal replay、历史Message来源完全一致**，Event sequence也一致。原false结果保留，复核结论独立保存，没有修改服务器数据使比较变绿。

此库存Run可回答，没有HITL pause，所以 `run_checkpoints` 为0是既有语义，不能称已在线验证Checkpoint恢复。原Checkpoint身份、冻结版本、跨Tenant拒绝重绑定由聚焦离线回归覆盖；本阶段**未在线运行HITL resume**，也未运行浏览器UI点击/渲染回归。

## 4. 来源、隔离、异常及历史对比

4题共8次数字引用均合法（8/8），3个Gold-row Case的Excel精确行 **3/3**：库存/库存Sheet行4；参数/产品参数Sheet行82；版本参数/产品参数Sheet行2。无错误、缺失、过宽行。最终检索Excel来源完整 **19/19**；真实版本/chunk/Manifest hash匹配，重排输出均来自同次输入。该检查证明本次授权scope内未出现来源身份漂移，不代表已穷举跨Tenant/ACL攻击场景。

相对S4-B最终30次重排全回退、PROVIDER_REQUEST_INVALID，本次8次完整阶段及API Trace不再出现该错误，也未出现任何被Adapter分类为4xx请求无效的重排。没有抓取上游原始HTTP正文；不编造逐请求HTTP状态码明细。本次未注入线上HTTP400/Timeout故障，降级是否仍正确由既有Provider/Stage单测及历史真实回退证据支持，**不能把健康线上成功叫线上故障降级测试**。

S4-B `table_query_003` 的Snapshot PROVIDER_TIMEOUT发生在Rerank之前。本次该题Job和Run均成功且无Snapshot超时；这仅表示本轮未复现，**根因未解决，仍需独立诊断**。Provider deadline、排队、模型与Snapshot外部I/O仍可能超时；不将Rerank恢复作为Snapshot已修复的证据。保留原失败分母与历史报告，不修改Fingerprint、Gate或旧baseline。

## 5. 实际检查与测试

以下Python均使用Ubuntu锁定环境，cwd为仓库根，非全局Python：

```sh
python .artifacts/synthetic-enterprise/s4d-rerank-smoke/inspect_environment.py environment-before.json
# 原launcher安全重新加载；observe.py仅包装原Worker的同一次调用。
python .artifacts/synthetic-enterprise/s4d-rerank-smoke/run_smoke.py
# 第一次脚本在SSE入口字段检查失败，原Job已完成；只补SSE，不新建Job。
python .artifacts/synthetic-enterprise/s4d-rerank-smoke/run_smoke.py --sse-only
python .artifacts/synthetic-enterprise/s4d-rerank-smoke/summarize.py
python -m pytest tests/test_reranker_adapter.py tests/test_rerank_stage.py tests/test_rag_provenance_contract.py tests/test_run_event_contract.py tests/test_rag_evidence.py -q --junitxml=.artifacts/synthetic-enterprise/s4d-rerank-smoke/focused-tests.xml
python -m ruff check backend/providers/rerank.py backend/providers/runtime.py
python .artifacts/synthetic-enterprise/s4d-rerank-smoke/inspect_environment.py environment-final.json
```

**60 passed、4 subtests passed，23.66秒，1项langchain-community弃用warning；Ruff通过。** 包含真实Adapter封装契约、malformed、timeout/cancel、有限重试、熔断、显式fallback、来源校验与Event契约；这些为离线回归，不是额外网关故障请求。未跑全仓库pytest；此前两个历史baseline fingerprint失败不在本次聚焦集合，不声称已消除。未改任何正式测试。S4-A/S4-B共119份历史资产SHA-256不变。

## 6. 20题正式评测准备与授权边界

可以创建一个新的、独立的健康Rerank20题Worker Job，但**现在停止，不自动创建**。预计约 **100–180次外部模型/远端Rerank请求**；复杂子查询、澄清、重试保守预留至 **250次**。这是一次20题原生Worker Job，不另跑一轮20题CLI、不跑冻结60题。估算依据：Fast/Planner、每子问题Grader与Rerank、Answer、Evaluator Judge；本轮版本题就有4次Rerank，不能假定每题仅1次。

此前用户说明接口免费或额度充足。若计费条件未改变且这些调用均在免费额度内，新增现金支出可为0；**没有可核验单价/Token账单，不能提供可信人民币总预算或把账户Run的cost=0当真实Provider账单**。正式20题启动前需用户明确授权该规模并确认仍免费/额度足够或指定费用上限。

冻结执行前配置：Embedding **BAAI/bge-m3@5617a9f61b028005a4858fdac845db406aefb181**、CPU、1024；top_k8/candidate30、最多4子查询/并发2；Grader4800/每块1200字符、Answer12000字符代理预算；四角色Profile及Rerank配置见上表；Dataset/Corpus/Index/Source/Fingerprint见第2节和 `evaluation-preparation.json`。Evaluator可用已由4题真实Judge验证。重启后需创建新Job冻结当前Model Snapshot，不复用旧Job身份；Rerank本身是进程配置，需要同时保留Profile receipt，不能声称它已被四角色Model Snapshot冻结。

建议授权后只运行一次新20题Job，原失败仍保留，不反复挑选成功结果；Snapshot失败单独统计，NO_KNOWLEDGE/版本Outcome/跨文档策略不在该轮修改。健康Rerank建立新基线可行，但不预判它必然通过0.95质量Gate。

## 7. 本次交付与未测范围

仅新增本报告与ignored `.artifacts/synthetic-enterprise/s4d-rerank-smoke/` 实验脚本、环境/index receipt、原生Job/Dataset/Cases/Report、Provider/Stage记录、前后排序、引用审计、SSE来源复核、测试XML、历史SHA清单与准备清单。原问题/Gold未上传到知识库，Smoke Dataset只进入Evaluation控制面。运行时观测包装已移除，标准服务恢复ready，所有生产源码与正式资产保持本轮开始时状态。

独立Provider的561ms及Stage的101ms仅证明三个短模拟文本的Adapter连通性；本报告的8次Worker与1次用户Run才是企业语料上的端到端证据。未测：完整20题健康Rerank基线、冻结60题、线上故障注入、线上HITL恢复、浏览器渲染、精确Token/费用、无Gold Chunk的MRR/nDCG、额外API Run重排前排名/独立阶段耗时。Snapshot历史问题未解决。停止在本Smoke，不进入新的算法开发阶段。
