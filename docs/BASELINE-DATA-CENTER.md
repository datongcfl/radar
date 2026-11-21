# data-center-ops 基线（v1.7.0）

## 数字

| 项 | 值 |
| --- | ---: |
| 公开来源 | 40 |
| selected / needs_review | 10 / 30 |
| 模块 / 子系统 | 10 / 16 |
| strong / evidence / mention / none | **0 / 20 / 6 / 0** |
| 单源单元 | 15（M03、M05、M06、M07、M10、S01、S02、S03、S06、S07、S09、S11、S12、S13、S15） |

对应产物：`runs/data-center-ops-demo/`。  
`state_hashes: OK`；`tools/audit_ledger.py --pack packs/data-center-ops/pack.json --seeds seeds/data-center-ops.json --run runs/data-center-demo` PASS。

## 来源构成

- 5 条通用底座：标准 / 招投标 / 企业 / 统计 / 报告；
- 15 条 GitHub 工具：Prometheus、Grafana、LibreNMS、Centreon、Netdata、NUT、Telegraf、collectd、OpenBMC、Ansible、NetBox、openDCIM、RackTables、ZoneMinder、Alertmanager；
- 20 条厂商/行业页：Vertiv、Schneider、Eaton、Raritan、Sunbird、Nlyte、Device42、Uptime、TIA、OCP、GreenGrid、DCD、DCK、DCF、DC Map、Cummins、Siemens、HID、Axis、IBM Maximo。

## 为什么 strong 是 0

- 所有 GitHub 来源只到 `readme`，没有 `real_artifact/code_tests/production`；
- 厂商/底座来源是 `metadata`，最高 mention；
- 因此 20 evidence、6 mention、0 none，但没有 strong。

## 已知缺口

- 6 个 mention：M08、M09、S04、S05、S08、S14；
- 15 个单源：M03、M05、M06、M07、M10、S01、S02、S03、S06、S07、S09、S11、S12、S13、S15；
- 这些是下一轮补证方向；第三 pack 只证明可替换，不证明完整。

## v1.6 补证

- Raritan PDU、Generac 柴发、Siemens 消防、IBM Maximo、GreenGrid PUE、Sunbird 环境页升级为具体页 + quote；
- 20 evidence / 6 mention / 0 none；
- S04/S05/S08/S14 仍是真实 mention，不硬凑。

## 边界

- 40 条来源中 30 条是 needs_review；厂商/媒体页不是独立评测；
- 跨 pack 复用 NetBox/openDCIM/RackTables/ZoneMinder，不增加独立性；
- 不抓登录/付费/验证码；底座正文未完整抓取时保持 metadata。
