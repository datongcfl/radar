# 弱电管理系统 · 雷达运行报告

Run: `20261126-093238` · Pack: `weak-current` v0.1.0 · Radar: v1.7.0

## 一句话

本次用 53 条来源，覆盖 14 个管理模块 + 23 个子系统；强/证据/提及/空 = 9/20/8/0。

## 平台覆盖

| 平台 | 来源数 |
| --- | ---: |
| docs | 6 |
| gitee | 7 |
| github | 29 |
| web | 11 |

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
- `SRC-013` access=unreachable, license_status=proprietary：厂商官方页，产品视角；深度手册可能需登录；不代表行业通用。；仅短标题/描述，降为 mention
- `SRC-016` access=public, license_status=needs_review：仅公开 README/metadata，未读代码；参考用
- `SRC-017` access=public, license_status=needs_review：仅公开 README/metadata，未读代码；参考用
- `SRC-024` access=public, license_status=needs_review：仅公开 README/metadata，未读代码；参考用
- `SRC-028` access=public, license_status=needs_review：仅公开 README/metadata，未读代码；参考用
- `SRC-035` access=unreachable, license_status=needs_review：['国家标准馆页面，正文/阅读器未完整抓取；仅 metadata']
- `SRC-037` access=public, license_status=needs_review：SourceForge 页面标注 GNU General Public License version 2.0 (GPLv2), Other License，含商业扩展，需人工复核；通用企业项目管理，非弱电专用。
- `SRC-038` access=public, license_status=proprietary：文档页声明 All rights reserved 且 Project initiation request 属 Enterprise 商业增强功能，仅作流程参考，不可直接复用实现。
- `SRC-039` access=public, license_status=needs_review：官网首页声明 GNU Public License (GPL) 但未标明具体版本号，需复核；偏 UPS/PDU 电源设备监控与协议，不含机房精密空调与机房布局。
- `SRC-040` access=public, license_status=needs_review：Debian 软件包页未内联完整许可证正文（上游 apcupsd 为 GPL-2.0，需复核）；聚焦 APC UPS 监控与断电关机，不含机房装修与精密空调。
- `SRC-041` access=public, license_status=needs_review：文档页未显式声明文档许可证（NetBox 源码为 Apache-2.0，需复核）；侧重 DCIM 机柜配电与功率利用率建模，不含蓄电池后备时长选型。
- `SRC-042` access=public, license_status=needs_review：仅核对公开 README 与仓库文件/测试目录，未完整搭建宿主环境运行；仓库未声明 LICENSE（license_status=needs_review），0 星。
- `SRC-044` access=public, license_status=needs_review：百科综述页面，非具体软件工程实现；CC-BY-SA-4.0 许可标记为 needs_review。
- `SRC-047` access=public, license_status=needs_review：Debian 稳定版软件包页面，侧重主机硬件温度/电压/风扇传感器采集；GPL-2.0 许可标记为 needs_review。
- `SRC-049` access=public, license_status=needs_review：Screenly/Anthias 仓库 LICENSE 声明为 GPLv2 与 Commercial 双许可，按规则标为 needs_review；文档聚焦播放器部署、资产排期、REST API 与多屏控制器。
- `SRC-050` access=public, license_status=needs_review：Xibo 社区版 CMS 采用 AGPL-3.0 协议，部分高级播放器为商业扩展，按规则标为 needs_review；本页为 Displays 章节手册，其余章节未逐页抓取。
- `SRC-052` access=public, license_status=needs_review：GitLab 开源嵌入式客房控制器毕业设计仓库（越南语 README，未声明 LICENSE 故标为 needs_review）；包含 ADC/DAC/I2C RTC/PWM/SPI/UART/digital_input.c 等硬件驱动源码，不含酒店 PMS 对接。

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
| `SRC-013` | [海康威视 服务支持/工具专区](https://www.hikvision.com/cn/support/) | web | mention | proprietary（不可复用） | unreachable |
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
| `SRC-035` | [GB 50311-2016 综合布线系统工程设计规范](https://www.ndls.org.cn/standard/detail/a500845f55497d65da6786ef11060758) | docs | mention | unknown（需复核） | unreachable |
| `SRC-036` | [Eywe 项目管理系统](https://gitee.com/eywe-butler/eywe) | gitee | strong | MIT | public |
| `SRC-037` | []project-open[ - Project Server](https://sourceforge.net/projects/project-open/) | web | strong | GPL-2.0（需复核） | public |
| `SRC-038` | [Project initiation request (Enterprise add-on) - OpenProject](https://www.openproject.org/docs/user-guide/projects/project-initiation-request/) | docs | evidence | proprietary（不可复用） | public |
| `SRC-039` | [Network UPS Tools - Welcome](https://networkupstools.org/) | web | strong | GPL（需复核） | public |
| `SRC-040` | [Debian -- Details of package apcupsd in bookworm](https://packages.debian.org/bookworm/apcupsd) | web | strong | unknown（需复核） | public |
| `SRC-041` | [Power Feed \| NetBox Labs Docs](https://docs.netbox.dev/en/stable/models/dcim/powerfeed/) | docs | evidence | unknown（需复核） | public |
| `SRC-042` | [jetlinks-v2/cloud-patrol-ui 园区智能巡更系统前端](https://github.com/jetlinks-v2/cloud-patrol-ui) | github | strong | unknown（需复核） | public |
| `SRC-043` | [zhousiraaa/mypoc 融合对讲与巡更平台](https://gitee.com/zhousiraaa/mypoc) | gitee | strong | Apache-2.0 | public |
| `SRC-044` | [Guard tour patrol system - Wikipedia](https://en.wikipedia.org/wiki/Guard_tour_patrol_system) | web | evidence | CC-BY-SA-4.0（需复核） | public |
| `SRC-045` | [pimoroni/enviroplus-python](https://github.com/pimoroni/enviroplus-python) | github | strong | MIT | public |
| `SRC-046` | [IPMI2 Monitoring \| Apache HertzBeat - Agentless Monitoring System](https://hertzbeat.apache.org/docs/help/ipmi/) | docs | strong | Apache-2.0 | public |
| `SRC-047` | [Debian -- Details of package lm-sensors in trixie](https://packages.debian.org/stable/lm-sensors) | web | strong | GPL-2.0（需复核） | public |
| `SRC-048` | [concerto/concerto](https://github.com/concerto/concerto) | github | strong | Apache-2.0 | public |
| `SRC-049` | [Anthias Documentation](https://anthias.screenly.io/docs/) | docs | strong | GPL-2.0（需复核） | public |
| `SRC-050` | [What is a Display? \| Xibo Docs](https://docs.xibosignage.com/user-manual/displays) | docs | evidence | AGPL-3.0（需复核） | public |
| `SRC-051` | [microsoft/SmartHotel360-IoT](https://github.com/microsoft/SmartHotel360-IoT) | github | strong | MIT | public |
| `SRC-052` | [Hotel Room Controller (GitLab)](https://gitlab.com/thangnguyentien/hotel-room-controller/-/raw/main/README.md) | web | strong | unknown（需复核） | public |
| `SRC-053` | [SmartHotel360 Reference Architecture Portal](https://microsoft.github.io/SmartHotel360/) | web | strong | MIT | public |

## 边界

- 大多数来源只到 metadata/readme/docs，不等于代码已验证；
- 专有来源只进参考池，不进可复用池；
- 覆盖度不是完整性证明，只是“有没有证据”的导航。
