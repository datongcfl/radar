# D03 材料采购与现场流转：端到端证据验证

> 状态：M10 第一轮真实源码证据评估。本文是基于公开仓库固定版本进行的人工证据核验，不是 Radar 使用用户 Token 完成的在线 Discover Run，也不是对 ERPNext 进行部署或运行测试。

## 1. 验证目标与输入

- Requirement：`D03`，版本 1；机器可读定义见 `examples/requirements/d03-material-procurement.json`。
- 行业 Pack：`weak-current`，涉及询价与产品库（M04）、采购与材料设备（M08）、实际成本与毛利（M11）。
- 参考实现：`frappe/erpnext`。
- 固定源码 Commit：`a8ea38cb75dd00f51212d4072de24ec580ad6c84`。
- 参考实现许可：GNU GPL-3.0（仓库 `license.txt`）。只能在遵守 GPL-3.0 及项目合规要求的前提下评估复用；本案例只做机制参考，不复制代码。

## 2. 证据索引

下列链接固定到不可变 Commit，行号是该版本中的源码位置。

| Evidence | D03 验收项 | 证据位置 | 可确认的事实 |
|---|---|---|---|
| E01 | C1、C3、C5 | [Material Request → Purchase Order mapper，L87-L162](https://github.com/frappe/erpnext/blob/a8ea38cb75dd00f51212d4072de24ec580ad6c84/erpnext/stock/doctype/material_request/mapper.py#L87-L162) | 已提交的 Purchase 类型 Material Request 可映射成 Purchase Order；明细保留 material_request 与 material_request_item 引用；已映射数量参与剩余数量计算 |
| E02 | D03-C2 | [Material Request → Supplier Quotation mapper，L335-L368](https://github.com/frappe/erpnext/blob/a8ea38cb75dd00f51212d4072de24ec580ad6c84/erpnext/stock/doctype/material_request/mapper.py#L335-L368) | Material Request 可映射为 Supplier Quotation，并保留来源明细引用；这证明报价采集入口存在，不足以证明完整的多供应商比价、评分和审批闭环 |
| E03 | D03-C4 | [Purchase Order validation，L201-L285](https://github.com/frappe/erpnext/blob/a8ea38cb75dd00f51212d4072de24ec580ad6c84/erpnext/buying/doctype/purchase_order/purchase_order.py#L201-L285)；[submit 与审批权限，L458-L480](https://github.com/frappe/erpnext/blob/a8ea38cb75dd00f51212d4072de24ec580ad6c84/erpnext/buying/doctype/purchase_order/purchase_order.py#L458-L480) | 订单校验供应商、来源单据、单位与数量等；提交时调用 Authorization Control 校验审批权限 |
| E04 | C5、C6、C10 | [Purchase Receipt validation and submit，L270-L405](https://github.com/frappe/erpnext/blob/a8ea38cb75dd00f51212d4072de24ec580ad6c84/erpnext/stock/doctype/purchase_receipt/purchase_receipt.py#L270-L405) | 收货校验采购订单、订单明细、供应商、公司和物料；可按设置要求必须关联 PO；执行质量检验引用校验；提交时更新前序单据状态、库存流水和总账 |
| E05 | D03-C8 | [Material Request → Stock Entry mapper，L375-L455](https://github.com/frappe/erpnext/blob/a8ea38cb75dd00f51212d4072de24ec580ad6c84/erpnext/stock/doctype/material_request/mapper.py#L375-L455) | Material Transfer/Material Issue 映射为 Stock Entry，按来源与目标仓库设置 s_warehouse/t_warehouse，并换算 transfer_qty |
| E06 | C7、C8 | [Material Request quantity controls，L500-L523](https://github.com/frappe/erpnext/blob/a8ea38cb75dd00f51212d4072de24ec580ad6c84/erpnext/stock/doctype/material_request/material_request.py#L500-L523) | 发料/调拨数量可按申请数量及允许超量比例进行约束；超出时拒绝 |
| E07 | D03-C9 | [Return source validation，L45-L120](https://github.com/frappe/erpnext/blob/a8ea38cb75dd00f51212d4072de24ec580ad6c84/erpnext/controllers/sales_and_purchase_return.py#L45-L120) | 退货关联原单，校验原单存在、供应商/客户、公司、日期及原始物料明细；采购收货退货路径纳入 rejected_qty/received_qty 字段 |
| E08 | D03-C10 | [Purchase Receipt rejected-warehouse return regression test，L8309-L8360](https://github.com/frappe/erpnext/blob/a8ea38cb75dd00f51212d4072de24ec580ad6c84/erpnext/stock/doctype/purchase_receipt/test_purchase_receipt.py#L8309-L8360) | 有专门测试覆盖浮点精度 2、UOM 换算系数 0.3356、合格/拒收数量、拒收仓退货，以及应付未开票库存科目金额 199.64 的回冲 |
| E09 | D03-C10 | [Purchase Receipt valuation/ledger regression tests，L10213-L10340](https://github.com/frappe/erpnext/blob/a8ea38cb75dd00f51212d4072de24ec580ad6c84/erpnext/stock/doctype/purchase_receipt/test_purchase_receipt.py#L10213-L10340) | 测试覆盖移动平均法退货、内部收货退货、库存价值和汇兑差额冲回 |
| E10 | C10 | [Issue #68057](https://github.com/frappe/erpnext/issues/68057) → [merged PR #68721](https://github.com/frappe/erpnext/pull/68721) | 真实缺陷：拒收仓退货因 UOM 精度舍入导致 Stock Received But Not Billed 残留 0.36；PR 修正冲回金额计算，并于 2026-11-21 合并 |

## 3. 端到端业务链重建

```text
项目/现场材料需求
  → Material Request（申请物料、数量、单位、需求日期）
  → Supplier Quotation（供应商报价入口）
  → Purchase Order（供应商、价格、数量、审批）
  → Purchase Receipt（分批到货、质检、合格/拒收）
  → Stock Ledger + GL（库存数量与价值）
  → Stock Entry（领料 / 发料 / 仓间调拨）
  → Purchase Return（关联原收货，合格品/拒收品退货）
  → 库存价值及会计回冲
```

这是从多个源码模块重建的业务链，不代表 ERPNext 的每个部署实例都启用了相同审批配置，也不代表弱电工程项目所需的现场签收、责任人、甲供/乙供材和成本分摊已经全部覆盖。

## 4. 验收矩阵（证据强度，而非产品打分）

| 验收项 | 当前判断 | 依据与缺口 |
|---|---|---|
| D03-C1 需求申请 | 部分支持 | E01/E06 支持需求单和数量控制；申请人、现场签收及审批链配置需进一步核验 |
| D03-C2 询价比价 | 部分支持 | E02 证明报价单创建入口；跨供应商比价规则、价格评分、审批历史尚无充分证据 |
| D03-C3 订单追溯 | 支持 | E01/E03 证明来源需求及明细映射、数量计算与前序单据校验 |
| D03-C4 订单审批 | 部分支持 | E03 证明提交时审批权限校验；完整审批流、代理/会签/超额授权需按部署配置验证 |
| D03-C5 分批收货 | 部分支持 | E04 证明 PO/明细关联、前序状态更新和收货入账；需要额外验证多次收货、短交/超交边界的业务规则 |
| D03-C6 质检与拒收 | 部分支持 | E04/E08 证明质量检验引用和拒收仓路径；质检标准、复检、供应商索赔流程未完整核验 |
| D03-C7 单位与数量 | 部分支持 | E05/E06/E08 证明单位换算与数量控制的部分机制；序列号/批次端到端流程需独立验证 |
| D03-C8 领料与调拨 | 部分支持 | E05/E06 证明 Stock Entry 与仓库方向、数量控制；现场签收人、调拨在途和签收确认需继续核验 |
| D03-C9 退货 | 部分支持 | E07/E08/E10 证明原单关联及拒收仓退货校验；退料与供应商退货的权限、审批和全量异常矩阵仍需补齐 |
| C10 库存/财务一致性 | 部分支持 | E04/E08/E09/E10 有库存、GL 和舍入回归证据；不能据此推断所有估价方法、币种和税费组合均已覆盖 |
| D03-C11 项目成本归集 | 无充分证据 | 当前采集的 D03 证据不足以证明采购承诺、实际领料、退料和项目成本科目完整勾稽；应联合 D02 继续发现和验证 |

**本轮结论：** 当前可重建采购主干，且能找到具体代码和回归测试支撑部分关键规则；但不能将 D03 判为全部满足。没有证据的项保持 `no_evidence` 或 `not_assessed`，不得推断为未实现。

## 5. 反例与重要边界

- 采购申请存在，不代表已完成询价比价或审批。
- 采购订单存在，不代表全部到货；需区分 ordered、received、rejected、returned 和 outstanding quantity。
- 收货单存在，不代表所有物料均合格入库；合格数量和拒收数量应分开追溯。
- 退货必须回到原收货明细，不能只按物料编码做负数库存调整。
- 0.3356 这样的单位换算系数会使舍入误差进入库存价值和会计科目；测试证据必须包含金额断言，不能只检查数量。
- CI/回归测试代码存在，只能证明仓库中定义了测试；若未取得该 Commit 对应的实际 CI Run 结果，不能宣称测试在本次评估中执行通过。

## 6. 对 Radar 的验证结果与下一步

本案例证明 Radar 的领域模型至少需要把以下内容分开：

1. Requirement / Acceptance Criterion：每个验收点独立评价；
2. Asset：Material Request、Supplier Quotation、Purchase Order、Purchase Receipt、Stock Entry、Purchase Return、Issue、PR、测试文件；
3. Evidence：精确到 Commit、路径、行号、测试方法和 Issue/PR；
4. Relationship：`derived_from`、`contains`、`tests`、`fixes`、`supports`；
5. Assessment：明确 `supported`、`partially_supported`、`no_evidence`、`not_assessed`。

**仍未完成的真实运行验证：** 尚未用用户真实 `GITHUB_TOKEN` 执行 Radar CLI 对本案例进行完整在线发现；本文件是固定版本源码的证据基线，不能冒充一次真实 Radar Run。下一步应在授权 Token 的环境中执行 `radar discover --github`，比较自动发现结果与本证据基线，统计漏检、误检和定位误差。


## 7. Radar 自动发现流水线验证（离线）

已将 D03 需求文件实际送入 Radar 的 `run_discovery()`，并通过 `python -m radar discover` CLI 再执行一次。该验证使用仓库现有 Seeds 和 weak-current Pack，未启用 GitHub 在线适配器。

可复现的离线 CLI 命令：

```bash
python -m radar discover \
  --workspace ws_d03_material_procurement \
  --workspace-root .radar-d03-workspace \
  --requirements examples/requirements/d03-material-procurement.json \
  --pack packs/weak-current/pack.json \
  --seeds seeds/weak-current.json
```

该命令刻意不传入 `--github`，因此不会调用 GitHub API，也不需要 `GITHUB_TOKEN`。

- 需求版本：D03 v1，11 个验收条件。
- 流程结果：`partial`，原因是既有 Seeds 中仍有缺少精确定位的旧 Quote。
- 需求候选资产：大于 0（来自 Pack 单元映射的既有资产）。
- D03 可定位 Evidence：0。
- D03 评价：`no_evidence`。这说明 Seeds 的模块覆盖声明不能替代 D03 采购流程的具体证据。
- CLI 和领域层均执行成功；该结果不代表在线 GitHub 发现成功。

### 本轮修正的检索覆盖缺陷

最初的 GitHub 适配器只取需求词表前 4 项，导致 D03 的收货、调拨、退货等术语不会进入搜索。现已将词表扩展到最多 16 项，并按每批 4 项分别执行 code / issue / PR 搜索；新增测试确认 16 项术语全部进入对应批次，且跨批次重复资产会去重。此改动解决了 D03 当前词表内的漏搜，但超过 16 项的词表仍受上限约束。

当前离线验证证明的是 CLI、需求装载、Pack 校验、Seeds 转换、候选映射和持久化路径可以执行；真实 GitHub API 在线发现仍需在配置 `GITHUB_TOKEN` 的环境中验证。
