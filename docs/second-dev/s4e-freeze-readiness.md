# S4-E：冻结测试集运行准备与预算

日期：2026-10-13（Asia/Shanghai）。更新状态：**Milvus 阻塞解除，授权后的模型预检通过；唯一一次 60-test Job 已完成 60/60，原生 Quality Gate 未通过**。原离线检查失败仍保留；最终结果见 [正式评测](s4e-final-evaluation.md)。

本报告是预检记录，不是冻结集质量报告。初次预检未创建冻结 Dataset/Job、未调用外部模型；正式运行前未逐题研究冻结题目或答案。第 4～6 节保留初次预检结果，第 10 节保留后续 Milvus 修复，第 11 节记录新的模型调用及账号授权，不覆盖初始失败证据。

## 1. 范围与不变量

遵循根目录及 backend、RAG、tests、frontend、docs、evals/rag 的 AGENTS、CONTEXT，以及 Document Version、Provider、Evaluation、来源契约相关 ADR；参考 S1～S4 的正式报告，重点是 [S4-B](s4b-evaluation.md)、[S4-D Smoke](s4d-rerank-end-to-end-smoke.md) 和 [健康 Rerank 基线](s4d-healthy-rerank-baseline.md)。

最后开发期参考 Job 为 `rag_eval_654bb3d8fef148a19803db409859b879`。不将人工认可的澄清转为自动通过，不调整 Outcome、Gold、Gate、Judge Prompt 或算法。不上传、重建、迁移、提交或推送；未开始 S5。

初次预检只新增本组报告及 `.artifacts/synthetic-enterprise/s4e/` 中的离线检查、只读诊断工具和运行收据。使用 `ponytail` 复用既有工具与标准库；使用 `diagnosing-bugs` 将 Milvus 全量核验超时缩小为有界读取与定向日志检查。初次诊断停在证据与修复建议；获得用户明确环境修复授权后，才添加第 10 节的路径映射。该授权不包含模型调用、账号重设或冻结 Job。

## 2. 源码、资产和依赖冻结

所有完整 SHA-256 在 `freeze-receipt.json`、`workspace-sha256.json` 和 `readiness-summary.json`，以下均为本次实际读取：

| 身份 | 值 |
| --- | --- |
| Git HEAD | `814cf69e01167669c9efae20c23d61daed61f979` |
| 实际工作区逐文件 SHA 清单 | 570 个文件；清单 SHA `92af34b2fff59b16af59bcfe1f22bbda454de4adb67cf0c14d047e4a470a98b4` |
| RAG Source Fingerprint | `992b88cd8dc138198fc49ebfe0cecca0b2f6a0387ef5a1d1c0e90f0d98297f1c` |
| 60-test Dataset Fingerprint | `3c40675787f2de08ce1690dc2fcadfcb7bdb770aac9951fd44869a55477f6739` |
| 冻结 Dataset 文件字节 SHA | `514e1bc0a9b31802fe45600b1d84a9bb5ee95ca37c72f3655a118c840484ff8c` |
| Corpus Fingerprint | `9c8144131a4d9a93be3621d80cd14691ee858b086f9a8650497dde5459ab049e` |
| Catalog Index ID | `6832df8a828ce611f321023be9e92ba78c377e14609ef36d9a789c7118ed9954` |
| Build Fingerprint | `ecd83a43735338e2f909223457682bffa7326b6abd589304b95190262b4a9f03` |
| Model Catalog Hash | `11164a28bef4fd7b19c61e6764807fea9f18bb55d7a2fc6c0afed28351657469` |
| 当前物理配置对应的原 dev Profile Hash | `5ce33b00b5ba65bc2e12ff2008ff0979bccdcfb629eda39155d3591b25e80afc` |

工作区清单包括跟踪文件及非忽略的新增文件，排除 `.idea/`、`.artifacts/` 和 Secret `.env`；包含 `.env.example`。Windows Git 初始只有未跟踪的 `.idea/`。WSL Git 因 CRLF/行尾解释显示大量文本修改；`git diff --ignore-space-at-eol --stat` 无输出。不能仅靠 HEAD 或任一平台 Git status 判断实际运行源码。本轮再次校验原 570 个文件，**字节变化数为 0**，包含原有 Gold、Gate、baseline 和锁文件。新增三份报告不改变已冻结的执行源码。

正式 Source Fingerprint 不覆盖整个仓库所有文件，不能替代上述实际字节清单。

依赖检查：

- 后端使用 WSL Ubuntu-24.04 的 `/home/lenovo/.local/share/supermew/venv/bin/python`，Python 3.12.3；不使用 Windows 全局 Python 跑后端。安装的 OpenAI、LangChain-OpenAI、Alembic、pymilvus、Ruff 分别为 2.45.0、1.3.5、1.18.5、2.6.16、0.15.21，与锁文件匹配。安装包与 `uv.lock` 的字符串版本差异只有 `torch 2.13.0+cpu` 对 `2.13.0`；这是 CPU 构建标记，仍需保留在环境身份中，不声称完整逐字一致。
- Node v24.15.0，npm 11.12.1；符合 engines 范围，但不是 packageManager 声明的 npm@10.9.7。检查了 250 项已安装锁定依赖，版本差异 0；本轮未重新安装或修改 lock。准确记录差异，不能称为已使用声明的 npm 版本。
- `pyproject.toml`、`uv.lock`、`frontend/package.json` 和 `package-lock.json` 的原始 SHA 都保存在冻结收据中；无需为预检引入新依赖。

## 3. 冻结数据的独立性

真实文件名为 `evals/rag/synthetic_enterprise/dataset_frozen_v1.json`，不是 `dataset_test_v1.json`。

程序化检查：60 frozen / 20 dev，ID 不相交，合并为原始 80 条；每条序列化字段与原 80 条 Dataset 对应记录一致。仅检查 Schema、字段一致性、数量和分布，不提前逐题研究题目/答案。冻结分布为简单事实 15、表格 15、跨文档 15、无答案 7、版本政策 8；HITL 预填回答总数 0。

原生 Dataset Validation 成功，指纹为上表值。`manifest.json` 所列文件字节全部匹配，`ingestion_allowlist` 数量为 12。未运行生成器覆盖正式语料；相关单测运行在其自身临时目录。

只读数据库检查发现该冻结 Dataset 指纹对应的导入数 0、Evaluation Job 数 0，开发期参考 Job 保持 succeeded / 20 cases。这证明当前持久系统没有该冻结指纹的历史 Job；不将其夸大为对所有外部系统历史的证明。本轮外部模型调用数 0。

## 4. 初次预检的运行环境与配置

初始 Docker Desktop 未运行，PostgreSQL/Redis 停止，API/Worker 不在运行。先启动现有 Docker Desktop、现有 PostgreSQL/Redis 容器；没有重建容器或数据卷。暂停/恢复之间又观察到基础设施重启、PostgreSQL 容器退出、原 API/Worker 消失；原因未确认，不归因于代码。再次只启动已停止的 PostgreSQL，并核验没有活动工作后通过正式 launcher 启动服务。

正式入口：`python -m backend.launcher --no-reload --shutdown-timeout-seconds 30`，本地缓存 Embedding 以 HF/Transformers offline 环境启动，不下载模型。恢复后 launcher/API/Indexing/Evaluation PID 分别为 368/369/370/371；PID 仅为该时间点的收据，不是持久身份。

| 检查 | 实际结果 |
| --- | --- |
| PostgreSQL / Alembic | 可连接，Schema current；未执行迁移 |
| Redis | PING=true |
| FastAPI Ready | HTTP 200；不等于 Milvus Collection 可查询 |
| Indexing Worker | 新鲜心跳约 0.72s，Build 匹配；Ready 显示 1 个兼容新鲜 Worker |
| Evaluation Worker | 新鲜心跳约 0.84s，正式进程运行 |
| 历史 Worker 记录 | 有 status=running 但心跳陈旧的记录，不据此声称多个活跃 Worker，也未清理这些记录 |
| 活动 Run / Index Job / Evaluation Job | 0 / 0 / 0 |
| 观察包装器 | 没有 `observe.py` / `launch_observed.py`；使用正式 launcher |
| API/Worker 配置 | 四进程 RERANK、EMBEDDING 及结构化策略环境键比较无差异；当前 Profile 和 Model Catalog 与 S4-D 完整相等 |
| 文档 / PG Manifest / Parent | 12/12 READY；与保存身份一致，详见下一节 |
| Milvus | 可连接、列 Collection；Loading 50%，实际读取失败；**阻塞** |
| Fast/Grader/Evaluator 真实结构化请求 | 本轮未测；等待新模型授权后做最小连通性检查 |
| 正式 RerankStage 真实请求 | 本轮未测；历史健康开发期成功不能替代当前连接检查 |

模型角色冻结：

| 角色 | 模型 | Profile ID / Version |
| --- | --- | --- |
| Answer / Grader / Evaluator | deepseek-flash | `model_cca5c8be5c5b42d2b31449a8579aea38` / 1 |
| Fast / Planner / Rewrite | deepseek-v4-pro | `model_489cb92681f943bca8364bde51e8fc3f` / 1 |

上述模型均 timeout=30s。Fast、Grader、Evaluator 的显式策略为 `deepseek_function_calling`；保留 Schema 校验，仅结构化调用关闭 Thinking。没有更改该补丁或普通 Answer 行为。

Embedding 为 BAAI/bge-m3，Revision `5617a9f61b028005a4858fdac845db406aefb181`，CPU，1024 维；缓存和 Revision 未变。

Rerank 为 qwen3.7-text-rerank，enabled=true，timeout=5s，min_score=0，candidate_limit=30，单文档/总字符限额 8000/60000；并发 4、连接池 20/10、Circuit 阈值/冷却 5/30。来自正式 settings/env；它不是独立的持久 ModelRole Profile。保存的 endpoint 只为不可逆 SHA，不保存网关地址。

检索 top_k=8、candidate_k=30、最多 4 子问题、并行 2、leaf_level=3、Parent Merge enabled=true / threshold=2、context 预算=12000。`max_context_tokens` 名称在当前实现中实际是字符代理，不当作真实 Token 计量；Grader 总/单文档证据预算 4800/1200 字符。

Gate 与参考 Job 相等：required provenance=live_rag，k=[5,10]，critical_no_regression=true，case_pass_rate minimum=0.95、max_regression=0；不为了 14/20 的历史结果下调门禁。未来正式 Job 使用新冻结评测标签时会有新的 Profile Hash，必须保存完整 Profile；不把标签变化或 Dataset 变化伪装为相同评测身份。

## 5. 文档身份核验与 Milvus 阻塞

PostgreSQL 内的 12 个 Document Version、Build、全部 IndexManifest 与 S4-B 保存身份相等，Catalog Index ID 与 S4-D 相等。允许文档集合精确等于 12 个 allowlist 文件，未混入答案资产。真实 Document ID、Version、Chunk ID、哈希及 Catalog Snapshot 保存在 `postgresql-identities.json`。

| 文件 | 当前真实 Document Version | Parent 实读数 | Vector Manifest 数 |
| --- | --- | ---: | ---: |
| inventory.xlsx | `docver_f515043826194db68855bdd7aa3c3a96` | 15 | 200 |
| product_prices.xlsx | `docver_5551578bd75e449084cd1608d22f558a` | 15 | 200 |
| product_specs.xlsx | `docver_0c8b6bd223db4f8ab4c6637bea269583` | 24 | 200 |
| repair_records.xlsx | `docver_c057ae23c2f644b4b9b6883541882924` | 11 | 100 |
| aftersales_policy.html | `docver_87b8e52aad484ed9bde66d68c472ff92` | 6 | 3 |
| product_faq.html | `docver_573746509ba24b5db414b6b5c511a6dc` | 402 | 201 |
| product_manual.html | `docver_6bac446c19bf4571bb2fec466216b074` | 402 | 201 |
| release_notes.html | `docver_1f639e93301d48b884d112d99823be42` | 12 | 6 |
| selection_guide.html | `docver_5c585861bd5d4bf68ab9ce8cc0e632df` | 402 | 201 |
| technical_specs.html | `docver_e42c752f63a4424cb79b337a09527d6d` | 402 | 201 |
| troubleshooting.html | `docver_d481d169edec43e6b8e3831bda989aba` | 402 | 201 |
| warranty_rules.html | `docver_0b51166dee4642a286d7c3087454b6e2` | 404 | 202 |
| 合计 | 12/12 READY | 2497 | 1916 |

Parent 使用原生 `ParentChunkStore.verify_version`，exact 全部 true；实读文本 SHA、content_hash 与 Manifest 一致。右列仅是 **PG Manifest 期望数，不是本次 Milvus 实读数**。不能凭 Document READY 或 Catalog 相同声称跨库核验通过。

故障链路：两次复用原 `inspect_index.py` 的完整核验均超过 300s，没有完成 `MilvusStore.verify_version`。随后有界探针成功列出 `supermew_embeddings_catalog_v1`，load_state=Loading / progress=50；limit=1 的只读 query 在约 4637ms 返回 MilvusException code=106，脚本明确退出 1。此前同一症状约 4645ms 复现。

按三个假设检查：资源不足、正常冷启动、特定 Segment 加载失败。定向日志支持第三项：Segment `469702728769062766`、field=121 的 JSON Key Stats 加载持续失败，`LocalChunkManager.cpp:60` 报 `invalid local path:var/lib/milvus/data/json_stats/.../meta.json` / segcoreCode=2011。

Docker 只读 stat 显示：容器 cwd=`/milvus`；对应绝对 `/var/lib/milvus/data/json_stats/.../meta.json` 存在，为 222-byte regular file；日志使用的相对路径 stat 退出 1。当前内存约 281.3MiB / 7.412GiB，没有本次故障由 OOM 引起的证据。确认了 **加载阶段的路径错误**，但尚未确认哪项持久配置、元数据写入或 Milvus 版本行为产生该路径，不能把所有根因都称为已经修好。

证据在 `runtime-probe.json`、`runtime-probe-resumed-ready.json`、`milvus-load-diagnostic.json`；后者只保存三条相关日志和文件 stat，不保存完整日志或私有配置。镜像身份也在收据内。

截至初次预检，没有 release/reload、删除/重建 Collection、重写 etcd、复制文件、创建软链接或调整启动路径。恢复必须先明确授权并保持现有 Version/Manifest/Index 身份；若只能重建索引，应停止并重新确认实验设计，不能继续称为同一冻结索引。随后授权的修复见第 10 节。

历史 `table_query_003` Snapshot Timeout 发生在 Rerank 之前，与本次 Milvus 加载错误不能合并为已修复。S4-D 只是未复现；仍是独立可靠性风险。

## 6. 离线检查与真实结果

从仓库根运行；后端命令下文的 `python` 指上述 WSL venv，前端从 `frontend/` 使用当前 npm。完整命令数组、cwd、退出码和耗时保存在 `backend-checks.json`、`diagnostic-checks.json`、`frontend-checks.json`。两批 pytest 文件不重叠，隔离复查不重复加总。

| 检查 | 实际结果 |
| --- | --- |
| 53 文件核心 pytest（RAG/Outcome/HITL/Checkpoint、Excel、Parent、Evidence/Citation、Evaluation、Provider、Worker 等） | 595 passed、4 failed、36 subtests passed、57 warnings；141.97s |
| 额外 5 文件（Milvus Writer/返回结构/Filter、Knowledge Tool Outcome、Settings 安全） | 75 passed、26 subtests passed；7.99s |
| 后端合计 | 670 passed、4 failed；另 62 subtests passed；不是完整仓库所有测试 |
| ModelRegistry 单项隔离复查 | 1 passed；不抵消核心组合中的失败 |
| Ruff check | 退出 0 |
| Ruff format --check | 退出 1；2 文件需格式化，312 文件已格式化；未修改源码 |
| Run/Tool Contract 类型生成 --check | 退出 0 |
| RAG Evaluation Schema 生成 --check | 退出 0 |
| 原生 frozen Dataset validate | 退出 0，60 cases |
| Offline Contract Score，不比较历史 baseline | 退出 0，contract_smoke passed=true；不是实际 RAG 效果 |
| Offline Score 加原历史 baseline | 退出 2，Source/Corpus fingerprint 不同；未绕过校验 |
| 前端 Unit | 230 passed / 27 files |
| 前端 typecheck / lint / build:check | 全部退出 0，initial JS gzip=73.64KiB，通过现有 bundle gate |

四个失败分别为：

1. `tests/test_rag_eval_cli.py::test_cli_scores_offline_baseline_and_writes_sanitized_reports`。
2. `tests/test_rag_eval_cli.py::test_cli_returns_one_for_a_quality_regression`。
   以上两项是历史 Source/Corpus baseline identity 不匹配；保留失败和原 baseline。
3. `tests/test_agent_runtime.py::ModelRegistryTests::test_model_roles_are_allowlisted_lazy_and_cached`：组合运行发现多了 Evaluator 角色；相同 cwd 下单独运行通过。符合测试环境/集合隔离不足的现象，尚未证明完整污染来源，也未证明运行时模型角色错误。不是本轮新增代码回归；需独立诊断，不擅自补空配置让结果通过。
4. `tests/test_service_launcher.py::test_repository_start_script_exposes_the_unified_launcher`：`/usr/bin/env: bash\r: No such file or directory`，start.sh 的 CRLF shebang 在 Linux 失败。当前直接执行正式 Python launcher 正常；不能声称 shell 入口已通过，也未转换行尾。

Ruff format 指向 `backend/providers/runtime.py` 与 `tests/test_knowledge_tool_outcomes.py`。冻结阶段未运行格式化改变源码身份。

辅助命令错误单独记录：最初 Validate 用了不存在的 `dataset_test_v1.json`，退出 2；随后使用真实 `dataset_frozen_v1.json` 校验通过，不将错误路径视为 Dataset 契约故障。诊断探针初稿假设不存在的 MilvusSettings.token，后来又遇到异常 code 为可调用对象的 JSON 序列化问题，均只修正忽略目录探针。恢复时 PostgreSQL 未启动也导致一次探针提前失败；最终有界探针已产出真实 code=106。

主要实际命令：

```bash
python .artifacts/synthetic-enterprise/s4e/checks.py backend
python .artifacts/synthetic-enterprise/s4e/diagnostics.py
python -m pytest tests/test_milvus_writer.py tests/test_milvus_retrieval_shapes.py tests/test_milvus_filters.py tests/test_knowledge_tool_outcomes.py tests/test_settings_security.py -q --junitxml=.artifacts/synthetic-enterprise/s4e/additional-backend.xml
python .artifacts/synthetic-enterprise/s4e/freeze.py
python .artifacts/synthetic-enterprise/s4e/database_probe.py
python .artifacts/synthetic-enterprise/s4e/runtime_probe.py runtime-probe-resumed-ready.json
python .artifacts/synthetic-enterprise/s4e/finalize_readiness.py
python scripts/evaluate_rag.py validate --dataset evals/rag/synthetic_enterprise/dataset_frozen_v1.json
python scripts/generate_contract_types.py --check
python scripts/generate_rag_eval_schemas.py --check
python -m ruff check .
python -m ruff format --check .
```

Windows 本地 Docker 定向探针为 `python .artifacts/synthetic-enterprise/s4e/milvus_log_probe.py`；它不加载业务模型。前端实际执行 `npm run test:unit`、`npm run typecheck`、`npm run lint`、`npm run build:check`。上述复现命令不是现在允许启动模型评测的命令。

未执行：完整发布门禁（mypy、覆盖率、benchmark、依赖审计）、前端 Playwright E2E/format check、真实网关结构化/Rerank 连通性以及 60-test 评测。不能据此宣布完整发布验收通过。

## 7. 60-test 请求预算（等待授权）

历史 20-dev 可直接验证的数据是：31 次 Rerank、均 attempts=1、0 fallback；7 个复杂 Case、0 rewrite、16 个 answer 分支、20 个 Judge。历史产物没有完整的 Fast/Grader HTTP 调用及 Token 帐本，因此下面各角色是**路径推算，不是实测调用数**。不读取冻结题逐题推算预算。

| 角色/阶段 | 60-test 预计逻辑请求范围 |
| --- | ---: |
| Fast / Planner | 20–60 |
| Grader | 90–160 |
| Answer | 40–60 |
| Evaluator Judge | 60 |
| 远端 Rerank | 90–160 |
| Fast Rewrite | 0–40 |
| 合计 | 300–540 |

建议为瞬时故障/重试预留 **1100 次外部请求额度**；这是保守运营估计，不是代码强制的硬上限。单次 Provider 策略最多 2 attempts，关闭 SDK 隐式重试。原生 Worker Case timeout=120s、Job lease recovery max_attempts=3 保持不变；不授权自动重跑 Job。

更极端的静态路径上界：每题 1 Planner、最多 4 子查询，每子查询最多 2 次 Grader、1 次 Rewrite、2 次 Rerank，再 1 Answer 和 1 Judge，全部走两次 Provider attempt：

`60 × [1 + 4 × (2 + 1 + 2) + 1 + 1] × 2 = 2760 requests`。

这是无中断、无额外 HITL 回答的单次 Job 理论上界；120s deadline 往往先截断，不能把实际一定小于 540 当作承诺。Rewrite 的方法选择与改写文本在 `utils.rewrite_query_once` 中是**同一次** Fast structured request，不重复计两次；Grader 给出 missing-evidence query 时甚至不需要额外 Fast。

授权后还需 3 个结构化角色与 1 个正式 RerankStage 的最小预检，额外 4 个逻辑请求、最多 8 attempts。预计 Job 与预检共约 304–544 个逻辑请求；理论上界 2768 次，不含获新授权后才可能执行的中断恢复/重新评测。

没有可信网关单价、完整 Token 使用信息或可验证收费口径，**不能换算人民币费用，也不能以此前“额度充足”代替本次授权**。按 Token 或候选文档收费时，请求数不等于费用上限；若需金额硬限额，应由网关账户配置硬限制并提供可验证单价。

## 8. 授权后执行协议与指标边界

现在不创建 Job。Milvus 恢复且逐 Version 跨库核验通过、原 570 文件和配置复验、最小模型连通性通过之后，才可经 `/v1/rag-evaluations/datasets` 和 `/v1/rag-evaluations/jobs` 各创建一次正式资产，使用标准 Evaluation Worker。保存正式 API 返回的 Job/Case/Report 和 Execution Receipt，不额外运行一轮 CLI Live RAG，也不选择性重测失败题。

若需要专用 account_id=3 登录，之前内存密码已丢失；本阶段没有重设账号。该操作需要本轮单独授权，不沿用旧阶段授权。

若 Job 中断，立即保留已完成案例、失败证据和 Receipt，不由操作者重新创建/重试。原生 lease recovery 可能自动回收过期 Job；在授权运行前还需确认安全停机/正式取消方案，避免服务重启后无意继续调用。不得为此改变冻结 Worker 策略或抹除失败。

评测结果固定为原生 Gate 与全 60 题分母；有 Gold 文档的 Recall 必须单独报告有效 n，失败题仍留在总体 Case 分母。Chunk MRR/nDCG 因缺完整 Gold Chunk 映射未测，不用文档名冒充 Chunk ID。Judge correctness/groundedness/completeness 为连续分数，Case Pass 不是 Answer Accuracy。

完整必要文档覆盖率可由真实最终检索文档集合与原 Gold Document 集合比较，另列初始召回/最终 Evidence 的人口与截断差异。Rerank 排名、attempts、错误、延迟仅取原生 Trace/可验证阶段记录；没有完整角色调用/Token 帐本时明确未测，不拿静态预算当实测调用量。

引用审计存在明确适配限制：`scripts/audit_rag_citations.py::main` 只接受 20-dev；不得直接把它对 60-test 的拒绝关掉。其 `audit_case`、`source_rows` 可复用于授权执行后真实 Job 导出结果的只读后处理，绑定本次真实 Version/Leaf 身份、使用原规则、动态统计 eligible 分母；不新增 RAG/Judge 运行框架，不硬编码开发集“12 cases”或“未执行 frozen”的旧说明。此 60-test 辅助后处理尚未执行。缺少非 Excel claim-to-source Gold 的全面 Citation Recall/entailment 仍未测。

## 9. 初次预检结论与审批边界

数据契约与冻结独立性检查通过，后端/前端必要检查已经实际运行，源码/模型/PG 索引身份与健康开发期一致；但 **Milvus 不可查询，跨库身份核验未完成，真实网关连通性本轮未测，且离线门禁不是全绿**。因此目前不能启动冻结集，更不能进入 S5。

下一步先请求“只修复 Milvus 运行环境、保留索引身份”的明确方向；未经授权不实施路径/持久元数据修复。若修复影响源码或索引身份，应重新冻结并解释可比性。环境恢复后重新报告预检，确认上述新预算与必要的账号操作，才执行唯一一次正式 60-test Job。

最终结果位置：[正式评测状态](s4e-final-evaluation.md)、[质量复盘状态](s4e-quality-analysis.md)。目前均明确未执行，不能用于宣称冻结集性能或质量提升。

## 10. 用户授权后的 Milvus 环境修复

时间：2026-10-13 16:39～16:43（Asia/Shanghai），以收据 UTC 时间换算。本轮授权仅为“修复 Milvus 运行环境，保持业务代码、Document Version 和索引身份不变”；没有扩展为模型请求或正式 Job 授权。

### 根因证据与修复选择

重新运行同一个有界探针，得到 Loading 50%、query code=106、约 4652ms，退出 1；活动 Run/Index Job/Evaluation Job 均为 0。容器使用现有 `milvusdb/milvus:v3.0.0` 镜像、`milvus-existing-data` 数据卷及原 user.yaml 挂载。服务用户 milvus 能读取 644 权限、222 字节的原 JSON Stats meta.json，内容为有效 Stats 布局，并非文件丢失或读取权限不足。

对应官方 [LocalChunkManager 源码](https://raw.githubusercontent.com/milvus-io/milvus/v3.0.0/internal/core/src/storage/LocalChunkManager.cpp) 直接按传入文件路径检查存在性/读取，不自动拼接 root；结合实际 cwd 和 stat 结果，支持本次相对路径解析失败的判断。路径由哪一处上游写入/拼接产生仍未完整追溯，不把环境修复称为上游代码修复。

选择添加窄范围路径映射，而非复制 Stats、修改元数据、切换镜像或改变数据位置：

```text
/milvus/var/lib/milvus/data -> /var/lib/milvus/data
```

只创建原来不存在的 `/milvus/var`、`/milvus/var/lib`、`/milvus/var/lib/milvus` 三个目录及上述 symlink；不覆盖已有路径。执行前再次校验 Schema current、活动工作为零、原 570 文件 SHA 均未变、真实数据卷挂载一致。原 meta.json 修复前后 SHA 都为 `feb98c890191ae1bae44e79ef17e5dd4ed2ec6cb3e9cde7caf05bd38a6c00a6b`。

Milvus 的既有自动加载随后完成，**没有重启 Milvus、主动 release/reload、重建索引或修改 Schema**。本轮开始时另发现本地 PostgreSQL/API/Worker 已停止，只恢复已停止的原 PostgreSQL，并在活动数为零时通过正式 launcher 启动服务；没有中断正在运行的工作。修复后 launcher/API/Indexing/Evaluation PID 为 383/384/385/386，无实验观察包装器。

### 验证结果

| 检查 | 修复后的真实结果 |
| --- | --- |
| 原症状探针 | 同一脚本退出 0；Collection Loaded；query 返回 1 行，约 73.34ms |
| 12 个 Document Version | 12/12 READY，身份未变 |
| MilvusStore.verify_version | 全部 exact=true，实读 1916 个向量 Chunk |
| ParentChunkStore.verify_version | 全部 exact=true，实读 2497 个 ParentChunk |
| IndexManifest 与实读正文哈希 | 两种 Store 均逐版本通过；不再只是 PG 侧期望数 |
| Excel 来源 | 700 个真实叶子具备 sheet_name/row_start/source_anchor；整份来源诊断与 S4-B 按 Chunk ID 比较相等 |
| Catalog / Model / Profile | Catalog Index ID 未变；完整 Profile、Model Catalog 与 S4-D 相等 |
| Source / Corpus / Dataset | 所有指纹未变，原 570 文件字节未变 |
| API / Redis / Worker | Ready 200、PING=true、正式两 Worker 有新鲜心跳，进程 Rerank 配置一致 |
| 活动工作 / 外部模型 / 冻结题 | 0/0/0 活动；本轮模型请求 0；冻结评测未执行 |

这是路径环境故障的红→绿回归和正式跨库数据核验，不是新的 Live RAG 问答结果。没有重跑此前 670/4 的 pytest，原 4 项失败和格式检查失败保持既有结论；不能因 Milvus 修复将它们改为通过。历史 Snapshot Timeout 也仍未得到独立修复证明。

主要实际命令（仓库根；后端使用已记录 WSL venv）：

```text
python .artifacts/synthetic-enterprise/s4e/runtime_probe.py runtime-probe-repair-red.json
python .artifacts/synthetic-enterprise/s4e/milvus_path_repair.py
python .artifacts/synthetic-enterprise/s4e/runtime_probe.py runtime-probe-repair-green.json
python .artifacts/synthetic-enterprise/s4e/inspect_environment.py environment-after-repair.json
python .artifacts/synthetic-enterprise/s4e/verify_milvus_repair.py
```

其中 `milvus_path_repair.py` 是 Windows 本地标准库编排 Docker CLI，并用 WSL 官方 venv 执行 guard；没有使用全局 Python 跑业务 RAG。WSL 一次 Unicode cwd 调用因 `Wsl/Service/0x8007274c` 未启动，随后使用 `--cd /` 和脚本绝对路径成功，未产生模型重试。

收据：`milvus-path-repair.json`、`runtime-probe-repair-red.json`、`runtime-probe-repair-green.json`、`environment-after-repair.json`、`index-identities.json`、`excel-index-diagnostics.json`、`milvus-repair-verification.json`。初始 `readiness-summary.json` 保留 BLOCKED 历史状态，**当前状态以 milvus-repair-verification.json 为准**。详细产物继续处于 `.gitignore` 允许的 `.artifacts/` 中。

### 持久性与回退

映射位于当前容器 writable layer，未改数据卷、镜像、挂载或 user.yaml。它不是上游永久修复；容器重建会丢失映射。本轮未通过主动重启验证冷启动，仅验证当前自动加载及完整读回；后续重建/升级前必须明确恢复映射或验证上游兼容修复，不得悄悄更换冻结镜像/索引。

回退仅涉及新建的路径：先确认 link 仍解析为 `/var/lib/milvus/data`，只 unlink `/milvus/var/lib/milvus/data`；再按子到父顺序 rmdir 三个目录，且仅允许空目录。**绝不删除 `/var/lib/milvus/data` 或其数据卷**。未执行回退，因为实际症状已消失。

上述修复完成时仍等待模型和账号授权。该等待随后由第 11 节的明确授权解除；修复本身不能证明最终 Gate 或 S5 验收通过。

## 11. 授权后的正式预检与一次性创建

用户明确授权最小模型预检、一次正式 60-test Job，以及仅重设 `account_id=3` 的临时密码。审批预算含预检约 304–544 个逻辑请求、建议 1100 次额度，静态极端上界 2768；无可信单价，人民币金额未知。这是预算而非实测账单。

再次执行 `inspect_environment.py environment-before-frozen-job.json`：API Ready 200、PostgreSQL Schema current、Redis/Milvus 正常、12/12 READY、跨库 Manifest exact、原 Catalog/Source/Corpus/Model 未变；活动 Run/Index/Evaluation Job 均为 0，四个正式进程 Rerank 环境一致，无实验包装器。DB 复验此前冻结 Dataset 导入 0、冻结 Job 0。

`preflight.py` 只发送小型连通性 fixture，不发送冻结题或 Gold：Fast/Grader/Evaluator 均通过原 Pydantic Schema，分别约 1925/696/704ms；正式 `RerankStage.run_async` 使用 qwen3.7-text-rerank，486ms、attempts=1、applied=true、fallback=false。该 Stage 结果不是 60-test 的 Rerank 成功率。

正式登录只重设账号 3 的 password_hash，密码和 Token 仅在内存。只执行一次原生 Dataset POST 和 Job POST，Job ID `rag_eval_64d66d2ec2aa4d2bb047e1df01f0d7b6`；Dataset ID `rag_dataset_c9b45ff934ce4accb88f614df778dcfb`。未设置 baseline_job_id，保持原生 case_pass_rate≥0.95 Gate。创建前写一次性 attempt 收据；不重放 mutating POST，不运行完整 CLI Live Round，不挑选最好结果。

本轮实际命令以仓库根为工作区；`<ROOT>` 为 WSL 绝对仓库路径 `/mnt/d/develop/项目/企业级rag平台/SuperMew`：

```text
wsl -d Ubuntu-24.04 --cd / /home/lenovo/.local/share/supermew/venv/bin/python <ROOT>/.artifacts/synthetic-enterprise/s4e/inspect_environment.py environment-before-frozen-job.json
wsl -d Ubuntu-24.04 --cd / /home/lenovo/.local/share/supermew/venv/bin/python <ROOT>/.artifacts/synthetic-enterprise/s4e/preflight.py
wsl -d Ubuntu-24.04 --cd / /home/lenovo/.local/share/supermew/venv/bin/python <ROOT>/.artifacts/synthetic-enterprise/s4e/run_frozen_evaluation.py
```

这三个步骤均使用锁定后端 venv，退出 0。模型预检通过；Job 终态 succeeded，60/60，attempts=1，无重复 Job。实测质量单独记录在正式报告：Case Pass 40/60，不满足 0.95 Gate。原生 Case 导出不保存完整重排 Trace、分阶段耗时、请求或 Token 帐本；保留最终候选分数及来源身份，未持久化项标为未测，不启动实验 Worker 来补造遥测。

运行后 `inspect_environment.py environment-after-frozen-job.json` 和只读 `analyze_export.py` 均退出 0：Source/Model/Catalog 未变，Profile 排除审计标签后完全相同；原 570 文件变化 0，12/12 READY、跨库 Manifest exact，702 个导出身份错配 0，活动工作 0。`execution-receipt.json`、`final-integrity.json` 和原生 Observation/Report 为本轮当前终态证据；初始 BLOCKED 与修复后 pending-authorisation 收据仍保留历史含义，不当作当前状态。

测试后只读 Parent Pack 诊断输出及预期红断言见 [质量复盘](s4e-quality-analysis.md)。没有应用业务修复、自动重跑、Commit/Push/Merge 或进入 S5。
