# M15-D2b：Gitee Source Capability 接入

将既有 `collect_gitee` 包装为 `source/gitee`，CLI 的 `--gitee` 路径通过 CapabilityRegistry 执行。原有 Gitee 查询和 metadata 映射不变。

## 约束

- 保留 GITEE_TOKEN 环境变量及 `~/.config/radar/gitee_token` 文件读取方式。
- Token 只进入当前执行上下文，不写入结果、metadata 或警告。
- 无 Token 且 Pack 配置了 Gitee 查询时，明确返回 failed，而不是空成功。
- 部分查询成功时保留记录并标记 partial。
- 仍然只返回仓库 metadata，不提升为代码或文档 Evidence。
- 旧的 `collect_gitee` 函数保持可用，CLI 通过 Registry 接入。

## 尚未解决

真实 Gitee Token、速率限制、私有仓库和服务端分页仍需端到端验证；Gitee API 响应格式也需要真实样本覆盖。
