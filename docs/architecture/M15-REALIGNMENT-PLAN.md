# M15 分支治理与架构边界重整

> 状态：审计基线已建立；尚未迁移代码、删除分支或合并 PR。
> 审计时间：2026-11-22
> 仓库：datongcfl/radar

## 1. 冻结的审计基线

| 项目 | 审计结果 |
|---|---|
| main HEAD | `b14c8916e3545ea5e9302bc9f69ed7f3b3bd7558` |
| feature HEAD | `07c6ec7b97569e8a329d9f932f7e65113193a677` |
| feature 相对 main | 197 ahead / 0 behind |
| compare API 返回提交数 | 197 |
| compare 文件差异 | 70 个文件 |
| 文件变更量 | +14,608 / -288 行 |
| feature HEAD 仓库树 | 179 项，未截断 |
| 当前开放 PR | 0 |
| main 保护 | 已启用；本计划不直接写 main |

旧分支 `fix/agents-authorized-fix-branch` 相对 main 为 0 ahead / 3 behind，没有独有提交。它是候选清理对象；删除前仍须重新核实 refs、PR 和工作流引用。

本文件建立时，feature 分支 HEAD 已重新读取并确认。M15 分支 `chore/m15-architecture-realignment` 从该 SHA 创建，保留完整快照，不改写历史。

## 2. 197 个提交的主题盘点

提交主题按提交消息前缀和实际文件差异归类。类别是治理分组，不代表可独立 cherry-pick；提交间存在连续依赖，不能仅按消息前缀拆分。

| 主题 | 主要成果 | 处理方向 |
|---|---|---|
| Discovery 数据模型与存储 | 版本化领域对象、Schema、Workspace JSONL、快照、Legacy 迁移 | Discovery Core |
| Requirement-driven Discover | 离线发现编排、CLI、Assessment、需求映射 | Discovery Core |
| GitHub 发现 | Code/Issue/PR、文件树、文档、讨论、Review、CI 证据 | Source Adapter |
| 文档解析 | CSV、DOCX、XLSX、PPTX 解析和定位 | Document Capability |
| 代码分析 | Python AST、模块关系和状态转换候选 | Code Capability |
| Business Graph | Evidence/Asset/Requirement 关系、聚合和投影 | 通用图模型与领域投影分离 |
| 业务不变量与 Observation | 表格观察值、跨 Asset 聚合、业务规则 | Industry Capability / Pack |
| Ledger / Voucher | Ledger Effect、凭证完整性、冲销、期间、对账、控制流水线 | 独立 Industry Ledger Capability |
| M14 依赖治理 | 选型政策、组件盘点、基准、pyproject、uv.lock、CI | 通用工程治理 |
| 示例与案例 | D03 需求、Pack 业务模型和案例 | 示例/行业包，不进入 Core 默认行为 |

### 关键文件分组（相对 main 的差异）

**工程治理**
- `AGENTS.md`
- `pyproject.toml`
- `uv.lock`
- `.github/workflows/tests.yml`
- `.github/workflows/package-smoke.yml`
- `.github/workflows/component-benchmarks.yml`
- `docs/OPEN_SOURCE_COMPONENT_SELECTION.md`
- `docs/architecture/dependency-management.md`
- `docs/M14-COMPONENT-INVENTORY.md`
- `tools/benchmarks/*`

**Discovery Core 候选**
- `radar/discovery.py`
- `radar/discovery_store.py`
- `radar/discover.py`
- `radar/legacy.py`
- `schemas/discovery.schema.json`
- `examples/requirements/weak-current.json`
- `tests/test_discovery.py`
- `tests/test_discovery_store.py`
- `tests/test_discover.py`
- `tests/test_legacy.py`

**来源与技术能力适配器候选**
- `radar/github_discovery.py`
- `radar/document_parser.py`
- `radar/code_analyzer.py`
- `docs/architecture/document-adapter-contract.md`
- 对应 GitHub、文档、代码测试

**通用关系/观察能力与领域耦合待拆**
- `radar/business_graph.py`
- `radar/business_observation_extractor.py`
- `radar/observation_aggregator.py`
- `radar/business_table_evidence.py`
- `radar/business_invariants.py`
- `docs/BUSINESS-GRAPH.md`
- `tests/test_business_*.py`

**Ledger 行业能力候选**
- `radar/ledger_*.py`
- `radar/ledger_workspace.py`
- `docs/architecture/ledger-*.md`
- `docs/architecture/transaction-ledger-semantics.md`
- `tests/test_ledger_*.py`
- `tests/test_return_quantity_cap.py`
- `packs/weak-current/business-model.json` 中的 Ledger 专属声明

以上只是第一轮文件级边界。尤其 `business_graph.py`、`business_invariants.py`、`cli.py`、Pack Schema 和业务模型包含跨层耦合，不能简单移动文件就认为拆分完成。

## 3. 目标架构边界

### L0 — Radar Discovery Core
只负责通用知识发现和证据治理：
- Workspace、Requirement、Source、Asset、Evidence、Relationship、Assessment、DiscoveryRun；
- 来源版本、Evidence 定位、身份、溯源与不可变语义；
- 通用需求映射、覆盖缺口、Assessment 状态边界；
- 通用持久化接口和 CLI 编排；
- 通用图关系/投影接口，不内置会计科目或凭证语义。

### L1 — Source / Capability Adapters
- GitHub、Gitee、网页、文档、代码、CSV/XLSX 等来源/格式适配；
- Adapter 统一输出 Radar 领域对象；
- 可选解析器不能成为 Core import 的硬依赖；
- 部分解析、失败、unsupported 和 unresolved 必须显式表达。

### L2 — Industry Packs / Domain Capabilities
- 行业 Pack 声明业务对象、别名、字段映射、验收条件和规则；
- Ledger、Voucher、Inventory/GL reconciliation 作为可选领域能力；
- 通用 Observation/Invariant 执行接口与行业规则定义分离；
- Business Graph 的通用关系层与领域投影分离。

### L3 — Experimental / Benchmarks
- PDF、Tree-sitter 等候选比较；
- 合成样本和固定真实样本基准；
- 不影响 Core 安装、基础 CLI 和核心 CI。

## 4. 拆分与合入顺序

### M15-A：审计和保护（本阶段）
- 冻结 main/feature SHA、比较统计、文件清单、提交主题；
- 建立治理分支和本文件；
- 核查开放 PR、残留分支、工作流引用；
- 不删除任何分支，不改写历史。

### M15-B：依赖治理 PR
范围：`AGENTS.md`、依赖策略/管理文档、`pyproject.toml`、`uv.lock`、package smoke CI。
验收：
- Python 3.9+ 声明与当前支持矩阵一致；
- Core 无未批准运行依赖；
- lockfile 可复现；
- wheel/sdist 安装和 CLI smoke 通过；
- 不包含 Ledger 领域实现。

### M15-C：Discovery Core PR
范围：通用领域对象、Schema、Workspace/Discovery 编排、Assessment 和兼容层。
验收：
- 旧 `run / scan / validate` 保持兼容；
- Discovery 核心不 import Ledger 模块；
- Python 3.9 与当前 Python 测试通过；
- Evidence/Assessment 边界测试通过；
- 文档明确当前发现范围与未支持能力。

### M15-D：Source / Capability Adapter PR
范围：GitHub、文档、代码解析适配器和统一契约。
验收：
- Adapter 输出统一领域对象；
- optional dependency 缺失不会破坏 Core import；
- 来源定位和版本信息保留；
- API 限流、权限失败、部分结果和 unsupported 状态可区分；
- 对应 CI 独立运行。

### M15-E：Industry / Ledger Capability 隔离
范围：Ledger、Voucher、Inventory/GL、行业不变量与业务投影。
验收：
- 领域能力可独立启用/测试；
- Core 不包含会计专属字段、枚举和规则；
- 仍可通过通用 Evidence、Relationship、Observation 和 Assessment 接口回接；
- D03 案例保持可运行；
- 未取得真实 ERP 数据前，不宣称生产适配完成。

### M15-F：Benchmark 与文档收口
范围：组件 benchmark、README、路线图、架构图和迁移说明。
验收：
- benchmark 不进入 Core 依赖；
- README 与真实能力、测试数和支持范围一致；
- 所有阶段都有 CI 记录；
- PR 分批提交，合并权归仓库所有者。

## 5. 当前发现的文档/治理问题

1. README 将产品描述为“目录覆盖度工具”，但新数据模型已扩展为需求驱动的知识发现与证据评估系统；需要统一定位。
2. README 和 dependency-management 文档中的测试数量仍写 254，而后续 Adapter 加固记录为 259；应以最新 CI 日志重新核实后统一更新。
3. README 将 Ledger Source Adapter 作为较突出功能入口，需明确它属于可选行业能力，而非 Core 默认职责。
4. `AGENTS.md` 已允许依赖政策变化，但仍要求所有依赖先完成准入并获得仓库所有者批准；该治理约束应保留。
5. 当前没有开放 PR，因此可先建立分批 PR 方案；不得将大分支一次性合入 main。

## 6. 风险与禁止事项

- 不对 197 个提交执行 squash/rebase/force-push。
- 不直接修改 main，不自动合并 PR。
- 不因模块迁移而删除测试、历史案例或问题记录。
- 不把 Ledger 领域实现仅改名为 experimental 后继续从 Core 导入。
- 不将 PDF/Tree-sitter benchmark 的开发依赖加入 Core。
- 不在没有真实 ERP 导出样本时宣称 ERP Adapter 生产就绪。
- 每个 PR 写前重新 fetch 对应分支 head；commit parent 必须为最新 head；更新 ref 使用 expected_sha CAS。
- PR 按完整可运行功能单元拆分；跨层接口未稳定前不做机械文件搬迁。

## 7. 当前决策

- 保留原 feature 分支作为只读审计来源，直至各功能单元完成迁移。
- 使用 `chore/m15-architecture-realignment` 承载 M15 治理文档和后续拆分工作。
- 旧 fix 分支列为待清理，不在本次审计中自动删除。
- 首个实现 PR 应是依赖治理/包管理工程基础；之后再拆 Discovery Core 和领域能力。


## 8. Import coupling evidence (M15-C preflight)

A first import-graph inspection of the feature snapshot found concrete cross-layer coupling:

- `radar/discover.py` imports `github_discovery`, `business_graph`, `business_invariants`, `business_observation_extractor`, and `ledger_workspace` at module load time.
- `radar/business_graph.py` imports `ledger_aggregator` and `ledger_source_adapter` directly, so the graph projection layer is not yet domain-neutral.
- `radar/cli.py` eagerly imports Discovery, document, business, and Ledger modules in one command module.
- The basic `radar/discovery.py` domain contract itself uses only the Python standard library and has no import dependency on Ledger or external packages.

Implications:
1. The first safe Core boundary is the pure domain contract and storage layer, not the current top-level `discover.py` orchestration module.
2. Introduce capability registration/dispatch at orchestration boundaries before moving Ledger files. Core should call declared capability interfaces and receive normalized observations/results; it must not import concrete Ledger implementations.
3. Split Business Graph into a generic graph/provenance projection and separately registered domain projections. Moving the whole current module into Core would preserve the existing Ledger coupling.
4. CLI commands should lazy-load their implementation handlers so importing or running basic Core commands does not import optional domain capabilities.
5. M15-C must include import-boundary tests (e.g. Core domain/store imports succeed with Ledger capability modules unavailable) in addition to behavior tests.

This is a code-derived architectural finding, not a claim that the refactor has already been implemented.
