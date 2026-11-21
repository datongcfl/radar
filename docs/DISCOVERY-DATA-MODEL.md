# 需求驱动发现：领域数据契约 v1

> 状态：M1 契约冻结候选（v1）。本文件与 `schemas/discovery.schema.json` 是 M1 的共同基线；实现必须遵守这里的语义，不能仅以 JSON 能通过解析作为正确性标准。

## 1. 设计边界

Radar 的新发现链路采用八类领域对象：

| 对象 | 回答的问题 | 不应承担的职责 |
| --- | --- | --- |
| Workspace | 这项发现工作属于哪个隔离空间？ | 不存放具体证据结论 |
| Requirement | 要解决什么问题、如何验收？ | 不记录某次运行的临时结果 |
| Source | 信息来自哪个系统或来源入口？ | 不等同于某个文件或某段证据 |
| Asset | 来源中具体发现了什么对象？ | 不代表其内容已经被核验 |
| Evidence | 哪一处原始材料支持或反驳了什么事实？ | 不做需求满足度裁决 |
| Relationship | 对象之间存在什么可追溯关系？ | 不把推断伪装成事实 |
| Assessment | 基于哪些证据，对需求/验收项作何评价？ | 不覆盖或改写 Evidence |
| DiscoveryRun | 哪个输入版本、来源范围和规则执行了本次发现？ | 不覆盖历史 Run |

核心区分：

- Source 是来源系统/来源入口，例如 GitHub 仓库、网站、企业知识库连接。
- Asset 是来源中具体可定位的对象，例如仓库、仓库文件、Issue、PR、PDF、Excel、网页。
- Evidence 是从 Asset 的特定版本和特定位置提取的事实记录。
- Assessment 是对 Evidence 的解释和需求匹配结果。
- Agent 的推理结论不能直接写成 Evidence；必须作为 Assessment/备注，并引用其证据依据。

## 2. 通用字段与标识

每个领域对象必须具有：

- `schema_version`: 当前为整数 `1`，表示数据契约版本，不等于 Radar 软件版本。
- `object_type`: 固定对象类型。
- `id`: 带类型前缀的稳定标识；前缀分别为 `ws_`、`req_`、`src_`、`ast_`、`evd_`、`rel_`、`asm_`、`run_`。
- `created_at`: ISO 8601 日期时间，写入 UTC。
- `updated_at`: 可选，仅适用于允许更新的可变对象。
- `metadata`: 可选的扩展信息；不能用它绕过已定义字段语义。

ID 在 Workspace 内不得冲突。跨 Workspace 的公共 Source/Asset 可通过全局身份键去重，但 Workspace 私有的 Requirement、Evidence 关联、Relationship 和 Assessment 不得因去重而泄露或合并。

版本规则：

1. Requirement 使用单调递增的整数 `version`。修改需求语义、验收条件或关键术语时创建新版本，不原位覆盖旧版本。每个版本使用新的 `req_` ID，保持相同的 `workspace_id + key`，并通过 `supersedes_requirement_id` 指向上一版本；Assessment 同时保存 Requirement ID 和版本号。
2. Pack 引用必须锁定 `pack + version`，可附加内容摘要 `digest`。
3. Asset 的内容或上游版本变化时更新 Asset 的当前观察信息，并生成新的 Evidence；不得把新内容覆盖到旧 Evidence。
4. DiscoveryRun 固定记录 Requirement 版本、Pack 版本、来源范围和关键执行参数。
5. Assessment 固定引用 Requirement 版本和 DiscoveryRun；重复评价创建新的 Assessment。

## 3. 八类对象契约

### 3.1 Workspace

必需：`id`、`name`、`status`、`pack_refs`、`created_at`。

`pack_refs` 是 Pack 名称和版本的锁定列表。Workspace 是权限和数据隔离边界。第一阶段默认 Workspace 间隔离；只有经过明确授权的公共 Source/Asset 身份信息可以共享。Evidence、Requirement、Assessment、Run 不因共享 Asset 而自动共享。

### 3.2 Requirement

必需：`workspace_id`、`key`、`version`、`title`、`description`、`status`、`priority`、`acceptance_criteria`。

`key` 是人类可读业务编号（例如 D01、D03），`id` 是对象身份。术语至少区分 canonical、aliases 和 languages。验收条件必须有稳定的 criterion `id`，并标明是否必需、严重程度和类型。

需求状态：`draft`、`active`、`superseded`、`archived`。

### 3.3 Source

必需：`provider`、`uri`、`name`、`access_status`。

Source 描述来源系统或入口，不描述文件内容。访问状态与许可状态是两条独立信息：能访问不代表有复用许可；许可未知也不能推断为可复用。

### 3.4 Asset

必需：`source_id`、`asset_type`、`uri`、`title`、`status`。

Asset 可以有 `parent_asset_id`，例如仓库包含文件、Issue 关联仓库。文件路径、Issue/PR 编号、文档页码等定位信息属于 Asset 标识或 Evidence locator，不应只存成模糊文本。

Asset 类型首批覆盖 repository、file、directory、issue、pull_request、document、web_page、package、release、dataset。

### 3.5 Evidence

必需：`workspace_id`、`asset_id`、`evidence_kind`、`statement`、`locator`、`captured_at`、`verification_status`。

Evidence 是事实出处记录，必须能回到 Asset 的具体版本和位置。locator 支持文件路径/行号、PDF 页码、Excel sheet/cell range、网页 anchor、JSON Pointer 等。

Evidence 不可变。更正提取内容、上游文件变化、定位变化或核验状态变化时，新增 Evidence 或新增核验事件，不静默改写历史证据。引用原文应控制在必要范围内，默认 excerpt 上限 2000 字符；原始完整文件由快照策略管理，并考虑版权、隐私和存储成本。

核验状态：`unverified`、`source_confirmed`、`reproduced`、`rejected`。Quote 在页面中存在，只能说明来源文本确认；不能自动升级为代码运行或生产验证。

### 3.6 Relationship

必需：`from`、`to`、`relation_type`、`confidence`、`evidence_ids`、`status`、`created_by`。

关系是有方向的独立对象。首批关系类型：`contains`、`derived_from`、`supports`、`contradicts`、`tests`、`fixes`、`supersedes`、`depends_on`、`implements`、`mentions`、`same_as`。

除明确属于结构性关系的情况外，支持、反驳、实现、修复等语义关系应尽量引用 Evidence。冲突关系不能通过“最后写入覆盖”解决，应保留双方及其来源，交由 Assessment 或人工复核。

### 3.7 Assessment

必需：`workspace_id`、`requirement_id`、`requirement_version`、`discovery_run_id`、`overall_status`、`criterion_results`、`evidence_ids`、`pack_refs`、`assessed_at`。

每个验收条件单独给出状态和证据引用。整体状态不能掩盖单个关键验收项的缺口。

评价状态：

- `supported`: 有足够证据支持；
- `partially_supported`: 只有部分条件被支持；
- `contradicted`: 存在明确反证；
- `no_evidence`: 当前没有找到足够证据；
- `not_applicable`: 经规则或人工确认不适用；
- `not_assessed`: 尚未评价。

**`no_evidence` 不等于 `not_implemented`。** 没找到代码、文档或记录，不代表现实中不存在实现。只有发现明确反证或完成适当核验，才可以作更强判断。

### 3.8 DiscoveryRun

必需：`workspace_id`、`status`、`requirement_refs`、`pack_refs`、`source_scope`、`started_at`、`stages`、`counts`、`errors`、`parameters`、`radar_version`。

Run 状态：`pending`、`running`、`partial`、`succeeded`、`failed`、`cancelled`。每个阶段独立记录状态和错误；单个来源或解析器失败不应抹掉已成功阶段的结果。错误至少包含 stage、error_code、message、retryable，可选 source_id/asset_id。

Run 创建后保留其输入快照。运行结束后不应修改历史输入版本；补采集或重新发现必须产生新 Run。

## 4. 存储与引用规则（M1 约束，M2 实现）

首版使用标准库 JSON/JSONL 和 SHA-256，不引入第三方依赖。逻辑目录建议：

```text
workspaces/<workspace-id>/
  workspace.json
  requirements.jsonl
  sources.jsonl
  assets.jsonl
  evidence.jsonl
  relationships.jsonl
  assessments.jsonl
  runs/<run-id>/run.json
  snapshots/sha256/<digest>
```

JSONL 每行一个完整领域对象；ID 唯一，Requirement 的 `key + version` 也唯一。Run 单独写入 `runs/<run-id>/run.json`。快照以 SHA-256 内容哈希寻址，读取时重新校验哈希。v1 `JsonWorkspaceStore` 按 Workspace 隔离，采用单写入者约束；暂不承诺多进程并发写入。Source/Asset 当前也保存在 Workspace 内，跨 Workspace 公共资产共享留待后续授权与权限模型完善后实现。M2 可以改变物理存储实现，但不能改变本文件定义的领域语义。

## 5. 兼容与迁移

- 现有 Pack、Seeds、Run 文件及旧 CLI 命令保持原样可读。
- 新发现数据使用独立 schema，不把现有 `Source` 记录强行解释为新领域 Source。
- Legacy Source 可映射为一个 Source 加一个或多个 Asset；旧 Quote 只有在有明确出处定位时才能升级为 Evidence，否则保留为待补定位记录。
- 迁移过程必须记录来源对象 ID、转换时间和转换器版本；不删除或覆盖旧数据。
- `schemas/discovery.schema.json` 是 JSON Schema draft 2020-12。运行时校验由标准库实现，不依赖 jsonschema 等第三方库。
- `radar.legacy.read_legacy_sources()` 复用旧 Seeds 读取逻辑；`convert_legacy_sources()` 将旧 Source 拆成平台 Source 与具体 Asset。旧 Quote 只有同时具有文本和精确 locator 才能升级为 Evidence；没有 locator 的 Quote 保存在 `pending_quotes`，不伪造行号或页码。
- Legacy 导入采用稳定 ID；重复导入时应复用同一 `captured_at`，以保持记录内容一致。旧的 `quote_verified` 标记只有在 `quote_verified_this_run=true` 且由 web 核验时才会映射为 `source_confirmed`，避免把 Seeds 中的历史声明误当成当前核验事实。

## 6. M1 完成标准

1. 八类对象字段、ID、版本、时间、状态和关系语义冻结。
2. JSON Schema 覆盖八类对象及嵌套类型。
3. Python 领域对象与校验器遵循同一契约。
4. 测试覆盖必填字段、枚举、引用、不可变 Evidence、Requirement 版本和 Assessment 状态语义。
5. 不改变旧命令、旧 Schema 和现有 Pack/Seeds 数据。


## 7. Discover v1 离线闭环

第一版命令从需求文件和现有 Seeds 账本启动，不执行外网搜索：

```bash
python3 -m radar discover \
  --workspace ws_weak_current_demo \
  --workspace-root . \
  --requirements examples/requirements/weak-current.json \
  --pack packs/weak-current/pack.json \
  --seeds seeds/weak-current.json
```

需求文件使用 `schema_version: 1`，每条 Requirement 可声明 `pack_unit_ids`，将业务需求映射到 Pack 的模块/子系统 ID。此映射只用于发现候选资产，不等于需求已实现。

Discover v1 执行：读取需求和 Seeds → Source/Asset/Evidence 转换 → 按 Pack 单元建立候选 `mentions` 关系 → 生成逐需求 Assessment → 保存 DiscoveryRun。相同 Workspace 锁定 Pack 版本；更换 Pack 版本应建立新 Workspace 或执行显式迁移。

重要语义：

- `mentions` 表示候选关联，不代表 `supports`，更不代表已经满足验收条件。
- 有候选 Asset 但没有可定位 Evidence 时，Assessment 必须是 `no_evidence`。
- 有候选 Evidence 但尚未完成语义核验时，Assessment 是 `not_assessed`。
- 旧 Quote 缺少精确 locator 时保存在 Workspace 的 `pending_quotes.jsonl`，不会伪造成 Evidence。
- Discover v1 目前只使用现有 Seeds，不会主动发现 GitHub 文件、Issues、PR 或网页；资产级自动发现属于后续里程碑。
