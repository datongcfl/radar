# Schema 契约（v1.0）

## 文件

| 文件 | 对象 | `schema_version` |
| --- | --- | ---: |
| `schemas/pack.schema.json` | 行业 pack | 1 |
| `schemas/seeds.schema.json` | 来源账本 | 1 |
| `schemas/claims.schema.json` | claim 账本 | 1 |
| `schemas/state.schema.json` | run/scan 元数据 | 1 |

JSON Schema 使用 draft 2020-12，只作为契约文档；运行时不依赖第三方 validator，实际校验由 `radar/model.py`、`radar/claims.py` 完成。

## 不可破坏的字段

### pack

必需：`schema_version=1`、`pack`、`version`、`title`、`modules`、`subsystems`。  
模块/子系统必需：`id`、`name`、`artifacts`、`keywords`；ID 分别匹配 `M\d{2}` / `S\d{2}`。

### seeds

最小必需：`id`、`url`、`evidence_level`、`covers`、`quotes`、`status`。  
`--strict` 额外要求 v0.1 的 12 字段。可选字段包括平台、许可、stars、`quote_verified`、`quote_verified_by` 等。

### claims

必需：`schema_version=1`、`claims`；每条 claim 必需 `id`、`statement`、`covers`、`sources`；`contradicts` 可选。

### state

必需：`schema_version=1`、`run_id`、`title`、`created_at`、`pack`、`pack_version`、`pack_sha256`、`seeds_sha256`、`mode`、`options`、`counts`、`warnings`、`radar_version`、`radar_commit`。  
`mode=scan` 时额外写 `base` / `since`。

## 兼容规则

- `schema_version` 是**数据格式版本**，当前冻结为 `1`；
- `__version__` 是**软件版本**，当前 `1.7.0`；
- 新增可选字段不升 `schema_version`；
- 删除字段、改字段语义、改必填集合必须升 `schema_version` 并提供迁移脚本；
- 旧 run 缺 `radar_version` / `quote_verified` 时按 `?` / `unknown` 读取。
