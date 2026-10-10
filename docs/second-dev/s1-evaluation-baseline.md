# S1 基线执行记录与 Live 操作说明

日期：2026-10-10。从 SuperMew 仓库根目录执行。本阶段已生成离线资产并验证原生契约，尚未获得 Nebula 企业数据的真实 Live RAG baseline。没有上传文件、启动模型、调用付费 API、修改已有 baseline 或运行冻结集。

## 1. 实际交付和执行环境

新增 `scripts/generate_synthetic_enterprise.py`、`tests/test_synthetic_enterprise.py`、`evals/rag/synthetic_enterprise/` 与本文件、`s1-data-design.md`；S0 报告保留。生成目录包含 12 份逻辑文档、12 个兼容原始版本的上传文件（XLSX 同字节副本、Markdown 的 HTML 投影），200 产品、100 维修和 80 Case。所有业务/日期/答案数据都是虚构的。

机器可用 Python 3.12，但 PATH 没有 uv、项目没有 `.venv`；因此实际离线命令使用 `python`。为运行格式检查与 HTML/parser 回归，在被忽略的 `.artifacts/s1-tools/` 安装了仓库已有依赖 ruff 0.15.21、beautifulsoup4 4.15.0、pytest-asyncio 1.4.0（版本取自 uv.lock）。未改系统环境、pyproject 或锁文件；这些是验证工具，普通生成使用原有 Python 环境已安装的 openpyxl/Pydantic。安装器同时提示当前全局 langchain-openai/openai 版本不兼容，真实环境应执行锁定的 `uv sync --dev --locked`，不能把当前全局环境称为完整可运行环境。

## 2. 实际离线命令与结果

```powershell
python scripts/generate_synthetic_enterprise.py
python scripts/generate_synthetic_enterprise.py --check
python scripts/evaluate_rag.py validate --dataset evals/rag/synthetic_enterprise/dataset_v1.json
python scripts/evaluate_rag.py validate --dataset evals/rag/synthetic_enterprise/dataset_dev_v1.json
python scripts/evaluate_rag.py validate --dataset evals/rag/synthetic_enterprise/dataset_frozen_v1.json
python scripts/evaluate_rag.py validate --dataset evals/rag/rag_smoke_v1.json
python scripts/evaluate_rag.py score --dataset evals/rag/rag_smoke_v1.json --observations evals/rag/offline_smoke_observations_v1.json --gates evals/rag/gates_v1.json --report .artifacts/synthetic-enterprise/original-contract-smoke.json --markdown .artifacts/synthetic-enterprise/original-contract-smoke.md --fail-on-regression
python scripts/generate_rag_eval_schemas.py --check
```

以上实际通过：新 Dataset 分别 80/20/60 Case；旧 Orion Dataset 为 20 Case；旧静态 Observation 的 offline score 返回 `passed=true`；schema 生成检查成功；重复生成和 `--check` 完全一致。没有拿企业 GT 构造伪造的 Observation。

| Dataset | fingerprint |
| --- | --- |
| Nebula 80 全集 | `1543b9da09bcdd810548eedb912a0e5505bc8793ff05b9c25a7a935aeafdbc0d` |
| Nebula 20 开发集 | `7a2fde984e24ca3f7d2fe1a96bbaa82a20a6c92cbd4979e0ade3effb038155c2` |
| Nebula 60 冻结集 | `3c40675787f2de08ce1690dc2fcadfcb7bdb770aac9951fd44869a55477f6739` |
| 既有 Orion smoke | `5056cd2e320d5821813b9bdc352b555abf961801f7d58663f0a359850b215254` |

全部生成资产 hash 在 `manifest.json`，corpus 与 upload_corpus 分别保存，并记录 source→canonical_name 映射。原始 score 报告保留 source/profile/corpus fingerprint、`contract_smoke` provenance，其值仅说明静态评分器可执行，不能表述为原始 RAG 的准确率、延迟或召回。

验证工具命令（无需永久设置环境）：

```powershell
$env:PYTHONPATH = (Resolve-Path '.artifacts/s1-tools').Path
python -m ruff format --check scripts/generate_synthetic_enterprise.py tests/test_synthetic_enterprise.py
python -m ruff check scripts/generate_synthetic_enterprise.py tests/test_synthetic_enterprise.py
python -m pytest -q tests/test_synthetic_enterprise.py --junitxml=.artifacts/synthetic-enterprise/generator-tests.xml
python -m pytest -q tests/test_synthetic_enterprise.py tests/test_rag_evaluation.py tests/test_rag_eval_cli.py tests/test_rag_eval_adapters.py --junitxml=.artifacts/synthetic-enterprise/s1-regression-tests.xml
```

新增测试实际为 **38 passed**（包含 8 个正式 HTML parser 测试），覆盖 byte determinism、跨表关联、单元格/锚点、类别与冻结划分、答案可推导、原生 Contract、未知型号、引用无悬空、冲突规则、manifest allowlist/hash、人工文件保护、额外语料拒绝和 HTML 投影。扩展回归实际为 **73 passed / 5 failed**，共 78 项，无 skip。Ruff format/check 均通过。完整结果保存在本次 `.artifacts/synthetic-enterprise/` 的 JUnit XML。

扩展原生回归出现 5 项失败：2 项 baseline comparison 被 source/corpus fingerprint 校验拒绝；3 项 Live Adapter 生命周期 fake 测试导入时缺 `alembic`。未放宽测试或校验。初次直接用全局 Python 运行 Adapter 测试时缺 BeautifulSoup，补充隔离验证依赖后该 collection 问题已消除。其余纯评分、CLI 校验和 Adapter 投影测试通过；完整后端门禁尚未完成。

### 已有基线身份问题的证据

`git ls-files --eol backend/rag/pipeline.py evals/rag/corpus/orion-plans.html` 显示 Git blob 为 LF，工作树为 CRLF。只在内存把 corpus CRLF 规范化为 LF 后，hash 与旧 baseline 的 corpus fingerprint 相同；没有改文件。

同时按 `rag_source_fingerprint()` 的同一算法对 `git show HEAD:<source>` 原始 blob 做 hash，结果为 `55380e4b5c87fd8a9fa053eff1c48aa04b05c5a18948ff1bc930811356aa9cf4`，与 baseline 保存的 `28741025b746620adb0324dfd9e9c484102244f833a542bce37f82d09b08d7f8` 不同。因此源码身份不匹配不只是换行问题，HEAD 与 committed baseline 本身也有差异。S1 没有修改被 hash 的任何生产源文件。

在另一次原生 `score --baseline evals/rag/baseline_v1.json` 比较时应预期拒绝；不要加 mismatch override 伪装成功。后续须作为独立仓库维护问题审查源码变化并按规定重建 baseline，而非 S1 覆盖现有资产。

## 3. 未运行的真实环境及指标

- 项目 `.env` 不存在；当前进程没有 `ARK_API_KEY`、DATABASE_URL、REDIS_URL 等显式运行配置；
- `docker ps` 失败：Docker Desktop Linux daemon pipe 不存在；
- 未提供可确认隔离的 PostgreSQL/Redis/Milvus、Embedding 固定 revision 缓存和可用 Model Profiles；未用默认地址尝试访问共享服务；
- 当前全局 Python 缺 Alembic 且存在模型 SDK 依赖版本冲突，不能用于正式 live profile；
- 不存在真实 Document/Version/Index Manifest、模型/索引 profile identity 或企业 Observation。

因此 Document Recall@5、MRR@10、企业问答正确率、题型通过率、Live P50/P95、错误分布、Token/成本均为“未测”，不填 0 或理想值。即使后续 CLI 检索运行成功，仅名称 Gold 的 Dataset 也没有 Chunk MRR/nDCG；需要真实索引后建立 Gold Chunk mapping。CLI 不生成答案 Judge；答案质量应使用原有持久 Evaluation Worker。

## 4. 后续 Live baseline 操作（本阶段未执行）

### 4.1 准备隔离环境

使用独立 Compose project、数据库、Milvus collection、Redis prefix、上传目录以及评测 Tenant。参照 `docs/runbooks/deployment.md` 和 `persistent-indexing-worker.md` 配置 PostgreSQL/Redis/Milvus、固定 Embedding model revision、模型及服务端 Secret；完成迁移并启动 API/Indexing Worker/Evaluation Worker。API 与 Indexing Worker 的 DOCUMENT_PARSER_VERSION、DOCUMENT_CHUNKER_VERSION、Embedding、INDEX_VERSION 必须一致，保留原始 parser 的配置。

模型/API 使用现有正式配置；Secret 通过用户的环境/密钥管理器提供，不写进本文或报告。Live 必须由操作者确认已有 API 的使用和预算。RAG 查询按 Tenant 检索快照，而 CLI 不提供选择 KB 的参数；仅新建一个 KB 并不能证明隔离，因此该评测 Tenant/实例不能混入其他可检索文档。

### 4.2 只上传 allowlist

从仓库根目录在已登录管理员的同源前端使用文档管理上传 `manifest.ingestion_allowlist` 中的 12 个文件。若以 HTTP 自动化，调用的是实际存在的 `POST /documents/upload/async`（multipart 的字段为 `file`，不是 `/v1/documents/upload`）；按每次响应的 job_id 查询 `GET /documents/upload/jobs/{job_id}`，等待 completed。下面是用户可在已有内存 Access Token 后运行的 PowerShell 示例，本次未执行：

```powershell
$taskBaseUrl = 'http://127.0.0.1:8000'
# $taskAccessToken 由当前管理员登录取得；不写入磁盘/报告。
$taskHeaders = @{ Authorization = 'Bearer ' + $taskAccessToken }
$taskAssets = (Resolve-Path 'evals/rag/synthetic_enterprise').Path
$taskManifest = Get-Content -Raw "$taskAssets/manifest.json" | ConvertFrom-Json
foreach ($taskRelativeFile in $taskManifest.ingestion_allowlist) {
    $taskUploadFile = Join-Path $taskAssets $taskRelativeFile
    $taskUpload = Invoke-RestMethod -Method Post -Uri "$taskBaseUrl/documents/upload/async" -Headers $taskHeaders -Form @{ file = Get-Item -LiteralPath $taskUploadFile }
    $taskUpload | Select-Object job_id, document_id, document_version_id, filename
}
```

`Invoke-RestMethod -Form` 要求 PowerShell 7；Windows PowerShell 5.1 使用原有网页上传。不要递归上传 asset root。把每个文件返回的 Document/Version ID 与 `manifest.documents` 关联，保存在 `.artifacts/synthetic-enterprise/`。查询 `/documents` 核对全部 current READY、文件名、版本、build fingerprint、parser/chunker/model/index/collection。失败 Job 保留错误类型，不能跳过失败文档宣称已成功构建 12 份索引。

### 4.3 原生 CLI 检索 baseline

在专用进程和同一个已配置评测环境中先获得真实 Catalog index ID：

```powershell
python -c "from backend.env import load_env; load_env(); from backend.core.settings import get_settings; from backend.documents.retrieval import DocumentRetrievalScope; print(DocumentRetrievalScope().resolve(tenant_id=get_settings().app.default_tenant_id).index_id)"
```

这个 ID 是真实检索快照的 index identity，不能用任意 collection 名或臆造的 `index-v1` 替代。记录 Case 执行期间 Catalog 不变，独立进程只执行一个 profile。使用实际输出设置 `$taskIndexId`，并使用显式的实验 profile label `$taskProfileId`：

```powershell
$taskProfileId = 'nebula-original-dev-v1'
# $taskIndexId = 上一个命令的实际结果
python scripts/evaluate_rag.py run --dataset evals/rag/synthetic_enterprise/dataset_dev_v1.json --corpus-path evals/rag/synthetic_enterprise/upload_corpus --gates evals/rag/live_gates_v1.json --observations .artifacts/synthetic-enterprise/original-dev-observations.json --report .artifacts/synthetic-enterprise/original-dev-report.json --markdown .artifacts/synthetic-enterprise/original-dev-report.md --profile-id $taskProfileId --index-id $taskIndexId --timeout-seconds 60
```

仅运行 20 开发 Case。现有 Live Gate 含必须有 eligible Gold Chunk、complexity 等要求，本数据集 S1 尚不满足；报告可能/应标门禁未通过，不能删门禁或声称发布通过。这里没有传 `--fail-on-regression`，目的是生成探索报告并审阅缺测指标，必须检查 JSON 中 `passed` 和 gate status。Native k_values 已含 5/10，Document Recall@5、outcome、duration 和标签 slice 会从真实 Observation 计算；MRR@10、gold_chunk_coverage 等缺测保留缺测。

CLI 报告会绑定 corpus/profile/source/index fingerprint，但不会给出生成答案、Judge、Token 消耗和成本；不得把 Graph 的 context 当成最终答案评测。原始 baseline 不覆盖 `evals/rag/baseline_v1.json`。

### 4.4 原有持久 Evaluation Job 的答案 baseline

更适合实际问答质量的是管理员 RAG 评估工作台：只导入 `dataset_dev_v1.json`，配置 Answer/Fast/Grader/Evaluator 全部角色，创建 Job，由 Evaluation Worker 完成答案与 Judge。真实 API 为：

```http
POST /v1/rag-evaluations/datasets
{"dataset": <dataset_dev_v1.json 的 JSON 对象>}

POST /v1/rag-evaluations/jobs
{"dataset_id": "<实际返回的 ID>"}

GET /v1/rag-evaluations/jobs/<job_id>
GET /v1/rag-evaluations/jobs/<job_id>/cases
```

以上请求都要求管理员 Access Token；示例对象占位符需替换为实际 JSON。无需修改 API Contract。默认 `RagEvaluationService` Gate 使用 k_values=(5,10)、live_rag provenance 和 case_pass_rate，但仍应单独审阅 recall、Judge 和失败切片。保存冻结 Model Snapshot/catalog hash、实际 index/corpus/source identity、每 Case 的安全 Observation/Judge/错误/耗时以及正式 Report。用户界面的导出/响应保存至 `.artifacts/`；不把 Secret、文档全文或私有推理写入实验报告。未提供 usage/价格字段的路径就把成本标为未测。

## 5. S2 接续

S2 直接复用生成 XLSX 和辅助 GT。先选择 leaf/parent provenance 的持久路径，再实现受控 Excel parser；当前 ParentChunk 无 JSON metadata，Milvus dynamic fields 虽已开启但 writer/reader/schema 投影尚未贯通。不要在 S1 预先实现这些更改。

S2 保持同一语料、固定开发集与 HTML 投影，创建新 parser/chunker BuildProfile、候选 Version 与 index identity，经 exact manifest/CAS 发布。S3 负责引用传递与展示，S4 才运行 60 冻结 Case 的 A/B。A/B index/source fingerprint 变化要在辅助实验报告显式说明，不能称同 provenance 的 CI baseline regression。人工复核清单当前待本人检查。
