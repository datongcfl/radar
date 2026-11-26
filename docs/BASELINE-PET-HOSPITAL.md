# pet-hospital 基线

## 数字

| 项 | 值 |
| --- | ---: |
| 公开来源 | 22 |
| selected / needs_review | 22 / 0 |
| 模块 / 子系统 | 6 / 6 |
| strong / evidence / mention / none | **12 / 0 / 0 / 0** |
| 单源单元 | 0 |
| 无证据单元 | 0 |

对应产物：`runs/pet-hospital-demo/`。  
`state_hashes: OK`；`tools/audit_ledger.py --pack packs/pet-hospital/pack.json --seeds seeds/pet-hospital.json --run runs/pet-hospital-demo --expect-strong 12 --expect-evidence 0` PASS。

## 来源构成与许可隔离

- **宽松开源可借鉴代码（MIT / Apache-2.0，`clear`）**：`PH-003` PetCare、`PH-004` ARKA、`PH-005` MixPet、`PH-006` VetVoice、`PH-007` spring-petclinic-rest、`PH-010` vetmanager-token。
- **Copyleft / 协议待复核（`needs_review`）**：`PH-001`/`PH-002` OpenVPM（AGPL-3.0）、`PH-008` Gitee PetClinic、`PH-009` Jakarta EE PetClinic（EPL-2.0）、`PH-011` vetclinic（GPL-3.0）、`PH-018` DataHub Vet。
- **商业产品与专有参考（`proprietary`，仅参考业务边界）**：`PH-012` Activet、`PH-013` Provet、`PH-014` Digitail、`PH-015` Shepherd、`PH-016` ezyVet、`PH-017` Trupanion、`PH-021` WSAVA 指南。
- **临床规范与医疗影像标准**：`PH-019` AAHA 犬类疫苗指南、`PH-020` AAHA 麻醉监护指南、`PH-022` NEMA DICOM PS3.3 C.7（含动物物种与品种属性）。

> 注：`S02 住院`、`S03 手术`、`S04 影像`、`S05 检验` 虽已达到多源 `strong`，但 `reusable=false`（支撑方多为商业 SaaS 或待复核规范），写 PRD 时只借鉴其流程与数据边界，不直接复用代码。
