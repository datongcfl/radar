# M15-D：Capability Registry 契约 v1

## 目标

Discovery Core 通过稳定的能力接口调用来源采集、文档解析和领域扩展；Core 不导入具体 GitHub、PDF、Office、Tree-sitter 或 Ledger 实现。具体实现由应用组合根显式注册。

本阶段只建立接口和注册机制，不声称现有 Discover orchestration 已完成解耦。

## 能力类别

首批采用开放字符串类别，避免把行业能力写死在 Core：

- `source`：从 GitHub、Gitee、Web、企业系统等发现 Source/Asset/Evidence；
- `parser`：解析 PDF、Office、代码、图像等资产内容；
- `domain`：执行行业知识包相关的领域分析或投影。

类别不是权限声明。是否允许访问某个系统、Workspace 或数据范围，仍由调用方的授权和策略层负责。

## 契约

实现 `Capability` Protocol：

- `descriptor`：`name`、`kind`、`version`、`api_version`；
- `execute(context)`：接收显式操作、Workspace ID、输入和参数；
- 返回统一 `CapabilityResult`，包含状态、记录、警告、错误和元数据。

Registry 按 `(kind, name)` 唯一注册。重复注册拒绝；相同名称出现在不同类别时，调用方必须显式指定类别。注册表不支持覆盖注册，不会在后台扫描或导入任意 Python 模块。

## 失败语义

| 状态 | 语义 |
| --- | --- |
| `succeeded` | 能力完成，结果可用 |
| `partial` | 有部分结果，同时有警告或未完成项 |
| `skipped` | 按策略主动跳过 |
| `unavailable` | 请求的能力未注册 |
| `failed` | 能力执行失败，必须提供错误对象 |

缺少能力不能伪装为空结果或成功。执行异常由 Registry 隔离，并仅返回错误码和异常类型，不持久化异常文本，避免泄露 Token、路径或其他敏感信息。能力实现应自行把可恢复的来源级问题转成 `partial`，而不是抛出整个能力失败。

## 安全与依赖边界

- `radar.capabilities` 只依赖 Python 标准库。
- Core 不执行动态导入、entry-point 自动发现或任意插件代码。
- 注册动作由可信应用组合根显式完成；第三方插件的安装、启用和权限授权是独立流程。
- Context 的顶层映射只读；大型文件和敏感凭证不应作为普通参数复制，优先使用受控句柄或调用方提供的短生命周期对象。
- Registry 不替代网络权限、租户隔离、文件沙箱或审计日志。
- 能力结果中的记录必须由调用方继续经过 Discovery 领域校验、来源定位和 Evidence 可信度验证。Registry 不把 provider 输出自动升级为 Evidence 或 Assessment。

## 分阶段接入

1. M15-D1（本 PR）：能力契约、注册、查询、执行和失败语义。
2. M15-D2：将 GitHub Discovery 包装为 source capability，保留旧 CLI 行为。
3. M15-D3：将文档解析包装为 parser capability，保留页码、Sheet、Cell 等原生 locator。
4. M15-E：将 Ledger / Business Graph 行业能力注册为可选 domain capability。
5. 后续：按需引入插件发现机制，但必须有显式 allowlist、版本兼容、安全和许可证治理。

## 当前限制

本 PR 不迁移现有 GitHub、Office、Ledger 实现，也不改变 `radar discover` 命令行为。只有接口与注册表通过独立测试后，才能开始逐个接入；在完成 M15-D2/D3 前，不能宣称 Discovery 主链路已解耦。
