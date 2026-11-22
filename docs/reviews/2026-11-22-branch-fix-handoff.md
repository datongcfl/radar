# Radar 分支修复交接单

> 交接对象：独立实现 Agent（建议使用与审查者不同的会话/模型）
>
> 审查者：Arena Agent Mode
>
> 基线：`main @ 40c0528141b88c0a80ed25015b982ae44a8f8992`
>
> 源快照：`feat/requirement-driven-discovery @ 07c6ec7b97569e8a329d9f932f7e65113193a677`
>
> 当前状态：只有审查文档和 review-only 失败测试，没有生产代码修复；本交接单不授权合并，也不授权直接改 main。

## 0. 一句话任务

从当前 main 开始，按 PR-0 → PR-6 的短生命周期分支逐组 replay/修复；每个 PR 先提交失败测试，再提交生产修复；修复者不自签、不合并。不要试图把 197 个提交整包 rebase 或 merge 成一个 PR。

## 1. 先读什么（按顺序）

1. `docs/reviews/2026-11-22-branch-review.md`
   - 重点：§3 P0、§11“独立复核回应与证据矩阵”、§11.4 证据状态契约、§11.5 反向测试、§11.6 调整后的 PR 顺序。
2. `docs/reviews/2026-11-22-main-review.md`
   - main 既有 P0-1/P0-2/P0-3/P0-4；不要把它们误当成分支新问题，也不要忽略。
3. `tests/review_p0/README.md` 和 `tests/review_p0/test_branch_p0_contracts.py`
   - 13 个合同测试；全部应在未修复的 feature 快照上失败。
4. 源快照本身
   - 不要只看审查结论；每个 P0 都先复现。

## 2. 基线与快照

```bash
# main 基线
git fetch origin main
git rev-parse origin/main        # 期望 40c0528141b88c0a80ed25015b982ae44a8f8992

# 只读快照（不要 checkout 到主工作区）
curl -fsSL \
  https://codeload.github.com/datongcfl/radar/tar.gz/refs/heads/feat/requirement-driven-discovery \
  -o /tmp/rdd.tgz
mkdir -p /tmp/rdd
tar -xzf /tmp/rdd.tgz -C /tmp/rdd --strip-components=1
```

审查时的分支关系是 **197 ahead / 57 behind**。这个数字只用于说明不能整包合并；真正的回退证据是文件级差异：

- 分支 `radar/cli.py` 没有 `parse`/`CapabilityRegistry`；
- 分支 `radar/document_parser.py` 是 143 行旧版；
- 分支没有 `capabilities.py`、`xml_safety.py`、`requirements-*.txt`、`github_asset_inventory.py`；
- 分支 `.github/workflows/tests.yml` 没有 main 的四个 optional parser jobs。

因此：**旧 feature 分支只作为审计/取码来源，不作为合并目标。** 所有新分支从当前 main 开始。

## 3. 硬约束

- 遵守 `AGENTS.md`：不直接改 main；所有改动走 PR；合并权只属于仓库所有者。
- 不增加第三方依赖、不改 `pyproject.toml`/`uv.lock`，除非所有者明确批准并完成准入评估。
- 不打标签、不发版本、不改 LICENSE、不改 `schema_version`。
- 不修改 `docs/reviews/`；不把 `tests/review_p0/` 里的断言改到“绿”来伪造完成。
- 不删除/覆盖 main 的 `parse`、`xml_safety.py`、capability/parser、`requirements-*.txt`、optional parser CI。
- 不把 `/tmp/rdd` 的 197 个提交整段 cherry-pick；只移植当前 PR 需要的最小模块。
- 不把分支的旧 `document_parser.py` 覆盖 main 的 parser capability；需要 CSV/Office helper 时放到独立兼容模块。
- 不自签、不自动合并；修复完成后交给审查者或第三个 Agent 复核。

## 4. 交付顺序与测试映射

| PR | 范围 | 必须变绿的 review 测试 | 主要文件 |
|---|---|---|---|
| PR-0 | 基线/治理；冻结整包合并；更新 M15 计划 | 无（人工核对） | `docs/architecture/M15-REALIGNMENT-PLAN.md` |
| PR-1a | main 的 Web 自证、20k 截断 `unknown` | 新增 main 侧反向测试 | `radar/web.py`、`radar/model.py`、`radar/coverage.py`、`radar/verify.py` |
| PR-1b | Evidence 内容绑定 + 状态传播（P0-3/P0-4） | `TestObservationEvidenceBinding`、`TestEvidenceStatusPropagation` | `radar/business_invariants.py`、`radar/business_observation_extractor.py`、`radar/cli.py`、共享 helper |
| PR-2 | Discovery/Legacy 与来源身份（P0-7、main P0-2） | `TestLegacyLocatorAndIdentity` | `radar/legacy.py`、来源身份 helper |
| PR-3 | 表格/业务图（P0-2 + 接入 PR-1b） | `TestTransactionTablePath`、`TestTableInputHygiene` | `radar/business_table_evidence.py`、`radar/business_observation_extractor.py`、`radar/observation_aggregator.py` |
| PR-4 | Ledger 完整性（P0-5/P0-6） | `TestLedgerImportPreflight`、`TestLedgerAggregationIdentity` | `radar/ledger_workspace.py`、`radar/ledger_aggregator.py`、`radar/business_graph.py` |
| PR-5 | Parser/安全（P0-8） | `TestOfficeParserSafety` | `radar/document_parser.py` 或独立兼容模块、`radar/github_discovery.py`、复用 `radar/xml_safety.py` |
| PR-6 | 文档/CI/基准 | 无新增 P0；回归全绿 | `.github/workflows/*`、README、docs |

**所有 PR 都额外跑 `TestMergePreservation`**：确认树里仍有 `parse` 和 `xml_safety.py`。这个测试不是“功能 PR 的验收”，而是 replay 的底线。

### PR-0：基线与治理（只改文档）

- 从当前 main 开分支；把 `docs/architecture/M15-REALIGNMENT-PLAN.md` 从 `chore/m15-architecture-realignment` 取来（该文件不在 main）。
- 更新基线：main SHA、feature/chore 的实时 ahead/behind、open PR 数；删除“0 behind”。
- 把 M15-B 标为 main 已完成/只做补缺；M15-D 标为 main 已有 capability/parser，不要另起一套。
- 保留 §8 的 import coupling 结论，但把验收改为“`import radar.cli` 不加载 Ledger/Business/GitHub 模块”。

**验收**：计划中的数字可用 `gh api compare` 复算；chore 分支 diff 只有文档。

### PR-1a：main 证据状态（先做，独立于分支）

- 修 main P0-1：`quote_extracted` 不能自动变成 `quote_verified`。
- 修 main P0-4：正文截断时，截断区外的 quote 是 `unknown`，不是 `false`；保留截断标记和原始长度。
- 修 main P0-3 的审计目录校验（如本 PR 范围允许）；如果范围太大，拆 PR-1a-2，不要混入分支 replay。

**验收**：新增反向测试（自动抽取不得 verified；截断区外 unknown；错目录审计失败）；main 原有测试全绿。

### PR-1b：Evidence 契约（第一块分支代码）

- 只移植 `business_invariants.py`、`business_observation_extractor.py` 中与 Evidence/Observation 有关的最小部分，先不搬业务图/表格/Ledger。
- 建立统一 helper（建议名 `radar/evidence_policy.py`，名字可改）：
  - `rejected` 不得支撑 `pass`/`source_backed`；
  - `unverified`/`unknown` 不得默认成 `document_text`；
  - field/scope/transaction 三类 provenance 都要校验 locator 与状态；
  - Observation 记录内容版本/哈希；Evidence 内容变化后旧 Observation 失效；
  - `evaluate_business_invariants` 输出真实 Evidence level，不再用 origin 标签覆盖。
- `cmd_extract_observations` 计算输入内容哈希，与 Asset/Evidence 的 `content_sha256`（或等价版本标识）比对；无法比对时降级 `unknown`，不能 `pass`。

**验收**：

```bash
# 把对应测试移入正式 tests/ 后
python3 -m unittest discover -s tests -v
```

对应 `TestObservationEvidenceBinding`、`TestEvidenceStatusPropagation` 全绿；`TestMergePreservation` 仍绿；main 测试全绿。

### PR-2：Discovery/Legacy 与来源身份

- 移植 `discover.py`、`legacy.py`，接入 main 的 `cli.py`，保留 `parse`/lazy import。
- 修 P0-7：只有 `path + line/row/cell/field` 或 `url + 锚点` 才算精确 locator；`{"note":...}` 进 `pending_quotes`，保留原文。
- 修 P1-5：Legacy `captured_at` 复用、`legacy_covers` 排序去重，重复导入不报 duplicate ID。
- 来源身份（main P0-2）作为 PR-2a 或独立小 PR：统一 `(provider, object_type, canonical_id)`，避免 GitHub/Gitee 跨查询 ID 冲突；不要只在适配器里改下标。

**验收**：`TestLegacyLocatorAndIdentity` 全绿；重复导入无重复 Evidence；`radar discover` 离线路径通过；`parse` 仍在。

### PR-3：表格/业务图

- 移植 `business_table_evidence.py`、`observation_aggregator.py`、`business_graph.py`，接入 PR-1b 的契约。
- 修 P0-2：selector 把 `transaction_fields` 纳入选列；缺 transaction 时显式 skip，不能默认无交易。
- 修 P1-1/P1-2：重复表头、欧式小数不能静默取错；按声明 locale 或 skip。
- P1-6：`return_reference_target_field` 必须在 `deduplicate_by`；缺 target 的 return 进 unresolved，不能算成 `-1`。

**验收**：`TestTransactionTablePath`、`TestTableInputHygiene` 全绿；CSV/XLSX 从 selector → extractor → aggregator 端到端测试；篡改输入仍失败。

### PR-4：Ledger 完整性

- 移植 `ledger_effects.py`、`ledger_vouchers.py`、`ledger_aggregator.py`、`ledger_source_adapter.py`、`ledger_workspace.py`、`ledger_control_pipeline.py`。
- 修 P0-5：`import_ledger_bundle` 在 append 前调用完整语义 preflight；坏包零落盘。
- 修 P0-6：聚合身份至少 `(source_system, ledger_kind, ledger_entry_id)`；同身份冲突进 skipped/unresolved；独立 vs 镜像必须有明确语义，不能静默覆盖。
- P1-8：先完成映射/校验再创建 Evidence；避免失败行留下孤儿 Evidence；10k 行基准。

**验收**：`TestLedgerImportPreflight`、`TestLedgerAggregationIdentity` 全绿；坏包后 `ledger_effects.jsonl` 不变；合法包结果与现有测试一致。

### PR-5：Parser/安全

- 不覆盖 main 的 `document_parser.py`/`*_parser.py`；把分支需要的 CSV/Office helper 放到独立兼容模块。
- 复用 `radar/xml_safety.py`；ZIP 解压前检查总解压量/单 entry/压缩比；DTD/ENTITY fail closed。
- GitHub Office blob 路径也走同样预检。

**验收**：`TestOfficeParserSafety` 全绿；正常 DOCX/XLSX/PPTX 与 main 行为一致；`parse` 与 optional parser jobs 仍通过。

### PR-6：文档/CI/基准

- 对齐 main 的 `tests.yml` optional jobs + 分支 discover smoke；`package-smoke`/benchmark 加 main/PR 触发。
- 更新 259 vs 254、行业数、`BUSINESS-GRAPH.md:51` 字面 `\n`、`OPEN_SOURCE` 的 pyproject 说明。
- 把 review-only 测试迁移到正式 `tests/`，删除 `tests/review_p0/`。

**验收**：PR/main 门禁完整；文档数字与代码一致；全量测试通过。

## 5. 失败测试怎么用

```bash
# 在 main 工作区运行；不要 checkout 分支
python3 tests/review_p0/run.py --branch-root /tmp/rdd
```

预期：**13 tests, 13 failures**。这是基线证据，不是“测试坏了”。

规则：

- 不要修改 `tests/review_p0/` 让它们变绿；
- 每个 PR 把对应测试复制/移动到正式 `tests/`，按 PR 的模块调整 import；
- 修复后测试必须从“断言失败”变成“断言通过”，并在 PR body 里贴 before/after 输出；
- `TestMergePreservation` 在每个 PR 都跑，防止 replay 时丢 `parse`/`xml_safety`。

## 6. 每个 PR 的 Definition of Done

```text
[ ] 从当前 main 开短生命周期分支
[ ] 先提交失败测试（附失败输出）
[ ] 生产修复不碰 docs/reviews、不弱化测试
[ ] python3 -m unittest discover -s tests 全绿
[ ] 对应 review 测试已迁移并通过
[ ] TestMergePreservation 通过
[ ] git diff --name-status main...HEAD 没有删除 main 的 parser/capability/CI/requirements
[ ] PR body 写明：改哪些文件、怎么验收、未解决项
[ ] 由审查者/第三方在干净 checkout 复跑，不由修复者自签
```

## 7. 需要所有者先决定的事项

不要替所有者静默决定；把这些写在 PR-0 或 Issue 里：

1. **P0-6 跨源同 ID**：独立两笔默认相加，还是镜像导出去重？如果无法判断，输出 `unresolved/mirror`，不要默认相加或覆盖。
2. **P0-7 旧 locator schema**：哪些旧字段是精确 locator，哪些只是备注；迁移映射表放哪里。
3. **P0-3 内容版本**：filesystem 用 `content_sha256`；GitHub 用 blob SHA + 下载内容哈希；两者如何统一成 `asset_version_ref`。
4. **P0-8 安全限制**：ZIP 解压总量/压缩比/单 entry 上限的具体数值；是否与 main parser 一致。
5. **Ledger 身份**：是否把 `ledger_kind` 纳入聚合身份；`voucher` 的 `ledger_entry_ids` 如何携带 source。
6. **Schema**：Ledger 三类记录是纳入 `schemas/discovery.schema.json`，还是明确标为内部存储类型；不要两边都含糊。
7. **PR-1a 范围**：main P0-1/P0-4 与分支 replay 分开；如果所有者要合并处理，必须单独授权。

## 8. 给修复者的第一条消息（可直接复制）

```text
你是独立实现者，不是审查者。先不要写生产代码。

基线：main 40c0528；源快照：feat/requirement-driven-discovery @ 07c6ec7b。
先读 docs/reviews/2026-11-22-branch-review.md（尤其 §11）和
tests/review_p0/README.md。

第一步：
1. 下载/解压源快照到 /tmp/rdd；
2. 运行 python3 tests/review_p0/run.py --branch-root /tmp/rdd，记录 13 个失败；
3. 按 §11.6 输出 PR-0/PR-1a/PR-1b 的具体文件清单和测试计划，不要开始改生产代码；
4. 等我确认后再开始 PR-0。

硬约束：不改 main、不合并、不增加依赖、不改 docs/reviews、不弱化测试、
不删除 main 的 parse/xml_safety/optional parser CI。每个 PR 先失败测试后修复。
```

## 9. 停止条件

遇到以下情况先停下来报告，不要绕过：

- 无法复现 13 个失败（说明快照或环境不一致）；
- 修复需要第三方依赖或改 `pyproject.toml`/`uv.lock`；
- 测试与所有者尚未决定的业务语义冲突（尤其 P0-6 镜像、P0-7 旧格式）；
- 需要修改 `docs/reviews/` 或弱化测试才能通过；
- 合并会导致 main 的 `parse`、`xml_safety.py`、optional parser CI 消失。

## 10. 交接物清单

给修复者的最小包：

- 本文件：`docs/reviews/2026-11-22-branch-fix-handoff.md`
- 分支评审：`docs/reviews/2026-11-22-branch-review.md`
- 主评审：`docs/reviews/2026-11-22-main-review.md`
- 失败测试：`tests/review_p0/`（README、run.py、test_branch_p0_contracts.py）
- 源快照：`07c6ec7b` 的 codeload 链接（见 §2）

如果这些文件尚未推送到远程，先把它们作为附件/补丁交给修复者；不要让修复者凭记忆重建测试。
