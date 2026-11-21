# 数据中心动环/DCIM · 雷达运行报告

Run: `20261121-081437` · Pack: `data-center-ops` v0.1.0 · Radar: v1.7.0

## 一句话

本次用 40 条来源，覆盖 10 个管理模块 + 16 个子系统；强/证据/提及/空 = 0/20/6/0。

## 平台覆盖

| 平台 | 来源数 |
| --- | ---: |
| docs | 5 |
| github | 15 |
| web | 20 |

## 低星但高覆盖的发现

- 本次没有「低星（≤50）但覆盖 ≥2 格」的来源；这不代表没有低星好资料。

## 访问/许可需要注意

- `DC-003` access=public, license_status=needs_review：['仅公开 README/metadata，未读代码；参考用']
- `DC-006` access=public, license_status=needs_review：['仅公开 README/metadata，未读代码；参考用']
- `DC-008` access=public, license_status=needs_review：['仅公开 README/metadata，未读代码；参考用']
- `DC-009` access=public, license_status=needs_review：['仅公开 README/metadata，未读代码；参考用']
- `BASE-STD` access=public, license_status=needs_review：['通用底座，仅 metadata，未完整抓正文']
- `BASE-TENDER` access=public, license_status=needs_review：['通用底座，仅 metadata，未完整抓正文']
- `BASE-CORP` access=public, license_status=needs_review：['通用底座，仅 metadata，未完整抓正文']
- `BASE-STAT` access=public, license_status=needs_review：['通用底座，仅 metadata，未完整抓正文']
- `BASE-REPORT` access=public, license_status=needs_review：['通用底座，仅 metadata，未完整抓正文']
- `VND-VERTIV` access=public, license_status=needs_review：['厂商/媒体页，仅 metadata；不是独立评测']
- `VND-SCHNEIDER` access=public, license_status=needs_review：['厂商/媒体页，仅 metadata；不是独立评测']
- `VND-EATON` access=public, license_status=needs_review：['厂商/媒体页，仅 metadata；不是独立评测']
- `VND-RARITAN` access=public, license_status=needs_review：['厂商产品页，只作参考；不是独立评测']
- `VND-SUNBIRD` access=public, license_status=needs_review：['厂商产品页，只作参考；不是独立评测']
- `VND-NLYTE` access=public, license_status=needs_review：['厂商/媒体页，仅 metadata；不是独立评测']
- `VND-DEVICE42` access=public, license_status=needs_review：['厂商/媒体页，仅 metadata；不是独立评测']
- `VND-UPTIME` access=public, license_status=needs_review：['厂商/媒体页，仅 metadata；不是独立评测']
- `VND-TIA` access=public, license_status=needs_review：['厂商/媒体页，仅 metadata；不是独立评测']
- `VND-OCP` access=public, license_status=needs_review：['厂商/媒体页，仅 metadata；不是独立评测']
- `VND-GREENGRID` access=public, license_status=needs_review：['厂商产品页，只作参考；不是独立评测']
- `VND-DCD` access=public, license_status=needs_review：['厂商/媒体页，仅 metadata；不是独立评测']
- `VND-DCK` access=public, license_status=needs_review：['厂商/媒体页，仅 metadata；不是独立评测']
- `VND-DCF` access=public, license_status=needs_review：['厂商/媒体页，仅 metadata；不是独立评测']
- `VND-DCMAP` access=public, license_status=needs_review：['厂商/媒体页，仅 metadata；不是独立评测']
- `DC-012` access=public, license_status=needs_review：['跨 pack 复用同一工具；不增加独立性']
- `VND-GENERAC` access=public, license_status=needs_review：['Generac 首页仅 metadata；首页正文未命中该句，不冒充 docs']
- `VND-SIEMENS` access=public, license_status=needs_review：['厂商产品页，只作参考；不是独立评测']
- `VND-HID` access=public, license_status=needs_review：['厂商页，仅 metadata；不是独立评测']
- `VND-AXIS` access=public, license_status=needs_review：['厂商页，仅 metadata；不是独立评测']
- `VND-IBM-MAXIMO` access=public, license_status=needs_review：['厂商产品页，只作参考；不是独立评测']

## 单源模块

- `M03` 制冷与环境（evidence）
- `M05` 消防与安全（evidence）
- `M06` 巡检与工单（evidence）
- `M07` 能效与PUE（evidence）
- `M10` 集成与自动化（evidence）
- `S01` 机柜/U位（evidence）
- `S02` 配电/列头柜（evidence）
- `S03` UPS/电池（evidence）
- `S06` 温湿度/漏水（evidence）
- `S07` 消防联动（evidence）
- `S09` 视频监控（evidence）
- `S11` 告警/工单（evidence）
- `S12` 巡检（evidence）
- `S13` 能效/PUE（evidence）
- `S15` 资产/维保（evidence）

## 来源清单

| ID | 标题 | 平台 | 等级 | 许可 | 访问 |
| --- | --- | --- | --- | --- | --- |
| `DC-001` | [Prometheus 监控与时序库](https://github.com/prometheus/prometheus) | github | evidence | Apache-2.0 | public |
| `DC-002` | [Grafana 可观测平台](https://github.com/grafana/grafana) | github | evidence | AGPL-3.0 | public |
| `DC-003` | [LibreNMS 网络监控](https://github.com/librenms/librenms) | github | evidence | NOASSERTION（需复核） | public |
| `DC-004` | [Centreon 监控](https://github.com/centreon/centreon) | github | evidence | Apache-2.0 | public |
| `DC-005` | [Netdata 全栈可观测](https://github.com/netdata/netdata) | github | evidence | GPL-3.0 | public |
| `DC-006` | [Network UPS Tools](https://github.com/networkupstools/nut) | github | evidence | NOASSERTION（需复核） | public |
| `DC-007` | [Telegraf 指标采集](https://github.com/influxdata/telegraf) | github | evidence | MIT | public |
| `DC-008` | [collectd 系统采集](https://github.com/collectd/collectd) | github | evidence | NOASSERTION（需复核） | public |
| `DC-009` | [OpenBMC 基板管理](https://github.com/openbmc/openbmc) | github | evidence | NOASSERTION（需复核） | public |
| `DC-010` | [Ansible 自动化](https://github.com/ansible/ansible) | github | evidence | GPL-3.0 | public |
| `BASE-STD` | [国家标准全文公开系统](https://openstd.samr.gov.cn/bzgk/gb/) | docs | mention | unknown（需复核） | public |
| `BASE-TENDER` | [中国政府采购网](https://www.ccgp.gov.cn/) | docs | mention | unknown（需复核） | public |
| `BASE-CORP` | [巨潮资讯](https://www.cninfo.com.cn/) | docs | mention | unknown（需复核） | public |
| `BASE-STAT` | [国家统计局](https://www.stats.gov.cn/) | docs | mention | unknown（需复核） | public |
| `BASE-REPORT` | [艾瑞咨询](https://www.iresearch.com.cn/) | docs | mention | unknown（需复核） | public |
| `VND-VERTIV` | [Vertiv 数据中心基础设施](https://www.vertiv.com/en-us/) | web | mention | unknown（需复核） | public |
| `VND-SCHNEIDER` | [Schneider Electric](https://www.se.com/ww/en/) | web | mention | unknown（需复核） | public |
| `VND-EATON` | [Eaton 电源管理](https://www.eaton.com/us/en-us.html) | web | mention | unknown（需复核） | public |
| `VND-RARITAN` | [Raritan 机柜 PDU](https://www.raritan.com/products/power-distribution-units) | web | evidence | unknown（需复核） | public |
| `VND-SUNBIRD` | [Sunbird DCIM](https://www.sunbirddcim.com/) | web | evidence | unknown（需复核） | public |
| `VND-NLYTE` | [Nlyte DCIM](https://www.nlyte.com/) | web | mention | unknown（需复核） | public |
| `VND-DEVICE42` | [Device42 资产/CMDB](https://www.device42.com/) | web | mention | unknown（需复核） | public |
| `VND-UPTIME` | [Uptime Institute](https://uptimeinstitute.com/) | web | mention | unknown（需复核） | public |
| `VND-TIA` | [TIA 标准组织](https://www.tiaonline.org/) | web | mention | unknown（需复核） | public |
| `VND-OCP` | [Open Compute Project](https://www.opencompute.org/) | web | mention | unknown（需复核） | public |
| `VND-GREENGRID` | [The Green Grid](https://www.thegreengrid.org/) | web | evidence | unknown（需复核） | public |
| `VND-DCD` | [Data Center Dynamics](https://www.datacenterdynamics.com/) | web | mention | unknown（需复核） | public |
| `VND-DCK` | [Data Center Knowledge](https://www.datacenterknowledge.com/) | web | mention | unknown（需复核） | public |
| `VND-DCF` | [Data Center Frontier](https://www.datacenterfrontier.com/) | web | mention | unknown（需复核） | public |
| `VND-DCMAP` | [Data Center Map](https://www.datacentermap.com/) | web | mention | unknown（需复核） | public |
| `DC-011` | [NetBox 资产/布线路由](https://github.com/netbox-community/netbox) | github | evidence | Apache-2.0 | public |
| `DC-012` | [openDCIM 数据中心库存](https://github.com/opendcim/openDCIM) | github | evidence | unknown（需复核） | public |
| `DC-013` | [RackTables 机柜/端口](https://github.com/RackTables/racktables) | github | mention | GPL-2.0 | public |
| `DC-014` | [ZoneMinder 视频监控](https://github.com/ZoneMinder/zoneminder) | github | evidence | GPL-2.0 | public |
| `DC-015` | [Prometheus Alertmanager](https://github.com/prometheus/alertmanager) | github | evidence | Apache-2.0 | public |
| `VND-GENERAC` | [Generac 发电机组](https://www.generac.com/) | web | mention | unknown（需复核） | public |
| `VND-SIEMENS` | [Siemens 消防](https://www.siemens.com/global/en/products/buildings/fire-safety.html) | web | evidence | unknown（需复核） | public |
| `VND-HID` | [HID 门禁](https://www.hidglobal.com/) | web | mention | unknown（需复核） | public |
| `VND-AXIS` | [Axis 视频](https://www.axis.com/) | web | mention | unknown（需复核） | public |
| `VND-IBM-MAXIMO` | [IBM Maximo 资产/维保](https://www.ibm.com/products/maximo) | web | evidence | unknown（需复核） | public |

## 边界

- 大多数来源只到 metadata/readme/docs，不等于代码已验证；
- 专有来源只进参考池，不进可复用池；
- 覆盖度不是完整性证明，只是“有没有证据”的导航。
