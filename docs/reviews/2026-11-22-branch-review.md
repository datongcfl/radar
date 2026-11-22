# 2026-11-22 分支评审：feat/requirement-driven-discovery + chore/m15-architecture-realignment

> 评审对象（只读快照）：
>
> - `feat/requirement-driven-discovery` @ `07c6ec7b97569e8a329d9f932f7e65113193a677`
> - `chore/m15-architecture-realignment` @ 仅多出 `docs/architecture/M15-REALIGNMENT-PLAN.md`（3 个文档提交）
> - 当前 main：`40c0528141b88c0a80ed25015b982ae44a8f8992`（PR #43，M16 GitHub asset inventory）
>
> 本文行号均指上一节的分支快照，不是 main。文中的“分支”默认指 feature 分支；chore 分支单独在第 6 节评审。

## 0. 结论摘要

**不建议直接合并，也不建议把分支 rebase 后整包合入。**

原因不是“分支落后”，而是三层问题叠加：

1. **拓扑层**：feature 相对当前 main 是 `197 ahead / 57 behind`，merge-base 为 `b14c8916`。main 在分支创建后合入了 57 个提交（PR #29–#43），包含 capability registry、PDF/DOCX/XLSX/PPTX 解析器、`parse` CLI、`xml_safety.py`、可选依赖 CI、M16 asset inventory。分支没有这些文件；合并时 `cli.py`、`document_parser.py`、workflows、README 是 modify/modify 冲突，若按分支侧解决就会丢失 main 能力；即使自动合并成功，也不能证明两边能力同时保留。这是 **P0-1**。
2. **正确性层**：分支新增的表格观察链、业务不变量校验、Ledger 导入与聚合存在可复现的静默错误：交易字段被丢弃、观察值可以与 Evidence 不一致、被拒绝的 Evidence 仍能通过校验、非法 Ledger 包先落盘后报错、跨源 `ledger_entry_id` 冲突丢行。这些是 **P0-2 至 P0-7**。
3. **治理层**：`M15-REALIGNMENT-PLAN.md` 的基线仍是 `main=b14c8916 / feature 197 ahead / 0 behind`，并把“依赖治理”和“Source/Capability Adapter”列为未来工作；这两项已在 main 合入。照该计划执行会重复 main 已完成的工作，并继续使用过期基线做 PR。此问题在 chore 分支，**P0-9**。

**合并的最小前置动作**：

- 不要 merge feature 到 main，也不要用 feature 覆盖 main 的 `radar/cli.py`、`radar/document_parser.py`、`.github/workflows/tests.yml`、`requirements-*.txt`。
- 以 `40c0528` 为基线，按“领域契约/存储（main 已有）→ Discovery 编排 + Legacy → 表格观察 + 业务图 → Ledger → GitHub/文档适配 → 文档/CI”拆成多个 PR；每个 PR 保留 main 的 parser/capability 实现，只新增分支独有的编排与领域模块。
- 先修 P0-2 至 P0-8，并同步更新 P0-9 的治理基线，再谈“功能完成”。修完后 `259+` 测试全绿只是必要条件，不是充分条件；需要新增本文列出的端到端回归。

**与首轮 main 评审的关系**：main 评审的 P0-1（`--web` 自产自证）、P0-2（GitHub/Gitee 跨查询 ID 冲突）、P0-3（审计盲区/基线可覆盖）、P0-4（20k 截断判 false）在分支代码中仍然存在（分支没有修）；本文列的是**分支新增的** P0，两者是叠加关系，不是替代关系。尤其注意：分支把 main 的 `xml_safety.py` 与 Office 解析器换成了旧的单文件解析器，属于相对 main 的**安全回退**（P0-8）。

---

## 1. 实际跑了什么

### 1.1 快照与测试

- 用 codeload tarball 取 `feat/requirement-driven-discovery@07c6ec7b` 到 `/tmp/rdd`，未在 `/home/user/radar` checkout 分支，未改动 main。
- `python3 -m unittest discover -s tests`：`Ran 259 tests ... OK`。
- `python3 -m radar --help`：11 个子命令（`run/scan/claims/validate/discover/extract-observations/business-graph/ledger-adapt/ledger-import/ledger-control/diff`）。
- `pyproject.toml` 与 `uv.lock` 与 main 同内容；分支没有 main 的 `requirements-pdf.txt` / `requirements-docx.txt` / `requirements-xlsx.txt` / `requirements-pptx.txt`。

### 1.2 跑通的离线路径

```text
radar discover --workspace ws_review --workspace-root /tmp/wsrev \
  --requirements examples/requirements/d03-material-procurement.json \
  --pack packs/weak-current/pack.json --seeds seeds/weak-current.json
# exit 0；sources=7 assets=35 evidence=0 pending_quotes=23
# D03 离线无 GitHub token，evidence=0 是预期，不是 bug

radar business-graph --workspace ws_review2 ... --pack packs/weak-current/pack.json \
  --business-model packs/weak-current/business-model.json
# exit 0；nodes=74 edges=60 criterion_evidence_matrix=12
# 6 条 invariant 均为 no_observation，符合“不伪造观测”的口径
```

已确认的正常行为（不应误报）：

- 未初始化 workspace 的 `business-graph` 直接 `[fail] workspace is not initialized` 并 exit 1。
- `ledger_effect` 必须引用本 Workspace 的 Asset+Evidence；`import_ledger_bundle` 会拒绝外部 Evidence（`StorageError`）。
- `adapt_ledger_source` 对每行先 `validate_ledger_effects([effect],[ev])`，无效行进入 `unresolved`，不会作为合法 effect 落盘（但见 P1-8 的孤儿 Evidence）。

### 1.3 定向复现（本文结论的依据）

| 复现 | 结果 |
|---|---|
| 用 `select_required_table_chunks` + `extract_table_observations` 处理 weak-current `receipt_quantity_balance` | 选中的列只有 `accepted_qty/rejected_qty/received_qty` 与 scope；`transaction={}`。`docstatus/is_return/...` 未被选中 |
| 同一组表格行交给带 `transaction_semantics` 的 `aggregate_observations` | 全部跳过，原因 `unverified_transaction_metadata`；退货/过账语义不生效 |
| 两源 `S1/E1=5`、`S2/E1=7` 交给 `aggregate_ledger_effects` | 结果 `values={'qty':'7'}`、`contribution_count=1`；S1 的 5 被静默丢弃，无 `unresolved` |
| 缺 `ledger_kind` 的 rule / effect 走 `import_ledger_bundle` | 导入返回成功；随后 `run_ledger_control_pipeline` 才抛 `LedgerControlPipelineError` |
| `verification_status="rejected"` 的 Evidence 作为 test observation 的 provenance | `validate_observation_bundle` 通过；`evaluate_business_invariants` 输出 `outcome=pass`、`verification_level=test_fixture` |
| 输入 CSV 的单元格改成 `99/2/101`，Evidence 仍是 `8/2/10`（locator 完全相同） | `extract_table_observations` 产出 `99/2/101`；`validate_observation_bundle` 通过 |
| observation 的 `field_provenance.locator` 改成 `totally-different.csv:99:7` | 校验通过；没有把 provenance locator 与 Evidence locator 比对 |
| Legacy quote 的 locator 为 `{"note":"somewhere on page 3"}` | 被升级为 Evidence（evidence=1，pending=0） |
| 重复表头两个 `received_qty` 列 | 取后一列 `999`；无冲突告警 |
| `extract_csv_document` 输入 TSV `a\tb\tc\n1\t2\t3\n` | 整行被解析为单单元格 `a\tb\tc`；`\t` 未被当作分隔符 |
| `"1,23"` 作为数值 | 被规范化为 `123`；无告警 |
| 同一 Workspace 用相同输入隔 1.2s 再跑 `run_discovery` | Evidence 从 1 条变 2 条，ID/captured_at 不同（`evd_97ae…` vs `evd_9813…`） |
| 同一 Legacy Asset 的 `covers` 顺序从 `["u1","u2"]` 改为 `["u2","u1"]` 再导入 | `StorageError: duplicate immutable record id`；顺序敏感，不是幂等 |
| 删掉 `transaction_semantics.deduplicate_by` 中的 `receipt_id` 后跑 return cap | 模型校验仍接受；原始 10、退货 11 聚合为 `-1`，`contribution_count=2`，没有 `return_quantity_exceeds_original_receipt` |
| observation 缺声明中的 scope 字段 | `business_scope={}` 仍通过 `validate_observation_bundle` |

### 1.4 未覆盖

- 没有真实 GitHub/Gitee token，未跑在线搜索/文档抓取；未验证 GitHub API 限流、权限失败、大仓库、私有仓库。
- 没有执行真实 ZIP 炸弹或 DTD/实体样本（P0-8 是代码审查 + 对照 main 的 `xml_safety.py`，不是已执行攻击）。
- 没有跑 10k 行 ERP 性能基准；P1-8 的复杂度结论来自代码路径。
- 没有在 `/home/user/radar` 做实际 rebase/merge 演练；P0-1 的“会删 main 能力”来自文件清单与逐文件对比，不是实际合并冲突输出。
- 没有审 Gitee 分支能力（分支没有 main 的 `gitee_capability.py`）。

---

## 2. 分支范围与合并判断

### 2.1 硬数据

| 项目 | 读数 |
|---|---|
| merge-base | `b14c8916` |
| feature 相对 main | 197 ahead / **57 behind** |
| 变更面 | 70 files，+14,608 / −288 |
| chore 相对 main | 200 ahead / 57 behind；71 files；独有文件只有 M15 计划 |
| 当前 open PR | 0 |
| 分支测试 | 259（README 仍写 254） |
| main 测试 | 191（当前 main 快照） |

“197 ahead / 0 behind”是相对 merge-base 的读数，不是相对当前 main 的读数。**不要再把分支描述为 main 的超集。**

### 2.2 三层文件

**A. 两边同内容（契约没有漂移）**

- `radar/discovery.py`、`radar/discovery_store.py`、`schemas/discovery.schema.json` 与 main 字节相同；schema 1042 行、23 个 `$defs`、8 类对象。
- 这说明“领域契约/存储”已经是 main 的一部分，分支不是它的唯一来源；分支的增量主要在编排、业务图和 Ledger。

**B. main 独有（分支没有）**

- `radar/capabilities.py`、`radar/github_capability.py`、`radar/gitee_capability.py`、`radar/github_asset_inventory.py`、`radar/xml_safety.py`。
- `radar/pdf_parser.py`、`radar/docx_parser.py`、`radar/xlsx_parser.py`、`radar/pptx_parser.py`，以及 main 的 `radar/document_parser.py`（text/Markdown capability 版本）。
- `parse` CLI（main `radar/cli.py:275` 起），可选依赖 `requirements-*.txt`，`capability-registry-tests.yml`、`discovery-domain-tests.yml`，以及 main `tests.yml` 的 `pdf-optional/docx-optional/xlsx-optional/pptx-optional` jobs。

**C. 分支独有**

- `radar/discover.py`、`radar/legacy.py`、`radar/github_discovery.py`、`radar/code_analyzer.py`、`radar/business_graph.py`、`radar/business_invariants.py`、`radar/business_observation_extractor.py`、`radar/business_table_evidence.py`、`radar/observation_aggregator.py`、`radar/ledger_*.py`。
- 分支的 `radar/document_parser.py` 是 **143 行的旧版**，只有 `extract_csv_document` / `extract_office_document`；main 的同名文件是 capability 版 parser，两者不是同一接口。
- 分支的 `cli.py` 顶层 `from .discover import ...`、`from .business_graph import ...`、`from .ledger_* import ...`，`import radar.cli` 会加载 Ledger/Business/GitHub/Code 模块；main 的 `cli.py` 用 `importlib` 懒加载 parser。这是 M15-C 的 import 边界未达成，不是风格问题。

### 2.3 为什么不能整包合并（P0-1）

具体冲突不是“文本冲突需要手工选边”，而是**语义回退**。普通 `git merge` 不会自动删掉 main 新增、分支从未拥有的文件（例如 `capabilities.py`），但会在下列 modify/modify 文件上产生必须人工裁决的冲突；只要按分支侧解决，就会发生回退：

- 分支 `radar/cli.py` 没有 `parse` 子命令，也没有 `CapabilityRegistry`；若采用分支侧，main 的 `radar parse` 消失。
- 分支 `radar/document_parser.py` 没有 main 的 `TextDocumentParserCapability` 等类；若采用分支侧，main 的 parser capability/CLI 断链。
- 分支 `.github/workflows/tests.yml` 没有 main 的四个 optional parser jobs；若采用分支侧，这些 CI 门禁消失。
- 分支没有 `requirements-*.txt`、`xml_safety.py`、`github_asset_inventory.py`；普通 merge 会保留这些 main 文件，但分支的旧 `document_parser.py` 会绕过 `xml_safety.py`，分支的旧 `README`/dependency 文档会覆盖 main 的 M15-D/M16 描述。
- 分支测试 259 与 main 测试 191 有交集但不相等；整包合并无法证明两边能力同时保留。

**修法**：不要 merge，按 §7 的顺序 replay/cherry-pick 分支独有模块到当前 main；每次提交前先 fetch 最新 main，保留 main 的 parser/capability/CI/依赖文件。需要改 `radar/document_parser.py` 时，采用“main capability 版 + 分支的 CSV/Office helper 作为独立模块”的方式，而不是覆盖。

**验收标准**：

```bash
# 以 40c0528 为基线建立分支，合并后应满足：
python3 -m radar --help | grep -E 'parse|discover|ledger-control'
python3 -m unittest discover -s tests          # main + 分支测试并集全绿
diff <(git show main:radar/xml_safety.py) radar/xml_safety.py   # 仍存在
test -f requirements-pdf.txt && test -f requirements-docx.txt
# .github/workflows 同时保留 main 的 optional jobs 和分支的 discover smoke
```

只要出现 `parse` 消失、`requirements-*.txt` 删除、`xml_safety.py` 删除、optional parser job 减少，就算未完成。

---

## 3. P0（合并/正确性/安全阻塞）

### P0-2 表格链丢弃 `transaction_fields`，退货/过账语义对 CSV/XLSX 永不生效

**位置**：`radar/business_table_evidence.py:97-123`（选表）；`radar/business_observation_extractor.py:117-132`、`:220-239`（提取器其实支持 transaction）；`radar/observation_aggregator.py:273-325`（语义消费）。

**证据**：

- `select_required_table_chunks` 的 `selected_fields = required + [scope...]`（`:106`），只把 invariant 的 `fields` + `target_field` + `scope_fields` 选进来；`transaction_fields`（`docstatus`、`is_return`、`return_against`、`doctype` 等）完全不参与选列。
- 因此 GitHub/本地表格路径产生的 chunks 里没有 transaction 列，`extract_table_observations` 的 `transaction={}`；即使调用方手工把 transaction 塞进 chunks，选表阶段也已经把它们过滤掉。
- 带 `transaction_semantics` 的 aggregation 在 `observation_aggregator` 中发现 transaction 不完整，按 `unverified_transaction_metadata` 跳过；weak-current 的 `purchase_order_receipts_total` 会变成“无观测”，而不是“退货已计算”。
- `tests/test_return_quantity_cap.py` 是手工构造带 transaction 的 observation，绕过了 `select_required_table_chunks` 和 `extract_table_observations`，所以 259 个测试全绿也覆盖不到这条链。

**影响**：这是分支最核心的“业务不变量”卖点。当前 CSV/XLSX 路径只能算简单数量平衡，凡涉及 posted/return/dedup 的规则都不生效；而文档 `docs/BUSINESS-GRAPH.md` 与 `packs/weak-current/business-model.json` 把它们写成已声明能力，属于“声明大于实现”。

**修法**：

1. `select_required_table_chunks` 把 `invariant["transaction_fields"]` 的 key 并入 `selected_fields`，并像 scope 一样在 header 中做 alias 命中检查；缺失的 transaction 列应显式产生 `skipped` 原因，而不是静默不选。
2. `extract_table_observations` 已经会用 `transaction_fields` 提取，但要求每个 transaction 字段都有 cell Evidence；补上“声明了 transaction 但选不到/没有 Evidence”时的 skip 原因。
3. `validate_observation_bundle` 或 `build_business_graph` 在调用带 `transaction_semantics` 的 aggregation 前，要求 observation 的 `transaction` 包含该规则声明的全部 `transaction_fields`；不完整应报错/跳过，不能当正常观测。
4. 增加从 CSV chunks → selector → extractor → aggregator 的端到端测试，而不是只测 aggregator。

**验收标准**：

- 给定包含 `docstatus/is_return/return_against` 列的 CSV，`select_required_table_chunks` 返回这些列；端到端得到 `transaction` 非空。
- 同一 PO 的 posted 收货 10、return 3，聚合结果为 7；未 linked 的 return 被标记 `unresolved_return_target`，不静默计数。
- 新增至少 2 个测试：正常 posted+return、缺 transaction 列必须 skip 而不是 pass。

---

### P0-3 `extract-observations` 的观察值没有绑定到 Evidence 内容

**位置**：`radar/cli.py:215-262`（命令）；`radar/business_observation_extractor.py:64-70`、`:176-193`（按 locator 找 Evidence）；`radar/business_invariants.py:85-101`（只校验 Evidence 存在/Asset/level）。

**证据**：

- `cmd_extract_observations` 读取 `--input` 后只把 `asset_id` 与 workspace 记录做存在性匹配（`:230-233`），**没有计算输入文件哈希，也没有与 `asset.metadata.content_sha256` 比较**。
- 提取器的 `evidence_by_cell` 只用 `(_cell_identity(locator))` 做键（`:66-70`）；找到 Evidence 后直接采用 chunk 的文本，不比较 Evidence 的 `statement`/`excerpt`。
- 复现：Evidence 的单元格是 `8/2/10`，把输入 CSV 同一 row/column 改成 `99/2/101`，`extract_table_observations` 输出 `99/2/101`，`validate_observation_bundle` 仍 `pass`。
- 这等于“Evidence 指向旧文件，数值来自新文件”；provenance 的 `evidence_id` 和 locator 都是真的，但 `values` 是假的。后续 `business-graph` 会把它当 `source_backed` 计算。

**影响**：只要用户改一下输入文件，就能在不改 Evidence 的情况下改变业务结论；这是审计链的根问题，比“数字算错”更严重。

**修法**：

1. CLI 计算输入 bytes 的 SHA-256；若 Asset metadata 有 `content_sha256`，必须相等；若没有，至少要求所有被引用 Evidence 的 `metadata.content_sha256` 与输入一致（GitHub asset 可用 blob hash/内容哈希补齐）。
2. 提取器在采用 cell Evidence 前，要求 Evidence 的 `statement`/`excerpt` 与该 cell 文本一致（或 Evidence 是 row-level 且其 statement 包含该 cell 文本），否则 skip 并给出 `evidence_value_mismatch`。
3. 对 `--source-path` 只允许 workspace 相对路径，禁止 `..` 穿越；路径规范化后再与 locator 比对。
4. 增加“篡改单元格”回归：同一 locator、不同值必须失败/跳过；未改动必须通过。

**验收标准**：

- 修改输入 CSV 任一被引用单元格，命令以非零退出码失败，或在输出中明确 `skipped` 且不产出该 observation；不能出现 `pass`。
- 未改动输入时结果与当前一致，且 `business-graph` 能复现相同 aggregation。
- 直接调用 `extract_table_observations` 的 API 测试也覆盖同样约束（不能只在 CLI 层加哈希）。

---

### P0-4 `rejected` / 无验证元数据的 Evidence 仍能让业务不变量 `pass`

**位置**：`radar/business_invariants.py:85-101`（Evidence 检查）、`:202-213`（结果级别）；`radar/business_observation_extractor.py:187-192`（默认 level）。

**证据**：

- `validate_observation_bundle` 检查 Evidence 存在、Asset 相同、runtime flag、`verification_level` 一致，但**从不检查 `verification_status`**。`verification_status="rejected"` 的 Evidence 与 observation 的 level 相同（`test_fixture`）时直接通过。
- 复现：test origin 的 observation + `verification_status="rejected"` 的 Evidence → `outcome=pass`，`verification_level=test_fixture`。
- `_evaluate_one` 的 `verification_level` 取的是 `origin_levels[row["origin"]]`（`:202-207`），不是 Evidence 的 `metadata.verification.level`；即使 Evidence 的 level 是 `rejected`/缺失，也会被 origin 标签覆盖。
- 提取器在 Evidence 没有 `metadata.verification.level` 时默认 `document_text`（`:190-191`、`:216-217`、`:237-238`），把“未验证”升级成“文档文本”。
- `validate_observation_bundle` 还允许声明了 scope 字段的 observation 以 `business_scope={}` 通过（只检查“多出来的字段”，不检查“缺少的 scope 字段”）。

**影响**：业务图会把被拒绝的证据显示成 `source_backed`，把无验证来源显示成文档证据；这违反 `docs/BUSINESS-GRAPH.md` 的 verification 边界，也与 Ledger 链“Evidence 必须 exact record”的正确实现形成反差。

**修法**：

1. 在 `validate_observation_bundle` 的 field/scope/transaction 三处统一拒绝 `verification_status=="rejected"`；对 `static_source` 至少要求 Evidence 的 level 是 `document_text`/`static_source`，缺 metadata 应为 `unknown` 并拒绝，而不是默认 `document_text`。
2. `_evaluate_one` 的 `verification_level` 从 Evidence metadata 读取；缺失时输出 `unknown`，不要回落到 origin 标签。
3. 要求 observation 的 `business_scope` 覆盖 invariant 声明的全部 `scope_fields`（除非 invariant 没有 scope）；缺失即报错。
4. business graph 的 evidence 边只在 Evidence 未被 rejected 时标 `source_backed`；否则标 `rejected_evidence` 或 `unverified`。
5. 测试：rejected / 无 metadata / 缺 scope 三种 observation 都必须 fail 或被 skip。

**验收标准**：

- `verification_status="rejected"` 的 Evidence 不能产生 `pass`；`business_graph` 不把它当 `source_backed`。
- 无 `metadata.verification` 的 Evidence 的 `verification_level` 为 `unknown`，静态规则不能通过。
- 声明 2 个 scope 字段、实际只给 1 个的 observation 被拒绝。

---

### P0-5 `ledger-import` 语义预检缺失：坏包先落盘，`ledger-control` 才报错

**位置**：`radar/ledger_workspace.py:11-18`（docstring 声称 full bundle preflight）、`:38-51`（effect 只查 Evidence/Asset）、`:66-99`（manifest/rule 只查 ID/重复）；`radar/ledger_effects.py:166-203`（已有 `validate_ledger_effects`）。

**证据**：

- `import_ledger_bundle` 只做 envelope 校验和 Workspace Evidence 精确匹配；没有调用 `validate_ledger_effects`、`validate_gl_vouchers`、`aggregate_ledger_effects`。
- 复现 1：缺 `ledger_kind` 的 aggregation rule 通过 `import_ledger_bundle`；随后 `ledger-control` 抛 `LedgerControlPipelineError: ledger aggregation rule missing ledger_kind`。
- 复现 2：缺 `ledger_kind` 的 ledger effect 通过 import；`run_ledger_control_pipeline` 才抛 `ledger effect validation failed: ledger_effects[0].ledger_kind must be a non-empty string`。
- 因为 collection 是 append-only，坏记录已经写入 `ledger_effects.jsonl` / `ledger_aggregation_rules.jsonl`；后续每次 `ledger-control` 都会失败，不能通过“重新导入”修复（重复 ID 会被拒绝）。
- `docs/architecture/ledger-workspace.md:12` 明确写“A bundle is preflighted for schema and duplicate identity errors before the first append”；当前实现不满足自己的文档。

**影响**：一次错误导入会把 Workspace 永久卡住；这比“导入时报错”严重，因为需要手工删 JSONL 才能恢复。

**修法**：

1. 在 append 任何记录前，构造与 `run_ledger_control_pipeline` 相同的输入，调用 `validate_ledger_effects`、`validate_gl_vouchers`、`aggregate_ledger_effects` 做完整 preflight；任何 error 直接 `StorageError`，不落盘。
2. 校验顺序：evidence 精确匹配 → effect 语义/identity → manifest 语义 → rule 语义 → 全量交叉引用；全部通过后再 append。
3. 至少保证“语义失败不留任何新记录”；文件系统中途失败仍可接受非事务，但语义错误必须在第一笔 append 前发现。
4. 测试：缺 `ledger_kind` 的 rule/effect、缺必填字段的 effect、重复 identity 的 bundle 都必须 import 失败且 workspace 记录数不变。

**验收标准**：

- 坏 bundle 返回非零/`StorageError`，`ledger_effects.jsonl` 行数不变。
- 好 bundle 仍返回与当前相同的 counts，`ledger-control` 输出不变。
- 单测覆盖“import 失败后 workspace 仍可接受合法 bundle”。

---

### P0-6 跨源 `ledger_entry_id` 冲突静默丢行

**位置**：`radar/ledger_aggregator.py:81-85`；对照正确实现 `radar/ledger_effects.py:187-205`（identity 是 `(source_system, ledger_entry_id)`）。

**证据**：

- 聚合阶段 `by_ledger_id[contribution["ledger_entry_id"]] = contribution`，key 只有 entry id，后写覆盖前写，`unique` 只剩一条；`contribution_count` 也只剩 1。
- 复现：S1/E1=5，S2/E1=7，同一 scope → `values={'qty':'7'}`、`contribution_count=1`；S1 的 5 被丢弃，`unresolved` 为空。
- `docs/architecture/transaction-ledger-semantics.md:51-52` 把 `ledger_entry_id` 与 `source_system` 分为两个字段；`ledger_effects` 已用二元组做 identity。聚合器与校验器不一致。
- `tests/test_ledger_aggregator.py:13` 只使用单一 `source_system:"erp"`，没有跨源回归。
- `radar/business_graph.py:625-626` 的 `ledger_entry_aggregation_nodes` 也只按 entry id 建键，会把不同 source 的聚合节点混到同一凭证下。

**影响**：多 ERP/多来源 Workspace 的库存或 GL 聚合会少计；而且没有任何 `skipped`/`unresolved`，审计上看起来“正常”。

**修法**：

1. `aggregate_ledger_effects` 的去重 key 改为 `(source_system, ledger_entry_id)`；`contribution` 增加 `source_system`，输出/`evidence_ids` 不受影响。
2. 同 source 同 ID 但值不同：按 `ledger_effects` 的口径进入 `skipped`（`conflicting_ledger_entry_identity`），不要静默覆盖。
3. `business_graph` 的 `ledger_entry_aggregation_nodes` 同样用二元组；voucher 的 `ledger_entry_ids` 若没有 source，改为 `(source_system, id)` 或显式 unresolved。
4. 测试：两源同 ID 不同值 → 总和 12、contribution_count 2；同源同 ID 冲突 → skipped，不进入 total。

**验收标准**：

- 上述复现输出 `{'qty':'12'}`、`contribution_count=2`、`unresolved=[]`。
- 同源同 ID 冲突有明确 skipped 记录；不能出现“无提示少一行”。

---

### P0-7 Legacy “任意非空 dict”都被当成精确 locator

**位置**：`radar/legacy.py:143-155`；文档 `docs/DISCOVERY-DATA-MODEL.md:148-149`。

**证据**：

- 条件只是 `isinstance(locator, dict) and locator and any(value not in (None,"") for value in locator.values())`；`{"note":"somewhere on page 3"}` 满足，直接升级为 Evidence。
- 复现：`convert_legacy_sources` 后 `evidence=1, pending=0`；没有进入 `pending_quotes`。
- 文档要求“有明确出处定位 / 精确 locator 才能升级”，且“不伪造行号或页码”；`{"note": ...}` 不是可复核的定位。
- 同一 Legacy quote 若 `quote_verified_this_run=true` 且 `quote_verified=false`，`_verification_status` 返回 `rejected`；这个 rejected Evidence 又会被 P0-4 放行，形成链式漏洞。

**影响**：Legacy 导入会把自然语言备注伪造为可审计 Evidence；后续业务图和需求评估会把它当来源。

**修法**：

1. 抽一个共享的 `is_precise_locator(locator, kind)`：至少要求 `path`+（`line`/`row`/`cell`/`field`）或 `url`+锚点；`page` 对 PDF 可以，但不能只有 `note`/`block` 这类自由文本。
2. `convert_legacy_sources` 使用该函数；不满足的进入 `pending_quotes`，理由保持 `missing_precise_locator` 并附实际 locator。
3. 与 `business_invariants` 的 locator key 集合统一，避免“Legacy 接受、业务校验拒绝”两套标准。
4. 测试：`note`/空 dict/只有 `block` 三种都进入 pending；`path+line`、`url+field` 通过。

**验收标准**：

- `{"note":"somewhere"}` 不再产生 Evidence；`pending_quotes` 计数为 1。
- 有 `path`+`row`（或 `cell`/`line`/`field`）的 quote 仍升级。
- 单测覆盖“不伪造行号/页码”。

---

### P0-8 分支用旧 Office 解析器替换 main 的安全解析器：ZIP 炸弹/DTD 风险

**位置**：`radar/document_parser.py:13-17`（`archive.read` 全量）、`:22-25`（DOCX）、`:129-142`（异常处理，没有大小/解压比限制）；`radar/github_discovery.py:623`（只限制 tree 中 ZIP blob 本身的 `size <= 2MB`，这是压缩容器大小，不是解压后总量）、`:672-689`（Office blob 直接 `extract_office_document`）。对照 main 的 `radar/xml_safety.py` 与 `pdf/docx/xlsx/pptx_parser.py`。

**证据**：

- 分支的旧解析器没有检查 `ZipInfo.file_size` 总和、压缩比、单 entry 上限，也没有拒绝 `<!DOCTYPE`/`<!ENTITY`；`GitHub` 文档路径只限制了 git blob 的压缩大小（2MB），解压后可以远大于此。
- `ledger_source_adapter._xlsx_rows` 有部分 XLSX 预检，但 `github_discovery` 的 Office 文档路径没有；本地 `extract-observations --input foo.xlsx` 也直接进旧解析器。
- main 已经有 `radar/xml_safety.py`（编码感知的 DOCTYPE/ENTITY 检查）和独立的 `docx/xlsx/pptx_parser.py`；分支没有这些文件。直接合并会删掉 main 的安全实现，而不是“没有新增功能”。

**影响**：`--github` 会处理不可信仓库中的 Office 文档；一个 2MB 压缩包即可造成内存/CPU 拒绝服务，或把带 DTD/实体的 XML 交给 `ElementTree`。这是安全回退。

**修法**：

1. 不要用分支的 `document_parser.py` 覆盖 main；把分支需要的 `extract_csv_document` / `extract_office_document` 兼容 helper 放到独立模块，内部调用 main 的 capability/parser。
2. 对每个 ZIP entry 检查 `file_size` 总和、单 entry 上限、压缩比；超限 fail closed，不读取 entry。
3. 读取 XML 前调用 `xml_safety.contains_forbidden_xml_declarations`；含 DTD/ENTITY 直接拒绝。
4. 给 GitHub Office 路径加与 `ledger_source_adapter` 相同的预检，并限制解压后总量。
5. 测试：构造含高压缩比 entry 的 ZIP、含 `<!DOCTYPE` 的 XML、正常 DOCX/XLSX；前两者必须 `failed` 且不产生 chunks，正常文档仍 parsed。

**验收标准**：

- 恶意 ZIP/DTD 样本被拒绝，进程内存不随解压比增长。
- 正常 DOCX/XLSX/PPTX 仍能产出与 main 相同的 chunks/locator。
- `radar parse` 与 main 的 optional parser CI 在合并后仍通过。

> 注：本条是代码审查 + 与 main 对照，未执行真实炸弹样本；验收时必须补执行。

---

### P0-9 M15 计划的基线过期，会指导重复工作

**位置**：`docs/architecture/M15-REALIGNMENT-PLAN.md:9-19`（基线）、`:130-155`（M15-B/M15-D）、`:193-198`（当前决策）。

**证据**：

- 计划写 `main HEAD=b14c8916`、`feature 197 ahead / 0 behind`；当前 main 是 `40c0528`，feature/chore 都是 **57 behind**。
- 计划把 `M15-B 依赖治理` 作为“首个实现 PR”；main 的 PR #29–#43 区间已合入依赖治理/pyproject/uv.lock/package smoke。
- 计划把 `M15-D GitHub、文档、代码解析适配器和统一契约` 列为待做；main 已在同一区间合入 capability registry、PDF/DOCX/XLSX/PPTX parser、parser CLI，以及 M16 asset inventory（#43）。
- 计划的 §8 对 import coupling 的判断仍然准确（feature 的 `discover.py`/`cli.py` 确实 eager import Ledger/Business），但它是“feature 快照”的判断，不是“当前 main 还缺这些”的判断。
- chore 分支没有代码，只有计划；如果按计划直接开 M15-B/M15-D PR，会和 main 已完成的内容冲突/重复。

**影响**：治理文档本身会把团队引向错误的工作分解；比代码 bug 更容易造成重复劳动和错误的“已完成”声明。

**修法**：

1. 重算 §1 基线：`git fetch` 后写当前 main SHA、feature/chore ahead/behind、open PR=0；不要再用 merge-base 的 `0 behind`。
2. 把 M15-B 标记为“main 已完成，仅需审计/补缺”；把 M15-D 标记为“main 已有 capability registry/parser，feature 的 `github_discovery.py` 需改为 adapter 而不是另起一套”；新增 M15-F“把 feature 独有编排/业务/Ledger replay 到 main”。
3. 保留 §8 的 import coupling 结论，但明确它描述 feature 快照；M15-C 验收要加“`import radar.cli` 不加载 Ledger/Business/GitHub 模块”。
4. 计划更新后，chore 分支仍只含文档，不把代码搬进 chore。

**验收标准**：

- 计划第 1 节的 SHA/ahead/behind 与 `gh api compare/main...<branch>` 的实时读数一致。
- 计划中不再把已合入的依赖治理、parser capability、M16 列为“待做”。
- 首个实现 PR 的标题/范围不是重复 main 的 M15-B/M15-D。

---

## 4. P1（本分支新增的正确性/可维护性风险）

### P1-1 重复表头静默取后一列

**位置**：`radar/business_observation_extractor.py:157-164`；`radar/business_table_evidence.py:99-104`。

**证据**：两个 `received_qty` 列时 `header_map[field] = column` 后者覆盖前者；复现取 `999`，无告警。测试夹具全部唯一表头（`tests/test_business_table_evidence.py`）。

**修法**：构建 header_map 时检测同一 field 的多个 column，标记 `ambiguous_headers` 并 skip 整张表；selector 同理。**验收**：重复表头 → 该表无 observations，skipped 原因明确；唯一表头不受影响。

### P1-2 数值规范化无条件删除逗号

**位置**：`radar/business_observation_extractor.py:40-49`。

**证据**：`Decimal(str(value).replace(",", ""))`；`"1,23"` → `123`，`"1,2,3"` → `123`，没有 locale 声明。**修法**：按 Pack/字段声明 `decimal_separator`/`thousands_separator`；默认只接受单一 `.` 或明确的千分位模式；歧义时 skip。**验收**：`"1,23"` 在有欧式声明时 → `1.23`，无声明时 skip 并告警；`"1,234"` 仍可解析为 1234（若声明千分位）。

### P1-3 observation 的 provenance locator 不与 Evidence locator 比对

**位置**：`radar/business_invariants.py:80-101`（field）、`:134-152`（scope）；`radar/business_observation_extractor.py:187-193`。

**证据**：provenance locator 改成 `totally-different.csv:99:7` 仍 `pass`；只检查存在/Asset/level。**修法**：field/scope/transaction 三处都要求 `provenance.locator` 与 Evidence `locator` 精确一致（或 Evidence statement 包含该 locator 的单元格）；不一致报错。**验收**：篡改 locator 的 observation 被拒绝；正常 extractor 输出仍通过。

### P1-4 缺失 verification metadata 被默认成 `document_text`，且 scope 可不完整

**位置**：`radar/business_observation_extractor.py:190-192`、`:216-218`、`:237-239`；`radar/business_invariants.py:118-136`。

**证据**：Evidence 无 `metadata.verification.level` 时 provenance 写 `document_text`；`business_scope={}` 在声明了 scope_fields 时仍通过（已复现）。**修法**：默认 `unknown`，静态校验不接受 `unknown`；scope 必须覆盖声明的全部字段。**验收**：无 metadata 的 Evidence 不能支撑 static observation；缺 scope 的 observation 被拒绝。

### P1-5 重复 discover 产生重复 Evidence（GitHub + Legacy）

**位置**：`radar/github_discovery.py:202-219`（key 含 `captured_at`）；`radar/legacy.py:156-165`（key 含 `captured_at`）；`radar/legacy.py:111`（`legacy_covers` 初始顺序）。

**证据**：同秒重跑 1 条，隔 1.2s 重跑 2 条；ID `evd_97ae…` / `evd_9813…` 不同。文档 `docs/DISCOVERY-DATA-MODEL.md:149` 要求重复导入复用同一 `captured_at`。Legacy Asset 的 `covers` 顺序变化会触发 `StorageError: duplicate immutable record id`（已复现）。**修法**：Evidence 稳定 ID 去掉 `captured_at`；已有 Evidence 复用并把本次 run 记入 `metadata.observed_runs`；`legacy_covers` 在比较/构造时排序去重。**验收**：隔 1.2s 重跑 evidence 数量不变、ID 不变；`covers` 重排不报错。

### P1-6 退货上限可被配置绕过

**位置**：`radar/business_graph.py:257-264`（只强制 item target 在 dedup_by）；`radar/observation_aggregator.py:273-320`（`target_field` 不在 identity 时直接 `continue`）。

**证据**：删掉 `deduplicate_by` 里的 `receipt_id` 后模型校验通过；原始 10、退货 11 聚合为 `-1`、`contribution_count=2`，没有 `return_quantity_exceeds_original_receipt`（已复现）。**修法**：`return_reference_target_field` 也必须在 `deduplicate_by` 中；aggregator 对缺 target 的 return 不能静默 `continue`，应记为 `unresolved_return_identity` 并排除。**验收**：上述模型被 `validate_business_model` 拒绝；或 aggregator 产生 skipped，不能得到 `-1`。

### P1-7 本地表格没有“生成 cell Evidence”的入口

**位置**：`radar/ledger_source_adapter.py:346-352`（locator 只有 `{path,row,block:"row"}`）；`radar/business_observation_extractor.py:66-70`（只按 cell locator 匹配）；`radar/cli.py:230-258`（要求已有 Evidence）。

**证据**：`ledger-adapt` 为每行生成 row-level Evidence；`extract-observations` 需要 `{path,row,column}` 的 cell Evidence。离线/本地 CSV 没有命令创建 cell Evidence，只有 GitHub discovery 路径会创建（`github_discovery.py:702-715`）。文档示例却写“本地 CSV/XLSX + asset_id”直接可用。**修法**：增加 `table-import`/`extract-observations --create-cell-evidence`（先验证 content hash，再按选中单元格写 Evidence），或让 extractor 接受 row Evidence 并在 statement 中定位单元格。**验收**：本地 CSV 一条命令完成“注册 Asset → cell Evidence → observations”，不需要手写 JSONL；篡改 content hash 仍被 P0-3 拦截。

### P1-8 Ledger adapter 为失败行留下孤儿 Evidence，且逐行全表扫描

**位置**：`radar/ledger_source_adapter.py:469-470`（先 `_get_evidence`）、`:522-525`（映射失败才 continue）；`:346-366`（每行 `store.list_records("evidence")`）；`radar/discovery_store.py:118-159`（每次 append 全表查重 + fsync）。

**证据**：evidence 在字段映射/validator 之前创建；失败行/冲突行/非法 manifest 行也会把 Evidence 写入 Workspace，`rows_with_evidence` 计入它们，后续 `evidence_by_asset` 会看到孤儿。每行 `list_records` 是 O(n) 全量读，append 又是全表 + fsync；10k 行 ERP 导出会非常慢。**修法**：先完成该行的映射与 `validate_ledger_effects`，通过后再创建/复用 Evidence；为 evidence locator/asset 建索引；批量 append 或至少避免每行 `list_records`。**验收**：无效行不产生 Evidence；10k 行 CSV 的耗时有基线（例如 < 30s）且不再出现 O(n²) 证据扫描。

### P1-9 CI/workflow 在合并时会丢门禁

**位置**：`.github/workflows/tests.yml:1-57`（分支）；`.github/workflows/package-smoke.yml:5-13`；`.github/workflows/component-benchmarks.yml:6-10`。对照 main 的 `tests.yml` 四个 optional jobs、`capability-registry-tests.yml`、`discovery-domain-tests.yml`。

**证据**：分支 `tests.yml` 有 audit + discover smoke，但没有 main 的 `pdf-optional/docx-optional/xlsx-optional/pptx-optional`；分支没有 main 的 capability/discovery 专用 workflow。分支 `package-smoke.yml` 只在 `feat/requirement-driven-discovery` 触发；`component-benchmarks.yml` 只在同名分支 + `tools/benchmarks/**` 触发。合并/改名后这些 workflow 静默停跑（或丢失 main 的 optional 门禁）。**修法**：以 main 的 workflow 为底，加入分支的 discover smoke；把触发分支改为 `main` + `pull_request`；保留 optional jobs 与 `requirements-*.txt`；benchmark 改为 `workflow_dispatch` + main/PR 可选。**验收**：PR 上能同时看到 full tests、optional parser jobs、capability/discovery tests、package smoke；main push 也运行。

### P1-10 领域契约只声明 8 类对象，代码/存储新增 3 类 Ledger 记录

**位置**：`schemas/discovery.schema.json:5`、`:10`、`:1013-1038`（8 类、8 前缀）；`radar/discovery.py:13-17`（11 前缀）、`:34-38`（ledger_effect/manifest/rule）；`docs/DISCOVERY-DATA-MODEL.md:7`、`:34`、`:153-154`。

**证据**：`PREFIXES` 有 `lef/lmn/lar`，`REQUIRED` 有 3 类 Ledger 记录；schema 的 `DiscoveryRecord` 没有它们，id pattern 也不允许这些前缀；文档说“八类对象、Schema 覆盖八类”。当前 `validate_record` 是手写校验，不跑 JSON Schema，所以测试不会暴露。**修法**：要么在 schema 增加三类 `$defs`/oneOf 和前缀（并加 schema 测试），要么在文档中明确 Ledger 是“内部存储类型，不属于 Discovery 契约”，且 `validate_record` 不声称覆盖 schema。**验收**：任一 ledger 记录能被声明的契约验证，或文档明确排除且无“8 类/Schema 覆盖”冲突；新增测试 `schemas` 与 `PREFIXES`/`REQUIRED` 一致。

### P1-11 GitHub token 被发到 raw.githubusercontent.com，下载没有大小上限

**位置**：`radar/github_discovery.py:649-652`（raw URL + `Authorization: Bearer`）；`radar/verify.py:37-44`（`_curl_text` 无 `--max-filesize`、无 `--proto-redir`）。**证据**：raw host 是内容 CDN，不需要 API token；把 token 发给它扩大泄露面。`--github` 文档抓取/网页校验使用 `_curl_text`，任意 URL 可返回大文件，只有 tempfile 和 timeout。**修法**：raw fetch 不带 Authorization；只对 `api.github.com` 带 token；加 `--max-filesize`（例如 10MB）和 `--proto-redir =https`；拒绝非 https 重定向。**验收**：抓取公开文档不发送 token；超限 URL 返回明确错误，不写大文件。

### P1-12 文档数值/渲染漂移（259 vs 254、字面 `\n`、pyproject、行业数）

**位置**：`README.md:302`、`:323`、`:324`；`docs/architecture/dependency-management.md:72`；`docs/BUSINESS-GRAPH.md:51`；`docs/OPEN_SOURCE_COMPONENT_SELECTION.md:58`。

**证据**：README 仍写“254 个用例”“两个行业的种子来源”（实际 4 个 seeds），dependency-management 写“254 tests”，BUSINESS-GRAPH 第 51 行把整个 M12 段落压成一行并含字面 `\n`，OPEN_SOURCE 写“尚未发现 pyproject.toml”但仓库已有 pyproject。**修法**：测试数改为动态/当前值（259）；行业数改为 4；修复 Markdown 换行；OPEN_SOURCE 改为“已有 pyproject，M14-D 决策见 ...”。**验收**：`grep -n "254\|两个行业\|尚未发现 pyproject"` 无命中；`BUSINESS-GRAPH.md` 渲染出独立小节。

---

## 5. P2（维护性/性能/文档一致性）

- **P2-1 绝对 `file://` Asset URI**：`ledger_source_adapter.py:328-342` 用 `asset_path.as_uri()` 写绝对路径；文档 `ledger-workspace.md:72` 说用 Workspace 相对路径避免依赖导入机器路径。修法：Asset URI 用 workspace-relative logical URI，原绝对路径只放 metadata；测试移动 workspace 后仍可读。
- **P2-2 `discover` 的 `parameters` 写入绝对路径**：`discover.py` 的 run parameters 含 `workspace_root`/输入路径；分享 Workspace 会泄露本机路径。修法：只存 basename/相对路径 + 单独 machine-local metadata（不入库）。
- **P2-3 `package-smoke` 只触发 feature 分支**：`package-smoke.yml:5-13` 不含 `main`；合并后 main 不跑 wheel/sdist。修法：加 `main` + `pull_request`。
- **P2-4 `component-benchmarks` 只在 feature 分支 + tools 路径触发**：`component-benchmarks.yml:6-10`；分支改名/合并后基准静默停跑。修法：改为 `workflow_dispatch` + 可选 `main`/PR 触发，保留 pinned packages；考虑 `--require-hashes`。
- **P2-5 `_add_edge` 不去重**：`business_graph.py:331-339` 直接 append；同一 observation/ledger 多次进入可能产生重复边与 counts 膨胀。修法：按 edge id 去重或构建时用 dict；测试重复输入边数稳定。
- **P2-6 `github_discovery` 搜索上限的“每批”语义**：`_search_terms` 以 4 个术语为一批，每批各 `limit`，实际每需求/类型可超过 `--github-limit`；文档/CLI 写“候选上限”。修法：跨批累计计数，超过即停；测试。
- **P2-7 `discovery_store` 聚合规则查重键错误**：`discovery_store.py:141-143` 用 `self.get(kind, data["rule_id"])` 比较的是记录 `id`（`lar_...`）与业务 `rule_id`，永远不命中；直接 `store.append` 可写入重复 rule_id（`import_ledger_bundle` 有额外检查，但存储层不防御）。修法：按 `rule["rule_id"]` 查重；测试直接 append 重复 rule 被拒绝。

---

## 6. chore/m15-architecture-realignment 专项

### 6.1 现状

- 相对 main：200 ahead / 57 behind；相对 feature：3 commits，唯一独有文件是 `docs/architecture/M15-REALIGNMENT-PLAN.md`（217 行）。
- 计划的方向（不 squash、不直改 main、按完整功能单元拆 PR、保留只读审计分支）是正确的；§8 对 import coupling 的判断也准确（`discover.py`/`business_graph.py`/`cli.py` 的 eager import）。
- 但 §1/§4/§7 的基线和“第一 PR”已经过期，见 P0-9。

### 6.2 结论

**chore 分支不应与 feature 一起合并，也不应作为“功能分支”继续开发。** 它应保持“只含治理文档”的定位，在 feature 完成 rebase 后更新计划；否则会把“计划”与“实现”混在同一个 PR。

### 6.3 具体改法

- 改 `docs/architecture/M15-REALIGNMENT-PLAN.md:9-19`：写当前 main/feature/chore SHA 与实时 ahead/behind；删除“0 behind”。
- 改 `:130-137`：M15-B 标记为“main 已在 #29–#43 区间完成，本计划只做审计/补缺”，不要作为首个实现 PR。
- 改 `:148-155`：M15-D 标记为“main 已有 capability registry/parser/parse CLI；feature 的 `github_discovery.py` 需改为 adapter 并复用 main parser”，不要另起一套。
- 新增 M15-F（或等价小节）：按 §7 的顺序，把 feature 独有模块 replay 到当前 main；每个 PR 先保留 main 的 parser/capability/CI。
- 保留 `:201-217` 的 import coupling 结论，但把验收写成“`import radar.cli` 不加载 Ledger/Business/GitHub 模块”。

**验收标准**：计划中的每个数字都能用 `gh api compare` 复算；计划中不再出现已合入项作为待办；chore 分支 diff 仍只有文档。

---

## 7. 建议的合入顺序（修正版）

> 注：收到独立复核后，§11.6 把顺序调整为“证据契约先行”，并把 main P0 与分支 replay 拆成两条 PR 线。本节保留原始拆分依据；实际排期以 §11.6 为准。

> 原则：先恢复 main 的能力边界，再按领域拆分支增量；每个 PR 都能独立回滚，不把“修 P0”和“搬 197 个提交”混在一起。

1. **PR-0（治理，chore）**：更新 M15 计划基线（P0-9）；只改文档。
2. **PR-1（Discovery 编排 + Legacy，基于 main）**：
   - 新增 `radar/discover.py`、`radar/legacy.py`；把 `discover` 命令接入 main 的 `cli.py`，保持 `parse`/`CapabilityRegistry` 与懒加载。
   - 不引入 business/ledger；先修 P0-7、P1-5（legacy locator/captured_at/covers 顺序）。
   - 验收：`radar discover` 离线路径通过；`radar parse` 仍通过；`import radar.cli` 不加载 Ledger/Business。
3. **PR-2（表格观察 + 业务图）**：
   - 新增 `business_table_evidence.py`、`business_observation_extractor.py`、`business_invariants.py`、`observation_aggregator.py`、`business_graph.py`。
   - 修 P0-2、P0-3、P0-4，P1-1/2/3/4/6；补端到端测试。
   - 验收：transaction 端到端生效；篡改输入/拒绝 Evidence/缺 scope 都失败；259+ 测试全绿。
4. **PR-3（Ledger）**：
   - 新增 `ledger_effects.py`、`ledger_vouchers.py`、`ledger_aggregator.py`、`ledger_source_adapter.py`、`ledger_workspace.py`、`ledger_control_pipeline.py`、CLI 命令。
   - 修 P0-5、P0-6，P1-7/8；补多源聚合、非法导入、10k 行基准。
   - 验收：坏包不落盘；跨源同 ID 总和不丢；本地 CSV → cell Evidence → observations 的一条链路可用。
5. **PR-4（GitHub / 文档适配，复用 main 能力）**：
   - 新增 `github_discovery.py`，但文档解析统一走 main 的 parser/capability；修 P0-8、P1-11。
   - 保留 main 的 `xml_safety.py`、optional parser jobs、M16.
   - 验收：GitHub 文档解析有 ZIP/DTD 防护；`parse` 和 optional CI 同时通过。
6. **PR-5（文档/CI/基准）**：
   - 修 P1-9、P1-12，P2-1..7；把 `.github/workflows` 对齐 main + 分支新增 smoke。
   - 验收：PR/main 都跑完整门禁；文档数字与代码一致。

**不建议**：把 feature 直接 rebase 成单个 PR；rebase 只能解决文本冲突，不能解决“main 有 parser、分支要旧 parser”的语义冲突，也不能替代上述 P0 测试。

---

## 8. 与首轮 main 评审的交叉

| main 评审项 | 分支状态 | 说明 |
|---|---|---|
| P0-1 `--web` 自产自证 | 仍在 | 分支 `web.py`/`model.py`/`coverage.py` 未修；与分支新增表格链无关，但共享同一“自证”模式 |
| P0-2 GitHub/Gitee 跨查询 ID 冲突 | 仍在 | 分支 `adapters.py` 只改超时/异常，ID 逻辑未改；与 P0-6 的“跨源 ID”是同类问题在不同层 |
| P0-3 审计盲区/基线可覆盖 | 仍在 | 分支 `tests.yml` 有 audit，但 `run_demo.sh` 仍覆盖基线；CI 修复未做 |
| P0-4 20k 截断判 false | 仍在 | 分支 `web.py`/`verify.py` 未做截断状态 |
| — | **新增 P0-2..P0-8** | 表格 transaction、证据绑定、rejected Evidence、ledger 预检/聚合、legacy locator、Office 安全 |
| — | **新增 P0-9** | M15 治理基线过期；chore 分支专属 |

**不要**在分支评审里重复把 main P0 当“分支新发现”；它们是既有问题。分支评审的价值是：即使忽略 main P0，分支独有代码仍有上述阻塞。

---

## 9. 做得好的地方（合并时应保留）

- **Ledger Workspace 的 Evidence 信任边界**：`discovery_store.py:128-136` 要求 ledger effect/manifest 的 Evidence 属于同一 Asset 且 locator 精确相等；`ledger_workspace.py:28-47` 要求 supplied Evidence 与 Workspace 记录完全相等。这是正确的方向，应复用到业务 observation（P0-3/P0-4）。
- **`adapt_ledger_source` 的逐行校验**：`:518-525` 对每行先 `validate_ledger_effects`，失败进 unresolved；`_get_asset` 内容寻址 + 写入后 SHA-256 复核（`:302-326`）。
- **确定性 ID/模型 digest**：`discovery.py` 的 `_stable_id`、business graph 的 `model_digest`、`ledger_aggregator` 的 `sha256(rule|scope)` 都让输出可复现。
- **M15 §8 的诚实自述**：明确 `discover.py`/`business_graph.py`/`cli.py` 的跨层 import，没有把“已完成重构”写成事实。
- **Command 的失败边界**：未初始化 workspace、Pack lock 不一致、外部 Evidence 引用都会明确报错并 exit 1，没有静默继续。

---

## 10. 复核边界

- 本文的 P0-2..P0-8 结论均来自分支快照的代码 + 直接 Python API 复现；未在真实 GitHub 在线/大仓库/10k 行 ERP 上复现。
- P0-8 的 ZIP/DTD 是代码审查结论；验收时必须实际构造恶意样本，而不是只看代码。
- 未做实际 rebase/merge；P0-1 的文件回退清单来自 `diff -rq` 与 `git compare`，不是冲突演练。合并前应在临时 worktree 做一次 `git merge --no-commit` 并检查删除文件列表。
- 未审 Gitee 在线能力（分支没有 main 的 `gitee_capability.py`）；未审 M16 asset inventory 在分支的等价实现（不存在）。
- 行号会随 rebase 变化；修复时以函数名/断言为准，不要机械按行号打补丁。
- 本文不替代首轮 main 评审；两份文档应一起读：`docs/reviews/2026-11-22-main-review.md` + 本文。

---

## 11. 对独立复核意见的回应与证据矩阵

> 本节回应另一模型对本文的复核。它明确说明自己只看到结构化摘要、没有逐行看代码，因此下面的“接受/校准”都以本文已有的复现和文件证据为准，不把外部判断直接当成事实。

### 11.1 我接受的关键调整

1. **先建立 Evidence 内容绑定与可信度状态契约，再按模块拆 PR。**
   原 §7 把 P0-3/P0-4 放在“表格观察 + 业务图”PR 内，容易变成只修一个函数。更合适的顺序是：先定义 `Evidence → Observation → Invariant → graph/report` 的统一状态传播规则和内容绑定字段，再让表格、Ledger、Web 各自接入。PR-1 应当是这个契约 + 反向测试，而不是先搬业务图。

2. **P0-3 与 P0-4 必须作为一个完整闭环。**
   只做“输入文件哈希”不够；还要保证：
   - Evidence 的 `verification_status` 在 field/scope/transaction 三处都被消费；
   - `rejected` 不产生 `pass`，也不产生 `source_backed`；
   - `unknown`/缺失元数据不被默认成 `document_text`；
   - 旧 Observation 在 Evidence 内容变化后失效，而不是继续引用旧 ID。
   这需要 shared helper + 每个消费者都调用，不能只修 `business_invariants`。

3. **P0-6 不只是换聚合 key。**
   跨源同 ID 可能是两笔独立业务，也可能是同一事件的镜像导出。修复时必须先定义身份：
   - 候选聚合身份至少是 `(source_system, ledger_kind, ledger_entry_id)`；
   - 同身份不同值 → `skipped/unresolved`，不能静默覆盖；
   - 不同 source 的同 ID 是否相加，取决于 Pack/适配器的“business event / mirror”声明；默认不能假设相加，也不能假设去重。
   因此 P0-6 的验收要同时覆盖“独立两笔 → 相加”和“镜像两笔 → 去重/标记”两种语义。

4. **P0-7 不是“拒绝所有旧 dict”。**
   旧格式中可能有明确约定的 locator schema，应该做显式迁移/映射；无法识别的自由文本（`note`）只能进 `pending_quotes`，不能升级为 Evidence。修复应增加 locator schema 版本/迁移规则，而不是一刀切拒绝历史数据。

5. **测试必须包含反向用例和跨模块链路。**
   局部单测全绿不能证明数据链正确；每个 P0 至少要有“错误输入不能蒙混过关”的测试，并有一条从 Asset → Evidence → Parser → Observation → Invariant → Graph/Report 的端到端用例。

### 11.2 需要校准的地方

1. **“197 ahead / 57 behind”本身确实不能证明“整包合并必然丢功能”。**
   本文的 P0-1 不是只靠 ahead/behind 得出的；文件级证据是：
   - 分支 `radar/cli.py` 没有 `parse` 子命令，main 有；
   - 分支 `radar/document_parser.py` 是 143 行旧版，main 是 capability 版；
   - 分支没有 `capabilities.py`、`xml_safety.py`、`requirements-*.txt`、`github_asset_inventory.py`；
   - 分支 `.github/workflows/tests.yml` 没有 main 的四个 optional parser jobs。
   普通 merge 不会自动删除 main 新增、分支从未拥有的文件；但如果 `cli.py`/`document_parser.py`/workflows 的冲突按分支侧解决，就会发生回退。准确表述是：**不能整包合并，且不能把 197 个提交都当成必须保留的整体；应基于最新 main 逐项 replay。** 本文 §2.3 已按这个口径修正。

2. **缺陷优先级是决策辅助，不是事实。**
   独立复核把 P0-3、main P0-1、P0-4 排在前三，是合理的“审计可信度”排序；本文的 P0-1 排最后，是“产品缺陷”排序。两者不冲突，但必须分开写：
   - **操作上最先**：冻结整包合并、确认基线（P0-1/P0-9）；
   - **产品上最先**：Evidence 绑定与状态传播（P0-3/P0-4）；
   - **数据完整性**：Ledger 导入/聚合（P0-5/P0-6）。
   不要用一个编号同时表达三种维度。

3. **P0-6 的 `ledger_kind` 也要进入身份。**
   独立复核建议 `source_id + ledger_kind + ledger_entry_id`，比本文只写 `(source_system, ledger_entry_id)` 更完整；同一来源的 stock 与 GL 行可能共享 entry id。聚合器应按规则 `ledger_kind` 限定，再在同 kind 内做身份判定。

4. **P0-4 的“修复成本低—中”只对单个判断成立，对全局状态传播不成立。**
   加 `if rejected: continue` 是低；但要让 observation、aggregation、graph、report 都不再把它当 `source_backed`，并补跨模块测试，成本至少是中等。不要按“单点补丁”估工期。

5. **main P0 与分支 P0 要分开排期。**
   main P0-1（Web 自证）、main P0-3（审计目录）、main P0-4（截断）是主线既有问题；分支 P0-2..P0-8 是 replay 时的增量。把它们混进同一个“PR-1”会让分支 replay 变成主线重构，难以回滚。建议主线/分支各一条 PR 线，只在契约层共享测试。

### 11.3 P0 证据矩阵（已证实 / 部分证实 / 待验证）

| 编号 | 证据位置 | 触发条件 | 状态 | 仍需补 |
|---|---|---|---|---|
| P0-1 | `radar/cli.py`（无 `parse`/`CapabilityRegistry`）、`radar/document_parser.py`（143 行旧版）、`.github/workflows/tests.yml`、文件清单 | 基于当前 main 做 merge/rebase | **文件级已证实；merge 演练未做** | 临时 worktree `git merge --no-commit`，检查 `parse`、optional jobs、`xml_safety.py` 是否保留 |
| P0-2 | `business_table_evidence.py:106`、`business_observation_extractor.py:117-132/220-239` | `transaction_fields` 非空的 invariant + CSV/XLSX chunks | **已复现**（`transaction={}`，aggregator skip） | selector→extractor→aggregator 端到端测试 |
| P0-3 | `cli.py:215-262`、`business_observation_extractor.py:64-70` | 修改输入文件，locator 不变 | **已复现**（99/2/101 通过） | content hash + statement/excerpt 绑定；所有 parser 接入 |
| P0-4 | `business_invariants.py:85-101`、`:202-213` | `verification_status="rejected"` 或缺失 metadata | **已复现**（pass/test_fixture） | 全局状态传播；graph 不标 `source_backed` |
| P0-5 | `ledger_workspace.py:38-99` | 缺 `ledger_kind` 的 rule/effect | **已复现**（import 成功后 pipeline 报错） | 语义 preflight；失败零落盘；文件系统失败边界 |
| P0-6 | `ledger_aggregator.py:81-85` | 两源同 entry id 不同值 | **已复现**（5+7→7，count=1） | 独立 vs 镜像语义；`ledger_kind`；graph 链路 |
| P0-7 | `legacy.py:149-150` | locator=`{"note":"..."}` | **已复现**（Evidence=1，pending=0） | 旧 locator schema 迁移；pending 保留原文 |
| P0-8 | `document_parser.py:13-17/22-25/129-142`、`github_discovery.py:623/672-689` | 高压缩比 ZIP、DTD/ENTITY | **代码证实；恶意样本未执行** | 实际样本；main `xml_safety` 复用；解压总量/比例限制 |
| P0-9 | `M15-REALIGNMENT-PLAN.md:9-19/130-155/193-198` | 用计划中的基线开 PR | **已核实**（main `40c0528`；feature/chore 57 behind） | 更新计划；用实时 compare 复算 |
| main P0-1/3/4 | 首轮 main 评审对应位置 | Web/审计/截断 | **首轮已复现；本轮未重跑** | 与分支 replay 分开修 |
| main P0-2 | `adapters.py` 跨查询 ID | 多查询命中同一对象 | **首轮已复现；本轮未重跑** | 与 P0-6 一起做来源身份治理 |

### 11.4 Evidence 可信度状态契约（建议冻结）

| Evidence 状态 | 可用于 | 不可用于 |
|---|---|---|
| `rejected` | 保留审计记录、显示拒绝原因 | `pass`、`source_backed`、聚合计入、需求支持 |
| `unverified` / `unknown` | 候选、待复核、提示 | `pass`、强结论、默认 `document_text` |
| `source_confirmed` | 在 locator + 内容绑定一致时支撑静态结论 | runtime 结论、自动升级为 `reproduced` |
| `reproduced` / runtime | 在对应 runtime metadata 存在时支撑 runtime 结论 | 无 runtime 证据的静态结论 |
| 缺 `metadata.verification` | 只作 `unknown` | 默认 `document_text`/`test_fixture` |

**Observation 状态规则**：

- 只有 field、scope、transaction 三类 provenance 全部满足“Evidence 未 rejected + locator 精确匹配 + 内容绑定一致”，Observation 才能标 `verified`。
- 任一缺失/不一致 → `unknown`；Evidence rejected → `rejected`；不能默认成通过。
- Observation 必须记录 `asset_content_sha256`（或等价版本标识）与 Evidence locator；输入内容变化时旧 Observation 失效。
- `source_backed` 只在 Evidence 状态允许且内容绑定一致时使用；否则 `unverified`/`rejected_evidence`。

### 11.5 反向测试矩阵（修复验收的最低集合）

| 场景 | 必须保证 |
|---|---|
| 输入文件内容改变，Evidence 未更新 | 旧 Observation 不能 `pass`/`source_backed` |
| 工具自动抽取 quote | 不得自动获得 `verified` 身份 |
| Evidence=`rejected` | 不得支撑 `pass`；graph 不标 `source_backed` |
| 正文截断，quote 在截断区外 | `unknown`，不是 `false` |
| Ledger 缺必填字段 | 不得留下部分导入记录 |
| 两源同 `entry_id` | 不静默覆盖/丢弃；独立/镜像语义有明确输出 |
| ZIP 炸弹 / 恶意 XML | 安全拒绝或受控失败，不产生 chunks |
| 审计用错目录 | 非零退出，不 PASS |
| 重复表头 / 欧式小数 | 明确 skip/按声明解析，不静默取错 |
| `return_reference_target_field` 不在 dedup | 模型拒绝，或 return 进 unresolved，不能算出 `-1` |
| 跨模块链路 | Asset → Evidence → Parser → Observation → Invariant → Graph/Report 全链路通过，且篡改任一点会失败 |

### 11.5.1 失败测试骨架（已落地，仅评审用）

失败测试放在 `tests/review_p0/`，**不在**正常 `tests/test_*.py` 发现路径内；当前 main 的 `unittest discover -s tests` 仍是 191 OK。用：

```bash
python3 tests/review_p0/run.py --branch-root /tmp/rdd
```

对 `feat/requirement-driven-discovery@07c6ec7b` 的运行结果是 **13 tests, 13 failures**；覆盖 P0-2/3/4/5/6/7/8、P1-1/2/4/5 和 P0-1 的 `parse`/`xml_safety` 保留检查。修复者应把这些测试移到对应 PR 的 `tests/`，而不是在 review-only 目录里改到绿。

### 11.6 调整后的 PR 顺序

独立复核的“证据可信度先行”是对的；但 main P0 与分支 replay 不应混在同一个 PR。建议：

| 阶段 | PR | 范围 | 合并门槛 |
|---|---|---|---|
| 0 | PR-0 基线与治理 | 更新 M15 基线；冻结整包合并；确认 main SHA | 后续分支基于最新 main |
| 1a | PR-1a 主线证据状态 | main P0-1（Web 自证）、main P0-4（截断 unknown） | 反向测试通过；不改分支 replay |
| 1b | PR-1b Evidence 契约 | 分支 P0-3/P0-4 + shared status/content binding helper + 反向测试 | 所有消费者使用同一契约 |
| 2 | PR-2 Discovery/Legacy | P0-7、P1-5；main P0-2 的来源身份规则 | 旧数据不再制造假精确定位 |
| 3 | PR-3 表格/业务图 | P0-2；接入 PR-1b 契约 | CSV/XLSX 端到端 + 篡改测试 |
| 4 | PR-4 Ledger | P0-5/P0-6；P1-8 | 坏包零落盘；跨源语义明确 |
| 5 | PR-5 Parser/安全 | P0-8；复用 main `xml_safety`/parsers | 恶意样本拒绝；main parser 保留 |
| 6 | PR-6 文档/CI/基准 | P1-9/P1-12/P2 | PR/main 门禁完整；数字一致 |

**P0-1 不是产品缺陷 PR，而是 PR-0 的准入门槛**；**P0-9 是 PR-0 的文档产物**。把两者混进业务 PR 会让“修 bug”和“搬历史”互相阻塞。

### 11.7 结论

这份独立复核最有价值的地方不是它重排了 P0，而是它指出了**契约层缺失**：Radar 的问题不是“某个函数漏了过滤”，而是 Evidence 状态、内容版本、Observation 生命周期没有统一规则。本文接受这一点，并把原 §7 的“先搬 Discovery”调整为“先冻结契约、再按模块 replay”。

但外部复核只看到摘要，不能替代下面的边界：

- P0-2..P0-7 已有直接复现；P0-8 尚未执行恶意样本；P0-1 尚未做实际 merge 演练。
- 任何修复都必须以本文的反向测试和矩阵状态为准；不能因为“另一个模型同意”就跳过复现。
- 下一步不是立刻开 PR-1：PR-0（基线/治理）和本文 §11.3–11.5.1 的证据矩阵/反向测试骨架已经具备；真正开始实现前，应先由独立修复者确认这 13 个失败用例的预期，再按 §11.6 从 PR-1a/1b 进入。
