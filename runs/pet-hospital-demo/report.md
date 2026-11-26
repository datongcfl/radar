# 宠物医院管理系统 · 雷达运行报告

Run: `20261126-095326` · Pack: `pet-hospital` v0.1.0 · Radar: v1.7.0

## 一句话

本次用 22 条来源，覆盖 6 个管理模块 + 6 个子系统；强/证据/提及/空 = 12/0/0/0。

## 平台覆盖

| 平台 | 来源数 |
| --- | ---: |
| docs | 5 |
| gitee | 1 |
| github | 6 |
| web | 10 |

## 低星但高覆盖的发现

- `PH-003` [PetCare (Laravel + Vue 宠物诊所患者管理系统)](https://github.com/geosem42/PetCare) — 26★，覆盖 3 格，MIT 许可，自带物种/品种 Seeder 与 PHPUnit 测试，适合直接借鉴预约日历、病史/治疗计划与药品耗材库存模型。
- `PH-006` [VetVoice 兽医声动（宠物医院 AI 语音电子病历助手）](https://github.com/georgewangchn/VetVoice) — 15★，覆盖 3 格，Apache-2.0 许可的中文宠物医院诊室插件，明确拆解门诊接诊四阶段（问诊→开检查→看结果→确诊推荐用药）。

## 访问/许可需要注意

- `PH-001` access=public, license_status=needs_review：AGPL-3.0 强传染性开源许可（网络服务部署需公开修改源码）；主面向北美小动物门诊，尚未原生支持中文医保/国内处方格式。
- `PH-002` access=public, license_status=needs_review：官网明确标注急诊/专科/多院区尚处于 fit review 阶段而非生产就绪；AGPL-3.0 需注意网络服务分发边界。
- `PH-008` access=public, license_status=needs_review：Gitee 仓库未显式声明许可证文件且为纯前端镜像，需配合 REST 后端运行；Angular 版本较旧。
- `PH-009` access=public, license_status=needs_review：演示性 Rosetta Stone 项目，EPL-2.0 弱传染许可需合规评审；未覆盖处方、收费与辅助检查。
- `PH-011` access=public, license_status=needs_review：GPL-3.0 许可且项目停更较久（2017 年 Beta 状态），部分高级处方与账单功能标注在 Pro 版本中。
- `PH-012` access=public, license_status=proprietary：专有商业 SaaS（All rights reserved），仅可参考产品分层、多租户 RLS 审计理念与子系统划分，禁止抄袭源码。
- `PH-013` access=public, license_status=proprietary：商业 SaaS 产品特性文档，专有许可；部分集成能力（如特定检验设备/保险直连）依赖欧美合作生态。
- `PH-014` access=public, license_status=proprietary：商业 SaaS 平台，专有许可；页面描述以高层次工作流为主，不公开底层数据库表结构。
- `PH-015` access=public, license_status=proprietary：商业专有 PIMS；面向美国兽医临床合规（如 Buoy's Law / Lizzie's Law 出院医嘱规范）。
- `PH-016` access=public, license_status=proprietary：商业专有 PIMS（IDEXX 旗下），部分深度诊断与影像工作流与 IDEXX Web PACS / VetConnect PLUS 生态绑定。
- `PH-017` access=public, license_status=proprietary：商业专有保险直付平台（All Rights Reserved），国内宠物医疗保险直付机制与保单条款存在本地差异。
- `PH-018` access=public, license_status=needs_review：商业集成中间件官网，未公开 OpenAPI 细粒度 Schema 与开源许可信息。
- `PH-019` access=public, license_status=needs_review：临床权威规范指南（非软件实现），具体免疫程序与狂犬病法规需按所在国家/地区调整。
- `PH-020` access=public, license_status=needs_review：临床安全指南（非软件源码），部分详细监护记录表格下载需 AAHA 会员权限。
- `PH-021` access=public, license_status=proprietary：WSAVA 版权保留（All Rights Reserved）临床指南，需配合犬猫疫苗表与亚洲地区推荐补充实施。
- `PH-022` access=public, license_status=needs_review：NEMA DICOM 国际医疗影像标准（非专有软件），聚焦影像患者元数据字段定义而非医院端 PACS 部署脚本。

## 单源模块

- 无

## 来源清单

| ID | 标题 | 平台 | 等级 | 许可 | 访问 |
| --- | --- | --- | --- | --- | --- |
| `PH-001` | [OpenVPM 开源兽医诊所管理系统](https://github.com/evangauer/openvpm) | github | strong | AGPL-3.0（需复核） | public |
| `PH-002` | [OpenVPM 官网与托管产品规范](https://openvpm.com/) | web | strong | AGPL-3.0（需复核） | public |
| `PH-003` | [PetCare (Laravel + Vue 宠物诊所患者管理系统)](https://github.com/geosem42/PetCare) | github | strong | MIT | public |
| `PH-004` | [ARKA Veterinary Clinic 宠物诊所预约与门户系统](https://github.com/pjborowiecki/ARKA-Veterinary-Clinic-Page-and-Appointment-Booking-System) | github | strong | MIT | public |
| `PH-005` | [MixPet 宠物医院管理系统（网页端+医生端+微信小程序）](https://github.com/MixJade/MixPet) | github | strong | MIT | public |
| `PH-006` | [VetVoice 兽医声动（宠物医院 AI 语音电子病历助手）](https://github.com/georgewangchn/VetVoice) | github | strong | Apache-2.0 | public |
| `PH-007` | [Spring PetClinic REST API](https://github.com/spring-petclinic/spring-petclinic-rest) | github | strong | Apache-2.0 | public |
| `PH-008` | [Spring PetClinic Angular 前端（Gitee 镜像）](https://gitee.com/xfan1024/spring-petclinic-angular) | gitee | strong | unknown（需复核） | public |
| `PH-009` | [Jakarta EE 10 PetClinic 需求与状态机文档](https://jakarta-ee-petclinic.github.io/petclinic-jakartaee/) | docs | strong | EPL-2.0（需复核） | public |
| `PH-010` | [Vetmanager REST API 认证与计费发现 PHP 包（Packagist）](https://packagist.org/packages/otis22/vetmanager-token) | web | strong | MIT | public |
| `PH-011` | [vetclinic 开源兽医诊所 Web 系统（SourceForge）](https://sourceforge.net/projects/vetclinic/) | web | strong | GPL-3.0（需复核） | public |
| `PH-012` | [Activet 云端宠物医院管理平台](https://acti.vet/) | web | strong | proprietary（不可复用） | public |
| `PH-013` | [Provet Cloud 兽医医院全流程平台特性](https://www.provet.com/features) | web | strong | proprietary（不可复用） | public |
| `PH-014` | [Digitail AI 原生宠物医院管理系统](https://digitail.com/) | web | strong | proprietary（不可复用） | public |
| `PH-015` | [Shepherd Veterinary Software 临床与计费联动特性](https://www.shepherd.vet/features) | web | strong | proprietary（不可复用） | public |
| `PH-016` | [ezyVet (IDEXX) 兽医医院平台特性](https://www.ezyvet.com/features) | web | strong | proprietary（不可复用） | public |
| `PH-017` | [Trupanion 宠物保险兽医端直付理赔门户](https://vet.trupanion.com/) | web | strong | proprietary（不可复用） | public |
| `PH-018` | [DataHub Vet 兽医 PIMS 统一集成 API](https://www.datahubvet.com/) | web | strong | unknown（需复核） | public |
| `PH-019` | [2022 AAHA 犬类疫苗接种指南（2024 更新）](https://www.aaha.org/resources/2022-aaha-canine-vaccination-guidelines/) | docs | evidence | unknown（需复核） | public |
| `PH-020` | [2020 AAHA 犬猫麻醉与监护指南](https://www.aaha.org/resources/2020-aaha-anesthesia-and-monitoring-guidelines-for-dogs-and-cats/) | docs | evidence | unknown（需复核） | public |
| `PH-021` | [WSAVA 世界小动物兽医协会全球疫苗接种指南](https://wsava.org/global-guidelines/vaccination-guidelines/) | docs | evidence | proprietary（不可复用） | public |
| `PH-022` | [DICOM PS3.3 C.7 通用患者模块规范（含动物物种与品种属性）](https://dicom.nema.org/medical/dicom/current/output/chtml/part03/sect_C.7.html) | docs | evidence | unknown（需复核） | public |

## 边界

- 大多数来源只到 metadata/readme/docs，不等于代码已验证；
- 专有来源只进参考池，不进可复用池；
- 覆盖度不是完整性证明，只是“有没有证据”的导航。
