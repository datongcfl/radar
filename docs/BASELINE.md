# 弱电 pack 基线（v1.7.0）

## 数字

| 项 | 值 |
| --- | ---: |
| 公开来源 | 53 |
| selected / needs_review | 45 / 8 |
| 模块 / 子系统 | 14 / 23 |
| strong / evidence / mention / none | **9 / 20 / 8 / 0** |
| 单源单元 | 11 |
| 无证据单元 | 0（已清零） |

对应产物：`runs/weak-current-demo/`。  
`state.json` 的 `seeds_sha256` / `pack_sha256` 与仓库内文件逐位一致。

## 这个基线为什么变保守了

上一版有 30 strong。复核发现两个问题：

1. 宽 `covers` 来源（例如一个来源覆盖 30 个单元）把“相关性”当成了“证据”；
2. 12 条 quote 只是标题/短描述，不足以支撑主张。

本次修正：

- 所有 `covers ≥ 5` 的来源压到最多 3 个单元；
- 12 条短 quote 降为 `mention`，`limitations` 写明“仅短标题/描述”；
- 新增 `tools/audit_ledger.py`，审计宽 covers、宽来源独占单元、短 quote；
- v1.0 结果是 3 strong / 21 evidence / 8 mention / 5 none；
- v1.7.0 用 `--verify-quotes --require-web-verify` 实抓后：3 strong（M01/M06/M13）/ 20 evidence / 8 mention / 6 none；
- M01 恢复：SRC-008 从 SSL 失败的 docs 换成 OpenProject GitHub README，成为第二个验证通过的独立 host；
- **M02 仍为 none**：SRC-001 的“全链条”是概括，不直接证明立项单/台账/项目阶段，不能挂 covers；
- **M10 补证据**：SRC-012 补真实“竣工验收/资料”段落，从 mention 升 evidence；
- 2026-11-26 补齐 `M02`（`SRC-036` Eywe / `SRC-037` ]project-open[ / `SRC-038` OpenProject 立项向导）与 `S04`（`SRC-039` NUT / `SRC-040` Debian `apcupsd` / `SRC-041` NetBox PowerFeed），以及最后 4 个无证据子系统 `S09`（`SRC-042`~`SRC-044`）、`S11`（`SRC-045`~`SRC-047`）、`S14`（`SRC-048`~`SRC-050`）、`S22`（`SRC-051`~`SRC-053`），各自达到 3 个独立 host 联网验真；结果升至 **9 strong（M01/M02/M06/M13/S04/S09/S11/S14/S22）/ 20 evidence / 8 mention / 0 none**；
- 验证器修复了 Markdown 链接和 GitHub description 的误判，5 条真实 quote 恢复；4 条数据 quote 按原文修正/降级。

## strong 的集中度

3 个 strong（M01 / M06 / M13）的 `real_artifact` 支撑都来自 `SRC-001`（Gitee EEOPS）。  
它们不是三处独立确认；`SRC-001` 一旦失效，3 个 strong 会同时受影响。这是当前基线的结构性风险，不藏在数字后面。

## 真实缺口

无证据：无（`M02`、`S04`、`S09`、`S11`、`S14`、`S22` 已全部补证至 `strong`）。

单源：`M07`、`M10`、`M11`、`S07`、`S08`、`S15`、`S16`、`S17`、`S18`、`S21`、`S23`。

同源待印证（≥2 条证据但同一 host）：`M08`、`M14`、`S01`、`S02`、`S03`、`S10`、`S12`、`S13`。

这些是下一轮搜索的真实方向；不再用“商用厨房排油烟”这类不属于通用弱电的模块凑数。

## 来源构成

- 1 条底座来源：GB 50311-2016 综合布线标准页（SRC-035，metadata，未完整抓正文）。

- 13 条原有来源：弱电工程系统、报价/成本、图纸、项目管理、设备台账；
- 21 条新增来源：弱电/智能化项目、设备/资产/布线、楼宇/能源、视频/停车/IPTV/背景音乐/电话、工单、低代码联动。

新增来源里不少是**相邻领域开源组件**（NetBox、GLPI、Zabbix、openHAB 等），不是“弱电行业管理系统”的等价物；`limitations` 已标明“仅公开 README/metadata，未读代码”。

## 结论

34 条不等于完整；单源/无证据单元仍然存在。  
下一步应优先补 S04/S09/S11/S14/S22，或者做第二行业 pack / v1.0 契约冻结，而不是继续堆来源。
