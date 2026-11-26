# radar · 最小行业雷达（v1.7.0）

**A minimal industry radar: does every module in your industry outline actually have evidence?**

Give it an industry outline (`pack`) and a list of sources (`seeds`). It reports, module
by module, what is backed by evidence, what is only mentioned, and what is empty — plus a
source ledger, a gap list, and a diff between runs.

Zero dependencies, Python 3.9+, runs offline. Coverage levels: `strong` / `evidence` /
`mention` / `none`; a single source can never reach `strong`, by design.

```bash
python3 -m radar run --pack packs/weak-current/pack.json \
  --seeds seeds/weak-current.json --title "example" --out runs/demo
```

> 中文说明见下方。This English summary is for search visibility and first-time visitors.


输入一个行业 pack 和一批来源，输出：**目录 + 来源账本 + 覆盖度 + 缺口 + 报告 + diff**。

不是爬虫，不是通用搜索引擎，也不是自动写 PRD。它只做一件事：**把“目录每一块有没有证据”算清楚。**

## 快速开始

```bash
cd <repo>

python3 -m radar validate \
  --pack packs/weak-current/pack.json \
  --seeds seeds/weak-current.json
# 可选：--strict 要求 v0.1 的完整 12 字段

python3 -m radar run \
  --pack packs/weak-current/pack.json \
  --seeds seeds/weak-current.json \
  --title "弱电管理系统" \
  --out runs/weak-current-demo

# 第二次：基于上次 run 做增量扫描
python3 -m radar scan \
  --pack packs/weak-current/pack.json \
  --seeds seeds/weak-current.json \
  --title "弱电管理系统" \
  --out runs/weak-current-demo-v2 \
  --since runs/weak-current-demo
```

`scan` 会在新 run 里多写 `changes.md`（来源级新增/移除/变化）和 `diff.md`（覆盖变化）。

输出：

```text
runs/weak-current-demo/
├── sources.jsonl     # 每条来源：平台/URL/许可/访问/证据/覆盖
├── coverage.json     # 模块×来源的覆盖矩阵
├── changes.md        # 仅 scan 生成：来源级变更（新增/移除/字段变化）
├── toc.md            # 目录：模块/子系统 + 覆盖状态
├── coverage.md       # 覆盖明细
├── gaps.md           # 无证据 + 单源待印证
├── report.md         # 汇总/低星发现/许可问题/来源清单
└── state.json        # run 元数据、pack/seeds 哈希
```

## data-center-ops 第三真实 pack（v1.7.0）

- **40 条公开来源**：10 selected / 30 needs_review；
- 覆盖：**0 strong / 20 evidence / 6 mention / 0 none**；
- 10 模块 / 16 子系统；沿用 issue #20 的五类底座 + 行业垂直层；
- 基线见 [docs/BASELINE-DATA-CENTER.md](docs/BASELINE-DATA-CENTER.md)。

## video-kb 第二真实 pack（v1.7.0）

- **32 条公开来源**：22 selected / 10 needs_review；
- 覆盖：**0 strong / 26 evidence / 0 mention / 0 none**；
- 12 个单源：M03、M07、M08、M09、S01、S06、S07、S09、S12、S13、S15、S16；
- 同一套引擎，换 pack 不改代码；基线见 [docs/BASELINE-VIDEO-KB.md](docs/BASELINE-VIDEO-KB.md)。

strong 为 0 是因为没有单元同时满足“2 独立 host + real_artifact + web 验证 quote”。

## 通用来源底座（v1.7.0）

- [docs/SOURCES-BASE.md](docs/SOURCES-BASE.md)：标准/招投标/企业/统计/报告五类底座；
- weak-current 新增 `SRC-035`（GB 50311-2016，metadata）；
- 第三 pack 先复用底座，再补行业垂直层，不再从零找 30 条。

## 多个 pack 证明可替换

```bash
python3 -m radar run \
  --pack packs/pet-hospital/pack.json \
  --seeds seeds/pet-hospital.json \
  --title "宠物医院管理系统" \
  --out runs/pet-hospital-demo
```

同一套代码，换 pack 就能跑；弱电和宠物医院互不写死。

## 弱电 pack 现状（v1.7.0）

- **41 条公开来源**：36 selected / 5 needs_review；
- 覆盖：**5 strong / 20 evidence / 8 mention / 4 none**（strong：M01/M02/M06/M13/S04）；
- 11 个单源、8 个同源待印证、4 个无证据（S09/S11/S14/S22）；`gaps.md` 有真实缺口，不再写“无缺口”；
- 审计：无 `covers ≥5` 的万金油来源、无 <40 字的空壳 quote；
- 来源包含弱电工程系统、报价/成本、设备台账、楼宇自控、视频、停车、IPTV、背景音乐、监控、工单等；
- 完整基线：[docs/BASELINE.md](docs/BASELINE.md)。

这不是“完整”，是“当前证据地图”。运行 `python3 tools/audit_ledger.py` 可复查这条基线。

### 缺口先分诊

`gaps.md` 只说明“没有证据/单源”，不代表下一轮一定要搜。先判断三种动作：

1. 补来源；2. 删模块；3. 改 pack 边界。

S24 智能厨房排油烟就是例子：它来自酒店弱电清单，偏厨房/暖通，不是通用弱电主线；正确动作是删掉，而不是去搜“商用厨房排油烟”。见 [docs/GAP-TRIAGE.md](docs/GAP-TRIAGE.md)。

## 命令

```bash
python3 -m radar run --pack <pack.json> --seeds <seeds.json> --title "<标题>" --out <dir>
python3 -m radar scan --pack <pack.json> --seeds <seeds.json> --title "<标题>" --out <dir> --base <旧 run>
python3 -m radar draft --pack <pack.json> --url <url> --covers M02 --seeds <seeds.json> --out draft.json
python3 -m radar validate --pack <pack.json> --seeds <seeds.json>
python3 -m radar diff --from <run-a> --to <run-b> --out <diff.md>
python3 -m radar claims --pack <pack.json> --run <run-dir> --claims <claims.json> --out <claims-dir>
```

可选 GitHub / Gitee 搜索（默认关闭，避免限流）：

```bash
GITHUB_TOKEN=... python3 -m radar run ... --github --limit 3 --max-queries 3
GITEE_TOKEN=...  python3 -m radar run ... --gitee  --limit 3 --max-queries 3

# 可选：forward snowballing（GitHub forks）
GITHUB_TOKEN=... python3 -m radar run ... --snowball --snowball-per-source 2 --snowball-max 5

# 可选：抓 URL 的 ETag/content_hash（网络）
python3 -m radar run ... --fetch --fetch-limit 5

# 可选：抽取公开网页正文 + 许可提示（网络，可遵守 robots）
python3 -m radar run ... --web --web-limit 5 --respect-robots
```

网络选项（`--github/--gitee/--snowball/--fetch/--web`）需要本机有 `curl`；没有会直接报错，不会逐条伪装成 `web_error`。

### Gitee（可选）

1. Gitee → 设置 → 私人令牌 → 新建，最小权限（只读 projects/仓库读取；不要给 admin/hook）；
2. 二选一：
   - `export GITEE_TOKEN=...`；
   - 写入 `~/.config/radar/gitee_token`，`chmod 600`；
3. 运行时加 `--gitee`。

token 只通过 `Authorization: Bearer` 发送，不拼进 URL、不写日志；没有 token 时 `--gitee` 会明确跳过，不会静默返回空。

细节见 [docs/GITEE.md](docs/GITEE.md)。

## 覆盖度规则

- `strong`：至少 2 个来源、至少 2 个独立 host，且至少 1 个达到 `real_artifact/code_tests/production` + `quote_verified: true`；
- `evidence`：有 `readme/docs` + quote；**单源最高只能到 evidence**；
- `mention`：只提到名字，没有 quote；
- `none`：没有来源。

单源不是不能用，是不能当“已证实”用。`gaps.md` 会单独列“单源待印证”。

### 证据阶梯的方向

`production > code_tests > real_artifact` 是**存在性阶梯**：在产系统能证明“这个做法真的存在”，不等于“工程质量更好”。  
判断质量时要另看测试、文档、维护、边界；不要把存在性排序当质量排序。

## Quote 验证（v0.6）

`strong` 不再只看“有没有 quote”，还要求 `quote_verified: true`：

- `true`：`--web` 抓取成功，且 quote 归一化后是页面正文的子串；
- `false`：页面抓到了，但 quote 不在正文里（最高 mention）；
- `unknown`：没有验证过（最高 evidence，不能 strong）。

v1.3 用 `--verify-quotes --require-web-verify` 实际抓取后：weak-current 3 strong（M01/M06/M13），video-kb 仍 0 strong；claim 只认已验证来源。详见 [docs/QUOTES.md](docs/QUOTES.md)。

## 当前 MVP 的边界

- **包含**：Seed Lite（最小 6 字段 + 默认值 + `--strict`）、pack/seeds 校验、URL 去重、覆盖度、目录/缺口/报告、`scan --since` 账本层变更检测 + 覆盖 diff、可选 GitHub/Gitee metadata 搜索、`--snowball`（GitHub forks）、`--fetch`（ETag/content_hash）、`--web`（静态正文抽取 + 许可提示，可选 `--respect-robots`）、`claims`（claim 账本 + 置信度/复核队列）、`quote_verified`（quote 子串校验）、`--verify-quotes`（抓正文校验）、`--require-web-verify`（只认本次验证）；
- **不包含**：浏览器/登录、全量爬虫、UI、自动 PRD、OCR、定时任务（scan 是手动触发）、Gitee forks、GitHub dependents/引用图；`--fetch` 只抓公开 URL 的头/体 hash；`--web` 只做静态 HTML，不执行 JS、不绕登录；Playwright/docling/ScanCode 未做，v0.3 是**部分完成**；
- **来源**：seeds 是人工/agent 填的；`--github` 只到 metadata，不读正文；
- **许可**：专有来源只进参考池，不能复用；`needs_review` 要人工复核。

## 版本与产物溯源

每次 `run` / `scan` 的 `state.json` 会记录：

- `radar_version`：当前 `radar/__init__.py` 的版本；
- `radar_commit`：运行目录所在 git 的短 commit（没有 git 时为 null）；
- `pack` / `pack_version` / `pack_sha256` / `seeds_sha256`。

`report.md` 头部也会显示 `Radar: v...`。这样别人拿到一个 run，能知道是哪个版本/commit 跑出来的。

当前代码版本 `1.7.0`。tag 由仓库 owner 打；Agent 不自行打标签。

## Claim 账本（v0.4）

```bash
python3 -m radar claims \
  --pack packs/weak-current/pack.json \
  --run runs/weak-current-demo \
  --claims examples/claims.weak-current.json \
  --out runs/claims-demo
```

输出：

- `claims.md`：主张/置信度/状态/来源/原因；
- `claims.json`：机器可读；
- `review.csv`：复核队列（含 next_action）。

规则见 [docs/CLAIMS.md](docs/CLAIMS.md)。

## Schema 契约（v1.0）

- [schemas/](schemas/)：`pack` / `seeds` / `claims` / `state` 四份 JSON Schema；
- [docs/SCHEMA.md](docs/SCHEMA.md)：字段/必填/兼容规则；
- [docs/MIGRATION.md](docs/MIGRATION.md)：版本线与旧数据读取。

`schema_version` 冻结为 `1`，软件版本 `1.7.0` 独立演进。

## 自动化（v1.4）

```bash
./scripts/scan_all.sh
```

- 四个 pack 一起 `scan`，带 `--verify-quotes --require-web-verify`；
- 有变化退出码 2，无变化 0，失败 1；
- cron/DSH 示例见 [docs/AUTOMATION.md](docs/AUTOMATION.md)。

## 路线图

| 版本 | 主题 | 关键交付 |
| --- | --- | --- |
| v0.1 | MVP（已合并） | pack/seeds、覆盖度、缺口、`scan --base`、GitHub metadata |
| v0.2 | 可迭代 | `scan --since`、来源 hash/ETag、定时触发 |
| v0.3 | 多平台 | Gitee、网页/浏览器、docling、grant/ScanCode |
| v0.4 | 证据层 | claim/置信度/矛盾/复核队列 |
| v0.5 | 弱电真实来源（当前） | 13→34 条来源 + 基线；第二行业待定 |
| v1.0 | 稳定契约 | schema 冻结、迁移、handoff、可选 plugin/MCP |

详见 [ROADMAP.md](ROADMAP.md)。不承诺日期，也不承诺“收集所有开源信息”。

## 测试

```bash
python3 -m unittest discover -s tests -v
```

77 个用例覆盖：pack/seeds 校验、Seed Lite 默认值、`--strict` 拒绝最小字段、URL 规范化、单源上限、双源 strong、mention/none、gaps、来源级变更、Gitee metadata 映射、fetch 状态、snowball fork 映射、HTML 抽取、中文 quote、404 不冒充成功、license 提示、claim 覆盖校验/双向矛盾/CSV 注入、merge 并集/ID 唯一/canonical/平台推断/许可顺序、独立 host/单源口径、坏访问、reusable、CLI 报错、残留清理、账本审计、CLI run/scan/diff。

## 交给其他 Agent

- [HANDOFF.md](HANDOFF.md)：三种交接方式（DSH skill / CLI / 只读）；
- [AGENT-TASK.md](AGENT-TASK.md)：给对方的任务书；
- `./make_handoff.sh`：打一个可发送的 tar.gz。

## 设计依据

- 路线图：[ROADMAP.md](ROADMAP.md)
- Pack 写法：[docs/PACK.md](docs/PACK.md)
- MVP 验收：[docs/MVP.md](docs/MVP.md)
- Agent 规矩：[AGENTS.md](AGENTS.md)

## 目录

```text
radar/
├── radar/            # CLI + 校验 + 覆盖度 + diff
├── packs/            # weak-current / video-kb / data-center-ops / pet-hospital
├── seeds/            # 两个行业的种子来源
├── tests/            # 77 个单测
├── docs/             # PACK / MVP
├── .dsh/skills/radar # Skill
└── runs/             # demo 输出
```