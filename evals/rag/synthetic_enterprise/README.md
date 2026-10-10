# Nebula Industrial 合成企业评测资产

全部数据为星云智能科技有限公司（Nebula Industrial）的虚构测试数据，数据资产采用 CC0-1.0；生成器沿用仓库代码许可。本目录不证明真实企业上线或 RAG 效果提升。

## 从仓库根目录生成与校验

```powershell
python scripts/generate_synthetic_enterprise.py
python scripts/generate_synthetic_enterprise.py --check
python scripts/evaluate_rag.py validate --dataset evals/rag/synthetic_enterprise/dataset_v1.json
python -m pytest -q tests/test_synthetic_enterprise.py
```

锁定开发环境建议先执行 `uv sync --dev --locked`，再将上述 `python` 替换为 `uv run --no-sync python`。生成器只依赖原项目已有 openpyxl、Pydantic 和标准库，普通生成/测试不调用模型或联网。原生 HTML parser 回归测试还使用已有 BeautifulSoup；未安装时这 8 个测试会明确 skip。

默认 seed 为 `20261010`。源业务记录先确定性生成到 `source_records.json`，之后文档、参考答案和锚点均由同一份记录推导，不分别随机生成事实。固定日期、排序、XLSX XML 修改时间与 ZIP 时间保证相同环境下逐文件 SHA-256 一致；跨依赖版本复现应使用 `uv.lock`。重复生成对同内容文件不写入；有不同内容（包括人工改动）时，在任何写入前失败。修改 seed/生成规则请使用新 `--output` 目录，不覆盖已经冻结的 v1。

## 文件职责与索引边界

| 路径 | 内容 | 可上传知识库 |
| --- | --- | --- |
| `corpus/` | 4 XLSX + 8 Markdown，12 份逻辑业务文档 | 不直接用于原始版本批量上传 |
| `upload_corpus/` | 相同 4 XLSX + 8 HTML 投影 | 仅 manifest allowlist 中的这 12 个文件 |
| `source_records.json` | 200 产品、100 维修、历史参数与政策的唯一业务事实源 | 否 |
| `dataset_v1.json` | 原生 80 Case Dataset | 只导入 Evaluation，不导入 KB |
| `dataset_dev_v1.json` | 20 开发 Case | 只导入 Evaluation |
| `dataset_frozen_v1.json` | 60 冻结 Case | 留待 S4，禁止逐题调参 |
| `ground_truth.jsonl` | Case、来源锚点、参考答案与冲突预期 | 否 |
| `splits.json` | 固定、互斥的开发/冻结 Case ID | 否 |
| `manifest.json` | 全部生成资产 hash、文档身份映射、上传 allowlist | 否 |
| `manual_review.md` | 10 条待人工核对样本 | 否 |

原始上传校验与 `DocumentLoader.load_document` 不接受 `.md`。HTML 投影只将 Markdown 标题/段落转为 HTML，并使用现有正式 HTML parser；不新增生产解析器。每个 HTML 对应且仅对应一个 Markdown 逻辑文档，禁止同时上传两种格式。XLSX properties 与所有文本文件标明 SYNTHETIC DATA；Excel 第 1 行仍为业务表头，第 2 行起为数据。

严禁递归上传本目录。`manifest.ingestion_allowlist` 是唯一的批量上传清单，问题、标准答案和辅助 Ground Truth 不在该清单中。生成器也会拒绝 corpus/upload_corpus 中的额外文件。上传只有业务正文；文档内的业务事实并非评测标签泄露。

## 语料与问题规模

`product_specs.xlsx`、`product_prices.xlsx`、`inventory.xlsx` 分别有 200 数据行；`repair_records.xlsx` 有 100 数据行。型号均为 `NX-001` 至 `NX-200`，所有价格、库存和维修通过型号关联。8 份 Markdown 分别为使用说明、售后政策、保修规则、FAQ、技术规范、更新公告、故障处理、选型指南。

简单事实/表格查询比较/跨文档/无答案/版本政策各为 20/20/20/10/10 条；开发集各 5/5/5/3/2，冻结集各 15/15/15/7/8。功率比较只确定性比较两个数值；不要求统计或 ERP 实时同步。五个型号有明确硬件 1.0/2.0 功率变化；2025 与 2026 保修政策按购买日期区分。不存在随机无解矛盾。无答案题使用不存在的 NX-901 至 NX-910。

## 原生契约映射

`RagEvalDataset`/`RagEvalCase` 保持 schema v1：`id`、`tags`、`question`、`expected`、`gold_documents`、`reference_answer`、`required_claims`、`conflicts`。Gold Document 使用实际上传 XLSX/HTML 的 `canonical_name`；不把 `nebula:*` 来源标识冒充数据库 `document_id`。Gold Chunk 暂为空；Sheet/物理行/章节锚点保存在独立 Ground Truth。真实版本、Chunk ID、内容 hash 必须在索引完成后，从 Catalog/Manifest 和实际解析结果建立映射，不能预造。

原生 CLI Live Adapter 观察检索图，不生成答案/Judge；Document Recall@5、outcome、延迟等可由实际 Observation 获得。MRR@10 是 Chunk 指标，当前没有真实 Gold Chunk，不能声称已计算。答案 correctness 等需原有持久 Evaluation Job 的 Answer/Evaluator。详细操作及条件见 [S1 基线说明](../../../docs/second-dev/s1-evaluation-baseline.md)，来源设计见 [S1 数据设计](../../../docs/second-dev/s1-data-design.md)。

## S2 使用

直接使用 `corpus/*.xlsx` 作为单行表头 fixture，物理行从 2 开始。让正式 Excel parser 输出的 sheet/row 与 Ground Truth 对齐；本目录的锚点只供测试，不是已实现的运行时 provenance。旧 baseline 继续使用 `upload_corpus` 的文件名。若 S2 改变 parser/chunker，应产生新的 BuildProfile 和不可变 Document Version，不原地改旧版本。Markdown/HTML 转换策略在 A/B 两侧必须一致。
