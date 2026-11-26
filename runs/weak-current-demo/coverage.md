# 覆盖度明细

| 层级 | 数量 |
| --- | ---: |
| none | 0 |
| mention | 8 |
| evidence | 20 |
| strong | 9 |

## 管理模块

### M01 项目与往来单位 — strong

| 来源 | 平台 | 等级 | 许可 | 访问 |
| --- | --- | --- | --- | --- |
| `SRC-001` | gitee | strong | proprietary | public |
| `SRC-008` | github | evidence | GPL-3.0 | public |

### M02 立项与项目台账 — strong

| 来源 | 平台 | 等级 | 许可 | 访问 |
| --- | --- | --- | --- | --- |
| `SRC-036` | gitee | strong | MIT | public |
| `SRC-037` | web | strong | GPL-2.0 | public |
| `SRC-038` | docs | evidence | proprietary | public |

### M03 现场勘测与图纸 — evidence

| 来源 | 平台 | 等级 | 许可 | 访问 |
| --- | --- | --- | --- | --- |
| `SRC-006` | github | evidence | unknown | public |
| `SRC-011` | web | mention | proprietary | public |
| `SRC-012` | web | evidence | proprietary | public |

### M04 询价与产品库 — mention

| 来源 | 平台 | 等级 | 许可 | 访问 |
| --- | --- | --- | --- | --- |
| `SRC-005` | github | mention | MIT | public |

### M05 预估成本与容量 — mention

| 来源 | 平台 | 等级 | 许可 | 访问 |
| --- | --- | --- | --- | --- |
| `SRC-005` | github | mention | MIT | public |

### M06 报价与投标 — strong

| 来源 | 平台 | 等级 | 许可 | 访问 |
| --- | --- | --- | --- | --- |
| `SRC-001` | gitee | strong | proprietary | public |
| `SRC-003` | github | evidence | proprietary | public |
| `SRC-004` | github | evidence | proprietary | public |
| `SRC-007` | github | mention | MIT | public |

### M07 合同与变更 — evidence

| 来源 | 平台 | 等级 | 许可 | 访问 |
| --- | --- | --- | --- | --- |
| `SRC-003` | github | evidence | proprietary | public |
| `SRC-007` | github | mention | MIT | public |

### M08 采购与材料设备 — evidence

| 来源 | 平台 | 等级 | 许可 | 访问 |
| --- | --- | --- | --- | --- |
| `SRC-010` | gitee | mention | Apache-2.0 | public |
| `SRC-018` | github | evidence | Apache-2.0 | public |
| `SRC-021` | github | evidence | AGPL-3.0 | public |
| `SRC-024` | github | evidence | unknown | public |
| `SRC-025` | github | evidence | GPL-2.0 | public |

### M09 施工与进度 — mention

| 来源 | 平台 | 等级 | 许可 | 访问 |
| --- | --- | --- | --- | --- |
| `SRC-015` | gitee | mention | MulanPSL-2.0 | public |

### M10 竣工与验收 — evidence

| 来源 | 平台 | 等级 | 许可 | 访问 |
| --- | --- | --- | --- | --- |
| `SRC-012` | web | evidence | proprietary | public |

### M11 实际成本与毛利 — evidence

| 来源 | 平台 | 等级 | 许可 | 访问 |
| --- | --- | --- | --- | --- |
| `SRC-003` | github | evidence | proprietary | public |
| `SRC-005` | github | mention | MIT | public |

### M12 发票与收付款 — mention

| 来源 | 平台 | 等级 | 许可 | 访问 |
| --- | --- | --- | --- | --- |
| `SRC-007` | github | mention | MIT | public |

### M13 售后与运维 — strong

| 来源 | 平台 | 等级 | 许可 | 访问 |
| --- | --- | --- | --- | --- |
| `SRC-001` | gitee | strong | proprietary | public |
| `SRC-021` | github | evidence | AGPL-3.0 | public |
| `SRC-022` | github | evidence | GPL-3.0 | public |
| `SRC-023` | github | evidence | GPL-2.0 | public |
| `SRC-026` | github | evidence | AGPL-3.0 | public |

### M14 权限、审计与备份 — evidence

| 来源 | 平台 | 等级 | 许可 | 访问 |
| --- | --- | --- | --- | --- |
| `SRC-004` | github | evidence | proprietary | public |
| `SRC-010` | gitee | mention | Apache-2.0 | public |
| `SRC-022` | github | evidence | GPL-3.0 | public |

## 子系统

- **S01 综合布线** — evidence（7 个来源）
- **S02 计算机网络/无线WIFI** — evidence（3 个来源）
- **S03 综合管路** — evidence（3 个来源）
- **S04 机房/UPS** — strong（3 个来源）
- **S05 视频监控** — mention（2 个来源）
- **S06 门禁一卡通/出入口** — mention（2 个来源）
- **S07 入侵/防盗报警** — evidence（3 个来源）
- **S08 周界防范** — evidence（2 个来源）
- **S09 电子巡更** — strong（3 个来源）
- **S10 楼宇自控 BA** — evidence（9 个来源）
- **S11 环境监控** — strong（3 个来源）
- **S12 智能照明** — evidence（2 个来源）
- **S13 能源管理** — evidence（7 个来源）
- **S14 信息发布** — strong（3 个来源）
- **S15 程控电话/通讯** — evidence（1 个来源）
- **S16 IPTV** — evidence（1 个来源）
- **S17 有线电视** — evidence（2 个来源）
- **S18 停车场** — evidence（2 个来源）
- **S19 会议/多功能厅** — mention（1 个来源）
- **S20 背景音乐** — mention（1 个来源）
- **S21 五方对讲** — evidence（1 个来源）
- **S22 客控系统** — strong（3 个来源）
- **S23 公区温控联网** — evidence（1 个来源）

## 同源待印证

这些模块有 ≥2 条证据，但来自同一 host；不能当独立互证。

- `M08` 采购与材料设备（独立 host 1）
- `M14` 权限、审计与备份（独立 host 1）
- `S01` 综合布线（独立 host 1）
- `S02` 计算机网络/无线WIFI（独立 host 1）
- `S03` 综合管路（独立 host 1）
- `S10` 楼宇自控 BA（独立 host 1）
- `S12` 智能照明（独立 host 1）
- `S13` 能源管理（独立 host 1）
