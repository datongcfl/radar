# M15-D2：GitHub Source Capability 接入

## 本阶段范围

将既有 `radar.adapters.collect_github` 包装为 Registry 能调用的 `source/github` 能力。底层查询和 metadata 映射逻辑保持原样；本阶段不改成 GraphQL、不增加 GitHub SDK，也不声称已发现仓库文件、文档正文、Issues 或 PR。

## 执行边界

- CLI 是当前可信应用组合根，显式创建 Registry 并注册 GitHub capability。
- `GithubSourceCapability` 通过 `CapabilityContext` 接收 Pack、查询上限和 Token。
- Token 只作为本次执行的短生命周期参数，不写入 CapabilityResult、warnings 或 metadata。
- 现有 `collect_github` 保留，其他调用方可继续使用；CLI 的 GitHub 路径改为 Registry 调用。
- GitHub 实现仍在 `radar.adapters`，Capability 模块只负责契约适配。

## 结果语义

- 无查询警告：`succeeded`，即使 Pack 没配置 GitHub 查询词，也允许返回空记录。
- 部分查询成功且存在警告：`partial`，已取得的记录仍保留。
- 所有查询均失败：`failed`，不得当作空成功。
- Provider 抛出异常：转成不包含异常文本的错误码和异常类型。
- 结果继续标记为 metadata 级别；不得自动升级为代码、文档或 Evidence。

## 明确未解决

1. GitHub API 仍通过 curl 调用；当前错误诊断能力有限。
2. 仓库文件、文档、Issues、PR、Review comments、CI Checks 尚未由本能力采集。
3. 现有结果仍以仓库 metadata 为主，不能据此判断需求实现覆盖。
4. 真实 Token / rate-limit / 私有仓库端到端验证尚未完成。
5. 当前每次 CLI 调用创建一个轻量 Registry；后续多个 Source Capability 接入时再统一 composition root。

## 验收

- 原有 metadata 映射不变。
- CLI `--github` 经 Registry 调用。
- 部分失败不丢弃成功记录；全失败明确标记 failed。
- 不在结果或告警中暴露 Token。
- Python 3.9 / 3.13 完整测试套件通过。
