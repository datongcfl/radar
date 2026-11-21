# Roadmap

原则：每个版本只加一层；不承诺日期；先定验收，再写功能。

## v0.1 — MVP（已合并）

- pack/seeds 校验、URL 去重、覆盖度、目录/缺口/报告；
- `scan --base` 增量 diff；
- 可选 GitHub metadata；
- 10 个单测。

## v0.2.1 — Seed Lite（已合并）

- 最小 6 字段：`id/url/evidence_level/covers/quotes/status`；
- 其余字段默认值；
- `--strict` 保留 v0.1 完整校验；
- 12 个单测。

## v0.2.2 — 账本层 scan --since（已合并）

- 来源级变更：新增、移除、字段变化（`evidence_level/covers/quotes/license/access/version/content_hash/etag`）；
- `scan --since <旧 run>` 写 `changes.md` + `changes.json`，同时保留覆盖 diff；
- 19 个单测；
- **明确不做**：网络 `--fetch`，不假装已经抓网页；抓取留给 adapter。

## v0.2.3 — Gitee adapter（已合并）

- `GITEE_TOKEN`（env 或 `~/.config/radar/gitee_token`）；
- `Authorization: Bearer`，token 不进 URL/日志；
- `--gitee` + `source_map.gitee` 查询；
- 只做公开仓库 metadata，license 默认 `needs_review`；
- 无 token 明确跳过；
- 21 个单测。

## v0.2.4 — Forward snowballing（已合并）

- GitHub forks：从已选 GitHub 来源取 fork；
- 继承 parent 的 `covers`，`why_selected=forward: fork of <id>`；
- 只做 metadata，不读正文；
- 可选 `--snowball --snowball-per-source --snowball-max`；
- **不做**：GitHub dependents、Gitee forks、引用图（后续）。

## v0.2.5 — 网络 --fetch（已合并）

- `--fetch`：curl 抓 URL 的 ETag/Last-Modified/正文 hash；
- 更新 `http_status/last_seen/content_hash/etag/last_modified`；
- 401→login_required，403→blocked，404→deleted；
- `--fetch-limit` 控制条数；
- 与 `scan --since` 配合：hash 变了就报变化。

## v0.2 — 可迭代

目标：从“手动重跑”变成“只处理变化”。

- 来源状态：`last_seen`、`etag`、`content_hash`、`version`、`license_hash`；
- `scan --since`：只抓变化，不重跑全量；
- 定时触发（cron / DSH schedule）；
- diff 区分：新增、内容变化、许可变化、覆盖变化、删除/归档；
- **forward snowballing**：dependents、fork 网络、文档交叉引用（不能只盯已有来源，否则是引用回音室）；
- **最小种子字段**：`id/url/evidence_level/covers/quotes/status` 六项即可录入，其余由 adapter 补全。

验收：同一批来源，改一个页面/一个 release，`scan` 只报那一处变化。

## v0.3 — 网页抽取 + 许可提示（已合并，v0.3.0）

- `--web`：curl 抓公开 HTML，stdlib 解析 title/description/正文/短引用；
- `--web-limit` 控制条数；
- 最小许可识别：MIT/Apache/GPL/AGPL/LGPL/MPL/BSD/Unlicense/CC0/proprietary；
- 许可只做提示，不替代人工复核；不执行 JS、不绕登录；
- 31 个单测；
- 非 2xx 不冒充 200；中文按标点切句；许可只认强信号；
- **未做**：Playwright/登录页/PDF/OCR/docling/ScanCode；v0.3 只完成静态网页 + 提示。

## v0.3 — 多平台（原方向）

目标：不只 GitHub。

- Gitee adapter（token 或 `site:gitee.com`）；
- 网页正文（trafilatura）与浏览器（Playwright，可选）；
- 文档抽取（docling）；
- 许可扫描（grant / ScanCode）+ 人工复核。

验收：同一模块至少来自 2 个平台；许可状态可解释；不绕过登录。

## v0.4 — Claim 账本（已合并，v0.4.0）

- `radar claims` 读取已有 run + 手工 claim 文件；
- 置信度规则：strong 0.80 / evidence 0.60 / mention 0.30；
- 单源/同 host 上限 0.55，无 quote 上限 0.40，矛盾上限 0.40；
- `contradicts` 非空 → `contested`；
- 输出 `claims.md`、`claims.json`、`review.csv`；
- 39 个单测；claim.covers 与来源 covers 无交集 → `unsupported_by_sources`，置信度 ≤0.30；矛盾双向标记；review.csv 防公式注入。

## v0.4 — 证据层（原方向）

目标：从“来源清单”变成“主张账本”。

- claim schema：主张、来源、独立性、可验证性、矛盾、置信度；
- `single_source` / `contradiction` / `evidence_level` 进入报告；
- 明确 `EV_RANK` 是“存在性阶梯”，不是“质量排序”；
- 人工复核队列（CSV/Markdown，Label Studio 后置）；
- 覆盖度从“来源数”升级为“证据强度”。

验收：每条关键主张有 URL + quote + 置信度；矛盾不被强行合并。

## v1.7.0 — 数据正确性（本 PR）

- `infer_covers` 对 ai/dc/ups/bim/kv 等短词加词边界；
- `canonical_url` 剥 `.git`，GitHub/Gitee owner/repo 统一小写；
- 77 个单测。

## v1.6.0 — data-center 补证（已合并，v1.6.0）

- Raritan / Generac / Siemens / IBM Maximo / GreenGrid / Sunbird 具体页 + quote；
- data-center 从 11 evidence / 15 mention → **20 evidence / 6 mention / 0 none**；
- 15 个单源，S04/S05/S08/S14 仍 mention；
- 77 个单测。

## v1.5.1 — 第三真实 pack：data-center-ops（已合并，v1.5.1）

- 10 模块 / 16 子系统 / 40 条来源；
- 复用 issue #20 五类底座，补行业垂直来源；
- 0 strong / 11 evidence / 15 mention / 0 none；
- 7 个单源，0 个 none；
- 77 个单测。

## v1.5.0 — 通用来源底座（已合并，v1.5.0）

- `docs/SOURCES-BASE.md`：标准/招投标/企业/统计/报告五类；
- weak-current 新增 SRC-035（GB 50311-2016）；
- 35 条来源，30 selected / 5 needs_review；
- 77 个单测。

## v1.4.1 — 缺口补证据（已合并，v1.4.1）

- weak M02 保持 none（“全链条”quote 不直接证明立项/台账）；M10 由 SRC-012 竣工验收段落补证据；
- video S07 用 Obsidian Templates 官方文档、S13 用 Obsidian Mobile 官方页；
- weak 3 strong / 20 evidence / 8 mention / 6 none；
- video 0 strong / 26 evidence / 0 mention / 0 none；
- 77 个单测。

## v1.4.0 — 自动化（已合并，v1.4.0）

- `scan --fail-on-change`：有变化退出 2，无变化 0，失败 1；
- `scripts/scan_all.sh`：三个 pack 一起 scan，带 verify；
- cron/DSH 示例：`docs/AUTOMATION.md`；
- 77 个单测。

## v1.3.0 — Claim 完整性（已合并，v1.3.0）

- claim 只认 `quote_verified=true` + `quote_verified_by=web` 的来源；
- `no_verified_source` 上限 0.40；
- `unsupported_by_verified_sources` 上限 0.30；
- `next_action` 区分“先跑 --verify-quotes / 换已验证来源或改主张”；
- 77 个单测。

## v1.2.0 — 证据清理（已合并，v1.2.0）

- SRC-008 从 SSL 失败的 docs 换成 OpenProject GitHub README；
- weak-current 恢复 **3 strong**（M01/M06/M13）/ 19 evidence / 9 mention / 6 none；
- video-kb 仍 0 strong / 24 evidence / 2 mention / 0 none；
- 77 个单测。

## v1.1.0 — 通用 quote 验证（已合并，v1.1.0）

- `--verify-quotes`：GitHub/Gitee/网页抓正文，归一化子串校验；
- weak-current 实抓后：2 strong / 20 evidence / 10 mention / 5 none；
- video-kb 实抓后：0 strong / 24 evidence / 2 mention / 0 none；
- 77 个单测。

## v1.0.0 — Schema 契约冻结（已合并，v1.0.0）

- `schemas/pack|seeds|claims|state.schema.json`；
- `docs/SCHEMA.md` / `docs/MIGRATION.md`；
- `schema_version` 冻结为 1，软件版本 1.0.0；
- 63 个单测。

## v0.7.0 — 第二真实 pack：video-kb（已合并，v0.7.0）

- video-kb 从 15 → **30 条**公开来源；
- 10 模块 / 16 子系统：0 strong / 25 evidence / 1 mention / 0 none；
- 9 个单源，S07 是唯一 mention；
- 同一套引擎，不改代码；基线：[docs/BASELINE-VIDEO-KB.md](docs/BASELINE-VIDEO-KB.md)；
- 63 个单测。

## v0.6.1 — 防伪 hardening（已合并，v0.6.1）

- `--require-web-verify`：忽略 seeds 自带验证标记，只认本次 `--web`；
- claims 层 proprietary cap 0.40；
- `canonical_url` 默认端口 80/443 归一；
- rejected 来源不再把 covers/quotes 并进 selected；
- `.gitattributes`：JSON/JSONL 强制 LF；
- 63 个单测。

## v0.6.0 — Quote 验证（已合并，v0.6.0）

- `quote_verified: true/false/unknown`；
- strong 要求至少 2 host + `quote_verified: true`；
- `--web` 做归一化子串校验；
- seeds 不再有人工 true；当前 strong=0，等 --web 机器验证；
- 63 个单测。

## v0.5 — 弱电真实来源（已合并）

- 13 → 34 条公开来源；
- 3 strong / 21 evidence / 8 mention / 5 none；
- 13 个单源、8 个同源待印证、5 个无证据；缺口是真实方向，不再用宽 covers/短 quote 凑 strong；
- 已删除不属于通用弱电主线的 S24；
- 新增来源以公开 README/metadata 为主，4 条许可 needs_review；
- 基线：[docs/BASELINE.md](docs/BASELINE.md)；
- 63 个单测。

## v0.5b — 第二真实行业包（待定）

目标：证明换行业不是 smoke test。

- 第二个真实行业 pack（30–50 条来源，不是 3 条占位）；
- 与人工基线对比：覆盖召回、许可判对率、耗时；
- 记录“哪些查询有效、哪些平台没价值”。

验收：换 pack 不改引擎；覆盖度能指导下一轮搜索。

## v1.0 — 稳定契约

- engine/pack/ledger schema 冻结；
- 迁移脚本与版本兼容；
- 文档、测试、handoff 完整；
- 可选：DSH plugin / MCP wrapper（不是核心）。

验收：旧 pack 能在新引擎跑；坏数据有明确报错；交接不靠口头。

## 不承诺

- 不承诺具体日期；
- 不承诺“收集所有开源信息”；
- 不承诺自动写 PRD；
- 不承诺绕过登录/付费/验证码；
- 不承诺单源结论等于事实。
