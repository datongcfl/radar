# Radar 开源组件选型与依赖治理策略

> 状态：M14-A 已批准策略 / M14-B、M14-C、M14-D 进行中  
> 适用范围：Radar 通用核心、来源适配器、文档解析器、代码分析器、搜索与索引、知识存储、可选 Agent 集成。  
> 本文件定义准入规则和候选评估记录，不代表候选组件已获准接入。

## 1. 目标与基本原则

Radar 不再把“核心必须零依赖”作为不可变约束。正式采用：

**核心轻依赖、能力模块可扩展、行业 Pack 不绑定运行时。**

目标：

- 用成熟组件补足非差异化基础能力，避免重复造轮子。
- 让流水线更容易构建、测试、运行和维护。
- 保护 Radar 自己的核心模型、Evidence/Asset 溯源、Pack 契约和跨模型可移植性。
- 让重型、可选、具有平台或许可证约束的能力可以单独安装、独立运行和替换。
- 对每次引入建立可复现的准确率、性能、资源占用和许可证审计记录。

不以零依赖为教条，也不走“为了方便把所有库都装进来”的另一个极端。是否引入依赖必须由真实需求和总成本决定。

## 2. 组件分层与依赖策略

| 层级 | 定义 | 依赖策略 | 典型能力 |
|---|---|---|---|
| L1 Core | 核心数据模型、Evidence、规则、Workspace、CLI、基础流水线 | 允许少量成熟依赖进入默认安装；必须证明收益，严格审查 | 稳定格式处理、基础索引、通用数据结构 |
| L2 Optional capability | 并非所有用户都需要的能力 | 通过 optional extra / 插件组按需安装 | PDF/Office 深度解析、多语言语法分析、OCR |
| L3 External tool | 重型、平台相关或适合独立运行的工具 | 独立 CLI/子进程/容器，不强迫所有用户安装 | ScanCode、Tesseract、LibreOffice |
| L4 External service | 用户自托管或云端服务 | 用户显式配置，最小权限、清晰数据边界 | 搜索服务、向量服务、企业知识源 |
| Pack | 行业知识、字段别名、业务规则和映射 | 保持声明式数据，不绑定特定运行时 | 弱电、数据中心、宠物医院等行业知识 |

L1 并非“依赖越少越好”，而是“依赖的工程收益必须高于长期维护成本”。L2/L3 的失败不得破坏 Core 的基础功能。

## 3. Radar 必须自研与可以复用的边界

### Radar 必须掌握

- Asset、Evidence、Relationship、Observation 等统一数据契约。
- Evidence 的身份、来源、定位、版本与可信度边界。
- 需求条目到 Evidence 的映射、覆盖缺口和追溯关系。
- 业务对象、流程、状态、不变量和行业规则。
- Assessment 的裁决规则与最终验收结论。
- Adapter 失败、部分解析、来源不可访问时的 unresolved / degraded 状态。

### 优先复用成熟组件

- PDF、Office、HTML、图片等格式解析。
- 多语言语法树、符号和基础代码结构分析。
- 全文索引、查询执行、压缩和基础存储。
- OCR、格式转换、许可证扫描、SBOM。
- 通用网络协议、重试、限流、缓存和序列化工具。

第三方组件只能提供技术观察结果。例如解析器可以指出 PDF 第 12 页出现采购条款，但不能决定该条款是否满足需求验收条件。

## 4. 当前仓库基线与迁移约束

截至 M14-A，仓库 README 声明 Python 3.9+、离线可运行；CI 覆盖 Python 3.9 和当前 Python 3.x。核心目前大量使用标准库。仓库尚未发现 pyproject.toml、setup.py 或 requirements.txt 等统一 Python 包依赖声明入口。

因此：

1. 不再要求未来 Core 永远 stdlib-only；允许通过本文件准入的少量 L1 依赖。
2. 在包管理、依赖声明、版本锁定和 CI 安装流程建立前，不得零散增加运行时第三方导入。
3. 保持 Python 3.9 兼容作为当前基线。需要 Python 3.10+ 的能力只能先放入隔离的 L2 环境，不得抬高 Core 最低版本。
4. 可选依赖必须延迟导入；未安装时给出可操作提示，不能导致基础 CLI import 失败。
5. 新依赖不得破坏离线运行、旧命令、基础 Pack 校验和现有 Workspace。
6. 组件输出必须归一化到 Radar 自己的 Asset、Evidence、Relationship、Observation 等契约，保留原始定位和来源版本。
7. 任何组件都不能自行把候选证据升级为已验证事实或需求验收通过。

## 5. 统一准入流程

每个候选必须经过以下步骤，缺一不可：

1. **需求证明**：指出现有 Radar 能力的具体缺口、真实输入样本和失败案例。
2. **候选发现**：至少比较两个可行方案；若只有一个候选，记录原因和替代方案。
3. **许可证审查**：分别审查代码、传递依赖、模型权重、训练数据、规则库和示例数据的许可证。
4. **技术适配**：确认 Python 版本、OS/架构、离线运行、网络行为、外部二进制、模型下载及资源要求。
5. **隔离原型**：通过 Adapter 接入，不把供应商类型泄漏到核心模型。
6. **基准测试**：在固定样本集上比较准确率、定位完整性、吞吐、延迟、内存、磁盘和安装体积。
7. **安全审查**：检查文件解析攻击面、解压炸弹、XML 外部实体、命令注入、网络请求、临时文件和权限。
8. **决策记录**：记录 Accept / Optional / Hold / Reject，批准层级、版本范围、许可证依据和复审日期。
9. **持续治理**：锁定版本和哈希，跟踪 CVE、上游维护、许可证变化和弃用通知。

## 6. 评分模型

通过硬性门槛后再评分，满分 100：

| 维度 | 权重 | 评价重点 |
|---|---:|---|
| 需求匹配度 | 20 | 是否解决已证实的 Radar 缺口 |
| 证据定位与结构保真 | 15 | 页码、段落、Sheet/Cell、行列、代码行和坐标是否保留 |
| 许可证与再分发适配 | 15 | 核心/插件/服务模式是否可合法使用和分发 |
| 技术兼容性 | 10 | Python、OS、架构、离线和私有化能力 |
| 准确率与鲁棒性 | 10 | 复杂文档、错误输入、恶意输入和边界情况 |
| 性能与资源 | 10 | 吞吐、延迟、内存、磁盘、模型体积 |
| 维护与安全 | 10 | 维护活跃度、发布节奏、漏洞响应和供应链 |
| 可替换性 | 5 | 是否能被适配器封装、是否锁定专有数据结构 |
| 运维成本 | 5 | 安装、升级、部署、排障和用户学习成本 |

建议解释：85+ 可进入接入评审；70–84 只允许可选试点；低于 70 暂缓。许可证、安全、数据主权或兼容性硬门槛失败时，不因总分高而放行。

## 7. 硬性否决与风险门槛

- 许可证不明、组件或模型权重无法确认再分发条件：Hold，不进入发布依赖。
- 强 copyleft 或商业限制可能影响 Radar 分发方式：必须经项目治理确认，不得默认进入 L1。
- 需要未经用户同意上传私有代码、文档或观察值：Reject。
- 不可保留 Evidence 定位或无法区分原始文本与模型推断：不得承担正式证据提取职责。
- 解析过程可能执行文档宏、脚本或任意代码：默认禁止；必须在沙箱中验证。
- 安装或运行失败会影响旧命令、离线模式或基础 Pack 校验：Reject。
- 组件依赖模型或数据集时，模型/数据许可证必须独立审查，不能只看 Python 包许可证。

## 8. 首轮候选清单（初步判断，尚未批准接入）

| 能力 | 候选 | 初步判断 | 主要约束 / 下一步 |
|---|---|---|---|
| 全文检索 | SQLite FTS5（Python sqlite3） | 优先做无新增依赖的基线试验 | 目标环境 SQLite 是否编译启用 FTS5；中文分词与同义词需要独立评估 |
| PDF 基础文本 | pypdf 6.21.4 / 7.1.1 | 轻量候选，但版本线需拆分 | 6.21.4 支持 Python 3.9；7.1.1 要求 Python 3.10+；BSD-3-Clause；评估旧版本维护与安全回补 |
| PDF 表格/布局 | pdfplumber 0.11.11 | 高价值可选候选 | MIT、Python >=3.8；基于 pdfminer.six，需测复杂表格和坐标保真；上游当前测试矩阵从 3.10 起 |
| PDF 渲染/文本 | pypdfium2 5.15.2 | 可选候选 | Python >=3.6；Apache-2.0/BSD-3-Clause 及 PDFium/随附依赖许可；包含原生二进制，需审查各平台构建与二进制供应链 |
| 文档智能解析 | Docling 2.151.1 / docling-slim | 高价值 L2 插件候选 | MIT；Python >=3.10；docling-core 当前依赖包含 Pydantic、Pandas、Pillow、PyYAML、Typer 等；模型/下载与安装体积必须实测 |
| 多语言代码解析 | tree-sitter 0.26.1 + individual grammar wheels | L2 候选，已完成 Python/JS/Java/Go 合成语法探针 | Core binding MIT、Python >=3.10；当前 grammar 包均 MIT；逐个 grammar 锁版本并审查供应链；language-pack 1.25.2 需 Python >=3.11 且首次使用可能下载 parser |
| PDF 高性能/布局 | PyMuPDF | 暂缓 / 法务审查 | AGPL 或商业许可路径；许可证结论前不得纳入默认安装 |
| 许可证与 SBOM | ScanCode Toolkit | L3 外部工具候选 | 扫描深度较强，适合独立 CLI/服务；包、规则库、数据集和依赖许可证分别审查 |
| OCR | Tesseract / Docling OCR pipeline | 后续对比 | 语言包、二进制、模型权重和识别准确率分别评估；必须保留页码和区域坐标 |
| 图数据库 | 暂不选型 | 先不引入 | 当前 Business Graph 是可重建投影；只有查询规模和图算法证明现有存储不足时再评估 |

### 8.1 初步事实与官方资料

- SQLite FTS5 是 SQLite 的全文检索虚拟表模块；是否可用需在目标 Python/SQLite 构建中检测。  
  https://www.sqlite.org/fts5.html
- pypdf 6.21.4 的 PyPI 元数据显示 Python >=3.9、BSD-3-Clause；7.1.1 要求 Python >=3.10。版本升级不能忽略最低 Python 版本变化。  
  https://pypi.org/project/pypdf/6.21.4/  
  https://pypi.org/project/pypdf/7.1.1/
- pdfplumber 0.11.11 为 MIT、Python >=3.8，定位于字符/线条/矩形与表格抽取，基于 pdfminer.six；官方说明更适合机器生成 PDF，不提供 OCR。  
  https://pypi.org/project/pdfplumber/  
  https://github.com/jsvine/pdfplumber
- pypdfium2 5.15.2 的 PyPI 元数据显示 Python >=3.6，项目采用 Apache-2.0/BSD-3-Clause，包含 PDFium 原生二进制及其依赖许可；平台覆盖和二进制再分发需要单独审查。  
  https://pypi.org/project/pypdfium2/5.15.2/
- Docling 提供 PDF、Office、HTML、图像等结构化解析，MIT；当前要求 Python 3.10+，并有模型/深度学习依赖。  
  https://github.com/docling-project/docling  
  https://github.com/docling-project/docling/blob/main/pyproject.toml
- Tree-sitter Python binding 0.26.1 为 MIT、Python >=3.10；本轮实际使用的 Python/JavaScript/Go grammar 0.25.0 和 Java grammar 0.23.5 均为 MIT，需分别锁定。  
  https://pypi.org/project/tree-sitter/0.26.1/  
  https://pypi.org/project/tree-sitter-python/0.25.0/  
  https://pypi.org/project/tree-sitter-javascript/0.25.0/  
  https://pypi.org/project/tree-sitter-java/0.23.5/  
  https://pypi.org/project/tree-sitter-go/0.25.0/  
- tree-sitter-language-pack 1.25.2 为 MIT、Python >=3.11，首次使用可自动下载 grammar，离线部署需预下载；本轮未选它作为基准依赖组合。  
  https://pypi.org/project/tree-sitter-language-pack/1.25.2/  
  https://github.com/tree-sitter/tree-sitter
- PyMuPDF 的上游许可说明包含 AGPL 与商业许可选项。  
  https://pymupdf.readthedocs.io/en/latest/about.html
- ScanCode 可通过 CLI 或库扫描许可证、版权和依赖；许可证和数据资产需分层核查。  
  https://scancode-toolkit.readthedocs.io/en/stable/  
  https://pypi.org/project/scancode-toolkit/

## 9. 基准测试要求

所有解析/检索组件必须使用同一套固定、可再分发或明确授权的样本集。初版样本至少覆盖：

- PDF：可搜索文本、多栏、表格、扫描件、旋转页、页眉页脚、中文字体。
- Office：DOCX 表格、页眉页脚、PPTX 备注/图表、XLSX 公式/合并单元格/隐藏 Sheet。
- 代码：Python、JavaScript/TypeScript、Java、Go；语法错误和不完整文件。
- 搜索：中英文混合、缩写、同义词、路径/符号名、精确匹配和跨文档召回。

核心指标：

- 解析成功率、字段/段落召回率、定位准确率；
- 表格单元格准确率、代码节点与关系准确率；
- Precision@K、Recall@K、MRR；
- 每千页/每千文件处理耗时、峰值内存和安装体积；
- 离线运行成功率、错误隔离率和可重复性。

任何组件的输出都必须进入 Radar 的统一 Evidence 适配层，再参与后续业务计算；不允许组件输出直接成为 Assessment 结论。

## 10. 依赖工程化要求

在首个第三方运行时依赖进入项目之前，必须完成：

- 明确的包构建与依赖声明入口（例如 pyproject.toml，具体方案待 M14-D 决策）。
- Core 与 optional extras 的分组，避免可选依赖污染基础安装。
- 固定直接依赖范围及可复现锁定方案；明确开发、测试、运行依赖边界。
- CI 在 Python 3.9 和当前 Python 版本上验证基础安装；对 optional extra 单独设矩阵或专用 job。
- 依赖许可证清单、漏洞扫描和升级审查。
- 测试“没有可选依赖时基础 CLI 正常工作”和“可选依赖缺失时明确降级”。
- 供应链来源、哈希/锁文件、升级流程和回滚说明。

## 11. 当前阶段决策

- **批准的政策**：Core 可以引入少量经过严格评估的成熟依赖；不再强制零依赖。
- **当前默认安装**：本次只改策略和文档，没有新增第三方运行时依赖。
- **优先基线**：先评估 SQLite FTS5（无需 Python 第三方包）；PDF 解析并行比较 pypdf、pdfplumber、pypdfium2，不预设赢家。
- **L2 候选**：Docling、Tree-sitter；Tree-sitter 已通过合成多语言语法探针，仍需真实仓库基准和 Python 3.10+ 隔离安装。
- **L3 候选**：ScanCode、OCR 工具链；独立运行并评估。
- **暂缓**：PyMuPDF，待许可证审查；图数据库，待性能证据。
- **未批准**：上述候选均未获准进入默认依赖或正式发行包。

## 12. 变更记录

- 2026-11-22：M14-A 将“核心必须零依赖”修订为分层依赖策略；补充准入门槛、工程化要求和候选状态。
- 2026-11-22：M14-B 根据 PyPI 官方元数据更新 pypdf、pdfplumber、pypdfium2、Docling 和 Tree-sitter 的版本/兼容性预筛选；真实样本基准尚未完成。
