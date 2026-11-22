# M15-D3：Document Parser Capability v1

## 本阶段边界

本阶段先交付统一 Parser Capability 契约和一个不引入第三方依赖的文本解析实现。它覆盖 Markdown、纯文本和常见源代码/配置文本，作为后续 PDF、Office、OCR 与 AST 解析器的共同接入边界。

本阶段**不声称**已支持 PDF、DOCX、PPTX、XLSX、扫描件或多语言 AST。未知/二进制格式明确返回 `skipped`，不会把空结果伪装成解析成功。

## 输入契约

通过 `CapabilityContext(operation="parse")` 显式传入：

- `inputs.content`：已解码的 UTF-8 文本；
- `inputs.uri`：原始 Asset URI，必填；
- `inputs.filename`：文件名，用于格式识别；
- `inputs.media_type`：可选 MIME 类型。

当前实现限制最大 2,000,000 个 Unicode 字符；拒绝 NUL 字符。二进制解码、压缩包解包、网络抓取和文件系统权限仍属于调用方/Source 层，不由 Parser 自行处理。

## 输出契约

每条记录为 `document_fragment`，包含：

- 原始文档 URI、UTF-8 内容 SHA-256、格式；
- 片段类型、原文片段、Markdown heading path；
- locator：1-based 行号、0-based 字符偏移、UTF-8 字节偏移、fragment index。

偏移采用左闭右开区间。字节偏移以 UTF-8 编码计算；行号从 1 开始。解析结果按文档顺序输出，片段不跨越被省略的空白分隔行。

## Evidence 边界

Parser 输出是**解析观察值/文档片段**，不是 Evidence，也不是 Assessment。

调用方必须先确认 Source 和 Asset 已建立并通过领域校验，再根据片段内容、来源版本、定位完整性和采集时间创建 Evidence。Evidence 的 `locator` 应保留 Parser 的原生 locator；不能只存一段脱离文件位置的文本。Parser 本身不判断陈述真假、不判断是否满足需求，也不提升可信度。

## 格式能力矩阵

| 格式 | 本阶段 | 后续候选 |
|---|---|---|
| Markdown | 标题层级、段落、列表、引用块、围栏代码 | 表格结构、链接/引用关系 |
| TXT / RST / LOG | 空行分段 | 语言/版面检测 |
| Python/JS/TS/Java/Go 等文本 | 按空行分组的源码片段 | Tree-sitter AST 与符号关系 |
| PDF | 明确跳过 | pypdf / pdfplumber / pypdfium2 对照基准 |
| DOCX/PPTX/XLSX | 明确跳过 | python-docx / python-pptx / openpyxl 或 Docling 对照 |
| 扫描件 / 图片 | 明确跳过 | OCR 独立能力，保留页码与区域坐标 |

## 安全与资源

- 不执行宏、脚本或代码；不解压归档；不访问网络。
- 对文本字符数设上限；二进制 NUL 输入拒绝。
- 不在 CapabilityResult 中返回凭证或本地绝对路径。
- 上游解析失败不得转成成功空片段。
- PDF/Office 解析器后续必须单独评估恶意文件、ZIP bomb、XML 外部实体、超时、内存和沙箱。

## 依赖治理决策

本 PR 不修改 `pyproject.toml`、锁文件或默认依赖。后续 PDF/Office 组件仍按 `docs/OPEN_SOURCE_COMPONENT_SELECTION.md` 逐个做样本基准、许可证/安全审查和依赖批准；不能因为 M14 允许依赖就视为所有候选自动获批。

## 验收

- Python 3.9 与 3.13 完整测试矩阵通过；
- Markdown 标题路径、代码围栏、列表/段落和中英文 UTF-8 字节定位有测试；
- 纯文本与源代码文本按原始顺序切分；
- 超限、二进制、缺少 URI、错误 operation、未知格式均有明确结果；
- 无第三方运行时依赖；
- Parser 输出不自动成为 Evidence/Assessment。
