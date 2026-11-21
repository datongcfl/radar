# 弱电管理系统 · 雷达运行报告

Run: `20261121-081328` · Pack: `weak-current` v0.1.0 · Radar: v1.7.0

## 一句话

本次用 35 条来源，覆盖 14 个管理模块 + 23 个子系统；强/证据/提及/空 = 3/20/8/6。

## 平台覆盖

| 平台 | 来源数 |
| --- | ---: |
| docs | 1 |
| gitee | 5 |
| github | 25 |
| web | 4 |

## 低星但高覆盖的发现

- `SRC-001` [EEOPS 弱电工程运营管理系统](https://gitee.com/shmilytqq/eeops) — 1★，覆盖 3 格，管理主线 + 18 子系统 + 报价 Excel 分析，最贴近弱电；但只能读，不能抄。
- `SRC-003` [弱电智能化工程项目管理系统（PMS）](https://github.com/fanzhuangzhuang000-svg/Project-Management-System) — 0★，覆盖 3 格，0 星但业务主线最完整，含实际成本/动态毛利/发票勾稽/UI 令牌。
- `SRC-004` [BidCraft 弱电投标文件编制系统](https://github.com/yaoyongli1974-dotcom/BidCraft) — 0★，覆盖 2 格，事实台账 + 行业规则包 + 生成门禁，是证据/许可约束的最好参考。
- `SRC-005` [smart-system-costing 智能化项目估算](https://github.com/wanglizuishuai-arch/smart-system-costing) — 0★，覆盖 3 格，MIT，容量/清单/取费/毛利公式可直接借鉴；0 星但对口。
- `SRC-006` [CAD 弱电点位与网络拓扑存档系统](https://github.com/FnGas/cad-topo-system) — 1★，覆盖 2 格，CAD 点位/拓扑/DXF 回导，正好补 M03 的交互与数据模型。
- `SRC-007` [myerp 弱电/安防工程商业务管理](https://github.com/kaier0922/myerp) — 4★，覆盖 3 格，MIT，报价→合同→应收→项目成本主线，可交叉验证 PMS。
- `SRC-009` [HC 物联网系统（社区/园区设备）](https://gitee.com/bigstar2018/MicroCommunityIot) — 0★，覆盖 4 格，Apache-2.0，设备模型/点位授权/道闸监控，补 S05/S06/S13/S17。

## 访问/许可需要注意

- `SRC-001` access=public, license_status=proprietary：Gitee 未声明许可证，README 写私有；18 个子系统来自 4 份酒店报价，不是行业标准；未验证代码与 README 是否一致。；covers 仅保留 quote 能直接支撑的单元；已移除过短 quote
- `SRC-002` access=public, license_status=proprietary：厂商文章，不是标准；第二套 18 与 EEOPS 只有约 12 个重叠，说明 18 是常见桶数，不是固定清单。；covers 仅保留 quote 能直接支撑的单元；仅短标题/描述，降为 mention
- `SRC-003` access=public, license_status=proprietary：专有许可，禁止复制/修改/分发；README 是产品说明，不是独立验证；0 星。；covers 仅保留 quote 能直接支撑的单元；已移除过短 quote
- `SRC-004` access=public, license_status=proprietary：专有许可；偏投标文件，不是项目管理全流程；不能抄代码/文档。
- `SRC-006` access=public, license_status=needs_review：未声明许可证；只支持 DXF，不是 DWG；无版本/审计。；covers 仅保留 quote 能直接支撑的单元
- `SRC-008` access=public, license_status=needs_review：通用项目管理，不是弱电专用；GPL 需注意分发。；covers 仅保留 quote 能直接支撑的单元；SRC-008 只支撑 M01 的项目管理半部分，不覆盖往来单位/客户/供应商/分包
- `SRC-011` access=public, license_status=proprietary：商业闭源产品博客，不是独立评测；不能抄实现。；covers 仅保留 quote 能直接支撑的单元；仅短标题/描述，降为 mention
- `SRC-012` access=public, license_status=proprietary：厂商文章，不是标准；作为竣工验收/资料断点参考。；covers 仅保留 quote 能直接支撑的单元
- `SRC-013` access=public, license_status=proprietary：厂商官方页，产品视角；深度手册可能需登录；不代表行业通用。；仅短标题/描述，降为 mention
- `SRC-016` access=public, license_status=needs_review：仅公开 README/metadata，未读代码；参考用
- `SRC-017` access=public, license_status=needs_review：仅公开 README/metadata，未读代码；参考用
- `SRC-024` access=public, license_status=needs_review：仅公开 README/metadata，未读代码；参考用
- `SRC-028` access=public, license_status=needs_review：仅公开 README/metadata，未读代码；参考用
- `SRC-035` access=public, license_status=needs_review：['国家标准馆页面，正文/阅读器未完整抓取；仅 metadata']

## 单源模块

- `M07` 合同与变更（evidence）
- `M10` 竣工与验收（evidence）
- `M11` 实际成本与毛利（evidence）
- `S07` 入侵/防盗报警（evidence）
- `S08` 周界防范（evidence）
- `S15` 程控电话/通讯（evidence）
- `S16` IPTV（evidence）
- `S17` 有线电视（evidence）
- `S18` 停车场（evidence）
- `S21` 五方对讲（evidence）
- `S23` 公区温控联网（evidence）

## 来源清单

| ID | 标题 | 平台 | 等级 | 许可 | 访问 |
| --- | --- | --- | --- | --- | --- |
| `SRC-001` | [EEOPS 弱电工程运营管理系统](https://gitee.com/shmilytqq/eeops) | gitee | strong | proprietary（不可复用） | public |
| `SRC-002` | [德立云：18 大系统构建智能世界](https://www.deliyun.com/newsinfo/8795439.html) | web | mention | proprietary（不可复用） | public |
| `SRC-003` | [弱电智能化工程项目管理系统（PMS）](https://github.com/fanzhuangzhuang000-svg/Project-Management-System) | github | evidence | proprietary（不可复用） | public |
| `SRC-004` | [BidCraft 弱电投标文件编制系统](https://github.com/yaoyongli1974-dotcom/BidCraft) | github | evidence | proprietary（不可复用） | public |
| `SRC-005` | [smart-system-costing 智能化项目估算](https://github.com/wanglizuishuai-arch/smart-system-costing) | github | mention | MIT | public |
| `SRC-006` | [CAD 弱电点位与网络拓扑存档系统](https://github.com/FnGas/cad-topo-system) | github | evidence | unknown（需复核） | public |
| `SRC-007` | [myerp 弱电/安防工程商业务管理](https://github.com/kaier0922/myerp) | github | mention | MIT | public |
| `SRC-008` | [OpenProject 项目管理](https://github.com/opf/openproject) | github | evidence | GPL-3.0（需复核） | public |
| `SRC-009` | [HC 物联网系统（社区/园区设备）](https://gitee.com/bigstar2018/MicroCommunityIot) | gitee | mention | Apache-2.0 | public |
| `SRC-010` | [idcops 数据中心资源管理](https://gitee.com/decbe/idcops) | gitee | mention | Apache-2.0 | public |
| `SRC-011` | [PinMy 安装公司图纸钉点](https://pinmy.co/zh/blog/app-for-installers-zh/) | web | mention | proprietary（不可复用） | public |
| `SRC-012` | [众和：弱电工程信息孤岛](https://www.zhonghesoft.com/xwzx/gcgl/itemid_3590.html) | web | evidence | proprietary（不可复用） | public |
| `SRC-013` | [海康威视 服务支持/工具专区](https://www.hikvision.com/cn/support/) | web | mention | proprietary（不可复用） | public |
| `SRC-014` | [easyaiot](https://gitee.com/soaring-xiongkulu/easyaiot) | gitee | mention | MIT | public |
| `SRC-015` | [iot_api](https://gitee.com/ttgzs/iot_api) | gitee | mention | MulanPSL-2.0 | public |
| `SRC-016` | [openremote/core](https://github.com/openremote/core) | github | evidence | NOASSERTION（需复核） | public |
| `SRC-017` | [thingsboard/thingsboard](https://github.com/thingsboard/thingsboard) | github | evidence | NOASSERTION（需复核） | public |
| `SRC-018` | [netbox-community/netbox](https://github.com/netbox-community/netbox) | github | evidence | Apache-2.0 | public |
| `SRC-019` | [openhab/openhab-core](https://github.com/openhab/openhab-core) | github | evidence | EPL-2.0 | public |
| `SRC-020` | [domoticz/domoticz](https://github.com/domoticz/domoticz) | github | evidence | GPL-3.0 | public |
| `SRC-021` | [grokability/snipe-it](https://github.com/grokability/snipe-it) | github | evidence | AGPL-3.0 | public |
| `SRC-022` | [glpi-project/glpi](https://github.com/glpi-project/glpi) | github | evidence | GPL-3.0 | public |
| `SRC-023` | [osTicket/osTicket](https://github.com/osTicket/osTicket) | github | evidence | GPL-2.0 | public |
| `SRC-024` | [opendcim/openDCIM](https://github.com/opendcim/openDCIM) | github | evidence | unknown（需复核） | public |
| `SRC-025` | [RackTables/racktables](https://github.com/RackTables/racktables) | github | evidence | GPL-2.0 | public |
| `SRC-026` | [zabbix/zabbix](https://github.com/zabbix/zabbix) | github | evidence | AGPL-3.0 | public |
| `SRC-027` | [ZoneMinder/zoneminder](https://github.com/ZoneMinder/zoneminder) | github | evidence | GPL-2.0 | public |
| `SRC-028` | [asterisk/asterisk](https://github.com/asterisk/asterisk) | github | evidence | NOASSERTION（需复核） | public |
| `SRC-029` | [node-red/node-red](https://github.com/node-red/node-red) | github | evidence | Apache-2.0 | public |
| `SRC-030` | [OpenEMS/openems](https://github.com/OpenEMS/openems) | github | evidence | AGPL-3.0 | public |
| `SRC-031` | [tvheadend/tvheadend](https://github.com/tvheadend/tvheadend) | github | evidence | GPL-3.0 | public |
| `SRC-032` | [prathimacode-hub/Ezy-Parking](https://github.com/prathimacode-hub/Ezy-Parking) | github | evidence | GPL-3.0 | public |
| `SRC-033` | [TechnionYP5777/SmartCity-ParkingManagement](https://github.com/TechnionYP5777/SmartCity-ParkingManagement) | github | mention | Apache-2.0 | public |
| `SRC-034` | [snapcast/snapcast](https://github.com/snapcast/snapcast) | github | mention | GPL-3.0 | public |
| `SRC-035` | [GB 50311-2016 综合布线系统工程设计规范](https://www.ndls.org.cn/standard/detail/a500845f55497d65da6786ef11060758) | docs | mention | unknown（需复核） | public |

## 边界

- 大多数来源只到 metadata/readme/docs，不等于代码已验证；
- 专有来源只进参考池，不进可复用池；
- 覆盖度不是完整性证明，只是“有没有证据”的导航。
