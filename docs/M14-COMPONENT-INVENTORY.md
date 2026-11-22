# M14-B：Radar 现有能力与开源组件资产盘点

> 盘点日期：2026-11-22  
> 分支：`feat/requirement-driven-discovery`  
> 范围：Radar 当前代码、测试、架构文档、行业 Pack、研究资料，以及首轮外部开源候选。  
> 状态：仓库盘点完成；候选技术预筛选完成；真实样本基准进入 M14-C。

## 1. 盘点原则

本盘点不按 GitHub Stars 排序，也不把“仓库有代码”当成唯一价值标准。资产分为：

- **可直接复用的实现**：已有代码、测试、稳定契约。
- **知识资产**：架构文档、领域语义、研究结论、样本和操作手册。
- **外部候选**：可能补足缺口的开源组件。
- **待验证缺口**：当前能力边界，不能被候选宣传材料替代。

每项外部资产都要记录：解决的问题、真实文档/接口证据、许可证、版本与 Python 兼容、依赖规模、可离线性、定位保真、风险和实测计划。

## 2. Radar 仓库内已有能力

| 领域 | 现有实现 | 已有测试/证据 | 已知缺口 | 组件策略 |
|---|---|---|---|---|
| Office 文档 | `radar/document_parser.py`：stdlib ZIP/XML 解析 DOCX/XLSX/PPTX | `tests/test_document_parser.py` | 不支持 PDF/旧版 Office；DOCX 页眉页脚/脚注/批注/文本框未完整覆盖；XLSX 公式/样式/合并区域/隐藏 Sheet 语义不足；PPTX 备注/图表/SmartArt 不足；ZIP bomb/超大 XML 限制需强化 | 保留当前轻量解析作 fallback；评估成熟解析器补复杂格式 |
| CSV | 同一模块用 csv 提取行/列/表头定位 | 同上 | delimiter 检测简单；编码、引号、多行字段、异常行与大文件处理需要基准 | 当前实现作为 baseline，必要时只引入流式/格式辅助库 |
| PDF | 无 PDF 解析器 | 测试明确将 PDF 标为 unsupported | 页码、阅读顺序、多栏、表格、扫描件、旋转页和区域定位全部缺失 | 本轮重点评估 pypdf / pdfplumber / pypdfium2 / Docling |
| Python 静态分析 | `radar/code_analyzer.py` 用 ast 提取 import 和有限状态转换 | `tests/test_code_analyzer.py` | 只支持 Python；不完整导入解析、跨模块调用图、条件分支/赋值模式和动态行为 | 保留 AST 作为 Python 精确基线；Tree-sitter 用于多语言语法层，不替代业务语义 |
| 来源适配 | `radar/adapters.py`、GitHub/Gitee discovery | 对应 adapter/discovery tests | GitHub/Gitee 的评论、review、CI Checks 和分页覆盖仍有缺口；当前 GitHub 搜索主要是 metadata | API 适配层继续自研；HTTP/retry 可评估成熟依赖 |
| Web 抽取 | `radar/web.py`、`radar/fetch.py` | Web/quote tests | 动态页面、登录态、PDF 和附件解析不足 | 不把浏览器自动化框架塞进 Core；可选独立工具 |
| Evidence/Discovery | Asset、Evidence、Relationship、Discovery Store/Workspace | discovery/workspace tests | 多格式解析输出仍需统一 locator 和来源校验 | Adapter 输出归一化由 Radar 自研 |
| 业务观察值 | `business_observation_extractor.py`、`observation_aggregator.py` | 对应 tests | 自动跨文档业务对象关联和验收映射不足 | 不引入通用 NLP 框架替代行业规则 |
| Ledger/业务控制 | `ledger_effects.py`、`ledger_vouchers.py`、`ledger_aggregator.py`、`ledger_reconciliation.py`、`ledger_control_pipeline.py`、`ledger_workspace.py` | 对应 tests、D03 case | ERP 来源 Adapter、抽取完整性证明、真实 ERP 数据验证和 Assessment 闭环不足 | 领域规范与业务裁决由 Radar 自研；成熟格式解析/连接器可复用 |
| Business Graph | `business_graph.py` | graph tests / docs | 当前是可重建投影，非高性能图数据库 | 暂不引入图数据库，先测现有查询规模 |

## 3. 高价值内部知识资产

| 资产 | 类型 | 可复用价值 | 不能误读为 |
|---|---|---|---|
| `docs/architecture/transaction-ledger-semantics.md` | 领域架构 | 业务单据、库存/GL 流水和冲销语义 | 通用解析器实现 |
| `docs/architecture/ledger-workspace.md` | 架构/信任边界 | Workspace Ledger Records、Evidence 绑定与 Pack opt-in | ERP Adapter 已完成 |
| `docs/cases/D03-MATERIAL-PROCUREMENT.md` | 真实业务案例定义 | 采购、收货、质检、调拨、退料、成本的端到端验收场景 | 真实 ERP 运行数据 |
| `examples/requirements/d03-material-procurement.json` | 需求知识资产 | 需求级验收条件、invariant 引用 | Evidence 已经存在 |
| `docs/context/PRIOR-ART.md` | 研究资料 | 先例分类和产品边界 | 专利/学术系统查新结论 |
| `docs/context/RADAR-NOTES.md` | 产品/架构笔记 | 产品方向与历史设计决策 | 现行代码契约，需与代码交叉验证 |
| `docs/context/weak-current-probe.md` | 行业研究记录 | 弱电行业领域词汇和线索 | 已验证的业务事实 |

**关键结论：** Radar 的高价值资产不仅是 Python 代码。D03 案例、Ledger 语义、行业 Pack、研究笔记和定位规则对未来组件接入同样重要。第三方解析器不能替代这些知识资产。

## 4. 外部候选比较：PDF 解析

截至 2026-11-22 的公开项目元数据预筛选：

| 候选 | 当前可核实版本/要求 | 许可证 | 优势 | 风险与定位 |
|---|---|---|---|---|
| pypdf | 6.21.4：Python >=3.9；7.1.1：Python >=3.10 | BSD-3-Clause | 纯 Python，适合基础 PDF 文本/元数据抽取；版本发布和安全修复活跃 | 版本升级会抬高 Python 下限；复杂表格/阅读顺序/坐标需实测 |
| pdfplumber | 0.11.11；Python >=3.8，项目说明当前测试 3.10–3.14 | MIT | 提供字符、线条、矩形、表格和可视化调试，定位信息丰富 | 基于 pdfminer.six，依赖链比 pypdf 重；更适合机器生成 PDF，不提供 OCR；当前发布缺少 PyPI provenance |
| pypdfium2 | 5.15.2；Python >=3.6 | Apache-2.0 / BSD-3-Clause，另含 PDFium 和依赖许可证 | 原生 PDFium 能力，支持渲染、检查和文本相关操作；覆盖多个平台 | wheel 包含原生二进制，平台/架构与随附许可证要审计；不是纯 Python |
| Docling | 2.151.1 / docling-slim；Python >=3.10 | MIT | 统一 PDF、DOCX、HTML 等复杂文档解析，面向结构化下游 | 依赖 docling-core、Pydantic、Pandas、Pillow、PyYAML、Typer 等；模型/缓存/网络和资源成本较高，只能 L2 |
| PyMuPDF | 持续维护 | AGPL 或商业许可 | PDF 布局、渲染、速度和操作能力较强 | AGPL/商业许可风险，暂缓，未完成法务判断不得纳入默认依赖 |

### PDF 预筛选结论

不立即选定单一赢家，M14-C 采用同一份授权样本集对比：

1. pypdf：基础文本和元数据基线。
2. pdfplumber：字符/坐标/表格抽取候选。
3. pypdfium2：原生渲染与文本提取候选。
4. Docling：复杂文档结构解析候选，单独测安装和模型成本。

pypdf 7.1.1 不能直接用于当前 Python 3.9 Core；如测试 7.x，应放入 Python 3.10+ 的隔离任务。6.21.4 是当前已查到支持 Python 3.9 的候选版本，但需评估安全维护与升级路径，不能据此直接批准接入。

## 5. 外部候选比较：代码语法分析

| 候选 | 公开元数据 | 优势 | 风险 |
|---|---|---|---|
| Python ast | Python 标准库 | 零额外依赖，当前 Python 分析结果可精确定位 | 仅 Python；动态调用、跨模块关系和其他语言不支持 |
| tree-sitter 0.26.1 + individual grammar wheels | Core binding MIT、Python >=3.10；本次测试 Python/JS/Go grammar 0.25.0、Java 0.23.5，均为 MIT | 明确选择语言 grammar；不需要运行时自动下载 | 需要多个独立包；每个 grammar 单独锁版本、许可证和供应链；Python 3.9 不兼容当前 binding |
| tree-sitter-language-pack 1.25.2 | MIT；Python >=3.11 | 一体化提供大量语言 grammar | 首次使用可自动下载 parser；离线需预下载缓存；Python 下限更高；不作为本次首选方案 |

**结论：** 不替换现有 Python AST。Tree-sitter 的目标是给 JavaScript/TypeScript、Java、Go 等语言提供语法结构和精确位置。业务状态机、业务对象关系和不变量仍由 Radar 自己解释。当前候选更适合隔离 L2 运行环境。

### Tree-sitter 合成多语言实测（GitHub Actions，2026-11-22）

使用 `tree-sitter==0.26.1`，以及独立 grammar wheels：Python 0.25.0、JavaScript 0.25.0、Java 0.23.5、Go 0.25.0，在 Python 3.10.22 环境运行。四种语言均满足：

- 正常样本根节点无语法错误；
- 预期 import / class / function / method / type 节点全部找到；
- 每个节点保留 0-based 行列和 UTF-8 byte range；
- 四个故意损坏的语法样本均被标记为有语法错误。

单次解析耗时（仅作可运行性记录，不作性能排名）：Python 0.0001084 s、JavaScript 0.0000869 s、Java 0.0000669 s、Go 0.0000741 s。Python AST baseline 同时从同一份 Python 样本识别出 1 个 import 和 1 个状态转换候选。

**阶段结论：** Tree-sitter 已证明可以用五个 MIT 包的组合提供 Python、JavaScript、Java、Go 的语法树和精确位置。它解决的是多语言语法结构缺口；Radar Python AST 已识别的显式状态转换仍属于更高层语义。不能把 Tree-sitter 节点本身当成业务流程事实。

限制：样本是人工构造的短代码，未覆盖真实仓库、相对导入、跨文件引用、宏/生成代码、不同语言版本、复杂错误恢复和增量解析。Python 3.10 是当前依赖组合最低可用基线，不能因此把 Radar Core 最低版本提升到 3.10。

## 6. 外部候选比较：检索与知识处理

### SQLite FTS5

- Python `sqlite3` 可直接使用，不增加第三方 Python 包。
- FTS5 是否可用取决于运行时 SQLite 编译选项；必须通过真实 `CREATE VIRTUAL TABLE ... USING fts5` 探测，不能只假设已启用。
- 默认 tokenizer 对中文连续文本的分词效果有限；中文搜索需要专门测试 tokenizer/预分词方案。
- 首选做本机、离线、可重建索引基线。

#### FTS5 小型可行性探针（非 Radar CI 基准）

在本次执行环境（Python 3.13.5 / SQLite 3.46.1）进行内存数据库探针：

- `CREATE VIRTUAL TABLE ... USING fts5` 成功，说明该运行时具备 FTS5。
- 默认 `unicode61` tokenizer 能命中完整词串“采购订单”，但对连续中文中的子词“采购”“订单”均未命中。
- 将中文按二元字切分后写入 FTS5，以上二字查询均可命中；但这只是一个极小人工字符串探针，不代表召回率、排序质量或生产性能。
- `trigram` tokenizer 在此例中同样不能命中二字查询。

**阶段判断：** FTS5 可作为轻量索引后端候选，但中文检索需要明确的预分词/二元切分策略，并与同义词词典、精确词组和误召回率一起评估。不同操作系统/发行版的 SQLite 构建仍需在 CI 和用户目标环境探测；本次探针不是项目 Python 3.9/3.x 双环境验证。

#### PDF 候选合成样本实测（GitHub Actions，2026-11-22）

基于 `.github/workflows/component-benchmarks.yml`，分别在隔离环境安装候选包。固定生成 3 页 PDF（中文正文、业务单号、带网格表格、双栏说明），所有候选都匹配 14/14 条预期文本短语。

| 候选 | Python | 单次解析耗时 | 文本短语召回 | 字符几何定位 | 表格结构 | 双栏列顺序 |
|---|---:|---:|---:|---|---|---|
| pypdf 6.21.4 | 3.9.25 | 0.073605 s | 1.00 | 本轮未提供/未测 | 无表格 API | 左列优先 |
| pypdf 7.1.1 | 3.13.18 | 0.224858 s | 1.00 | 本轮未提供/未测 | 无表格 API | 左列优先 |
| pdfplumber 0.11.11 | 3.13.18 | 0.114298 s | 1.00 | 可用 | 3×5 表格精确匹配 | 默认输出按横向行交错 |
| pypdfium2 5.15.2 | 3.9.25 | 0.079777 s | 可用 | 可用 | 本轮未测表格抽取 | 左列优先 |

解释和限制：

- 这证明四个候选都能处理这个合成文件，并且可以恢复所有人工设定的短语；**不证明真实 PDF 的生产准确率**。
- 单次耗时受冷启动、runner 负载和环境影响，不作为性能排名。需要多轮 warm-up、重复运行和真实页数基准。
- pdfplumber 是本次唯一通过表格 API 精确还原 15 个单元格的候选；它也暴露字符几何信息，但默认文本顺序在双栏样本中按行交错。
- pypdf / pypdfium2 在此样本上保留了左列优先的提取顺序；pypdfium2 可提供字符几何信息。pypdf 本轮仅测试普通文本抽取，未启用其 visitor 回调定位能力。
- pypdf 6.21.4 在 Python 3.9.25 可运行；7.1.1 在 Python 3.13.18 可运行。版本线不能无条件互换。
- 所有结果和 `pip freeze` 环境清单均作为 GitHub Actions artifacts 保存（30 天）。

**阶段结论：** 暂不选单一赢家。pypdf 适合作为轻量基础文本解析候选；pdfplumber 是表格/字符定位专用候选；pypdfium2 是可选原生渲染/几何定位候选。真实企业文档语料、扫描件/OCR、跨页表格和恶意 PDF 测试完成前，不批准进入 Radar 正式 Adapter 或默认安装。

基准流程本身也发现了依赖元数据陷阱：ReportLab 5.1.0 的 PyPI 元数据声明 Python >=3.9，但其运行时在 Python 3.9 拒绝导入并要求 3.10+；基准生成器因此固定到 ReportLab 4.5.1（Python 3.9+）。这说明不能只读 `Requires-Python`，必须在目标解释器中真实 import/运行。

### ScanCode Toolkit

- 官方文档支持 CLI、库和 JSON / SPDX / CSV 等输出。
- 可提取文件级许可证、版权声明、行号和依赖包信息。
- 更适合 L3 外部工具：隔离进程运行、记录版本和扫描配置，Radar 消费结构化结果。
- 必须分别审查 ScanCode 主程序、依赖、license rules、数据集和再分发条件；扫描结果只能是候选识别，仍需人工复核。

### OCR / 图像

- Tesseract 主项目 Apache-2.0，但语言训练数据和模型来源应分别审查。
- OCR 必须保留页码、区域坐标、置信度和原始图像引用。
- OCR 文本只能作为低置信候选 Evidence，不能自动变成 verified quote。
- 本轮不把 OCR 引入 Core。

## 7. 不能外包给第三方的核心能力

以下部分属于 Radar 的产品差异化和信任边界：

- Evidence 身份、来源、locator、asset 归属和可追溯校验。
- 需求条目级覆盖率、证据缺口和冲突识别。
- 业务对象、流程、状态、取消/冲销、重复单据等领域语义。
- 业务不变量和 Ledger Control 计算规则。
- Assessment 最终裁决与人工复核流程。
- 行业 Pack 的声明式知识和跨行业通用底座。

允许组件解析“采购订单号”字段，但订单是否满足需求、是否已审批、是否已收货，必须通过 Radar 的证据链和业务规则判定。

## 8. M14-C 基准数据集要求

目前仓库测试主要使用小型内联 ZIP/XML fixture 和 Python 代码字符串，能验证契约与边界，但不足以证明生产解析准确率。不能将单元测试通过表述成真实文档解析基准通过。

M14-C 需要创建有授权、可固定哈希的样本集，至少包括：

- PDF：原生文本、多栏、复杂表格、扫描件、旋转页、中文字体、页眉页脚、跨页表格。
- Office：DOCX 页眉页脚/表格/批注；XLSX 公式/合并单元格/隐藏 Sheet；PPTX 备注/图表。
- 代码：Python、TypeScript/JavaScript、Java、Go；含语法错误、相对导入、跨文件调用。
- 搜索：中文、英文、缩写、同义词、文件名、符号名、业务术语映射。
- 每个样本提供人工标注真值：文本、字段、页码/段落/Sheet/Cell/行列/代码行、表格结构和目标 Evidence。

每个文件记录来源、许可、SHA-256、样本类别、真值标注版本和复核人。没有授权的企业私有材料不得放入公开仓库；可用脱敏 fixture 或只存本地的测试数据。

## 9. 基准指标与通过门槛

| 指标 | 说明 |
|---|---|
| Parse success | 能否成功解析，失败必须显式报告 |
| Text recall / precision | 文本召回和噪声比例 |
| Locator accuracy | 页码、段落、Sheet/Cell、代码行定位正确率 |
| Table structure F1 | 表格行列/单元格结构保真 |
| Field extraction accuracy | 关键业务字段抽取准确率 |
| Search Recall@K / Precision@K / MRR | 检索召回与排序质量 |
| Throughput | 每千页/每千文件处理耗时 |
| Peak memory / artifact size | 峰值内存和安装/模型体积 |
| Offline pass rate | 无网络环境能否完成已缓存任务 |
| Failure isolation | 组件失败是否被标为 failed/unresolved 而非空成功 |

最低要求：不能只看平均准确率。关键字段和 locator 错误必须单独统计；任何无法保留来源定位的组件不能进入正式 Evidence Adapter。

## 10. 当前结论与待办

- 仓库现有 DOCX/XLSX/PPTX/CSV 和 Python AST 实现保留为 baseline，不立即替换。
- PDF 是最明显的解析能力空缺，应优先进入 M14-C。
- FTS5 先做无依赖能力探测和中文检索基准。
- Tree-sitter 先验证多语言价值，接受它可能只能在 Python 3.10+/3.11+ 的隔离环境运行。
- Docling 只进入重型可选解析器评估，不进入默认安装。
- ScanCode 和 OCR 先作为外部工具。
- 目前尚未有组件获得 L1/L2 正式接入批准；也尚未建立完整授权 PDF/Office/多语言代码语料，因此性能/准确率分数暂不填报。

## 11. M14-D 依赖管理与打包基线

- 新增 pyproject.toml：Python >=3.9、datongcfl-radar 包元数据、radar CLI entry point。
- 新增 uv.lock：由 uv 0.13.9 生成并在 CI 用 uv lock --check 验证；当前 Core 无第三方运行时依赖。
- setuptools 80.9.0 作为精确锁定的构建后端；uv 只作为开发/CI 环境工具，不进入 Radar 运行时依赖。
- Package smoke 在 Python 3.9 和 3.13 分别通过：Core 安装、radar / python -m radar CLI、254 项测试、wheel 与 sdist 构建。
- CI：[Package and dependency smoke](https://github.com/datongcfl/radar/actions/runs/44980531908)，[Radar tests](https://github.com/datongcfl/radar/actions/runs/44980531886)。
- pypdf、pdfplumber、pypdfium2、Tree-sitter 尚未加入正式 optional extras；对应 Adapter 和真实语料评估完成前不宣称已批准。

## 12. 参考资料（官方项目 / PyPI 元数据）

- pypdf 6.21.4（Python >=3.9，BSD-3-Clause）：https://pypi.org/project/pypdf/6.21.4/
- pypdf 7.1.1（Python >=3.10，BSD-3-Clause）：https://pypi.org/project/pypdf/7.1.1/
- pdfplumber 0.11.11（MIT，Python >=3.8）：https://pypi.org/project/pdfplumber/
- pypdfium2 5.15.2（Apache-2.0 / BSD-3-Clause 与依赖许可）：https://pypi.org/project/pypdfium2/5.15.2/
- Docling：https://github.com/docling-project/docling
- Docling package metadata：https://github.com/docling-project/docling/blob/main/pyproject.toml
- Tree-sitter Python binding：https://pypi.org/project/tree-sitter/0.26.1/
- Python grammar：https://pypi.org/project/tree-sitter-python/0.25.0/
- JavaScript grammar：https://pypi.org/project/tree-sitter-javascript/0.25.0/
- Java grammar：https://pypi.org/project/tree-sitter-java/0.23.5/
- Go grammar：https://pypi.org/project/tree-sitter-go/0.25.0/
- Tree-sitter language pack（Python >=3.11）：https://pypi.org/project/tree-sitter-language-pack/1.25.2/
- SQLite FTS5：https://www.sqlite.org/fts5.html
- Python sqlite3：https://docs.python.org/3/library/sqlite3.html
- ScanCode Toolkit：https://scancode-toolkit.readthedocs.io/en/stable/
- Tesseract license：https://github.com/tesseract-ocr/tesseract/blob/main/LICENSE

## 13. 变更记录

- 2026-11-22：完成仓库代码、测试、架构、行业 Pack 和研究资料盘点；建立 PDF、代码解析、检索、OCR、许可证扫描候选比较；明确 M14-C 基准数据集和指标。
- 2026-11-22：完成 SQLite FTS5 小型可行性探针；当前运行环境可用，但默认中文 tokenizer 不支持二字子词召回，预分词方案待真实语料验证。
- 2026-11-22：新增隔离 PDF 候选基准 workflow；pypdf 6.21.4 / 7.1.1、pdfplumber 0.11.11、pypdfium2 5.15.2 均通过合成样本解析，完整记录版本、定位能力、表格结果和限制。
- 2026-11-22：新增 Tree-sitter 多语言基准；Python、JavaScript、Java、Go grammar 全部通过语法节点、错误恢复和 locator 探针；当前组合要求 Python 3.10+。
- 2026-11-22：M14-D 打包基线完成；pyproject.toml、uv.lock、Core package smoke workflow 双 Python 版本通过，254 项测试通过并构建 wheel/sdist。
