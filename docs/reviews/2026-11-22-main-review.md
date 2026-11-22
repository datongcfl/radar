# Radar 仓库复核（main @ `40c0528`，2026-11-22）

> 性质：外部评审记录。**未修改 `radar/`、`packs/`、`seeds/`、`schemas/` 或既有文档**。
> 依据 `AGENTS.md`：每条问题都写清“改哪个文件”和“怎么算做完”；实现与合并仍由仓库所有者决定。
> 复核者环境：Python 3.11.2，Linux；`uv` 不可用；可选 PDF/DOCX/XLSX/PPTX 依赖未安装。

## 0. 结论摘要

这个仓库的核心纪律是清楚的：pack/seeds 契约、来源账本、覆盖度、缺口、claim 置信度、
claim 与覆盖层都坚持“单条来源不能单独变成单元级 strong”。191 个测试全绿（20 个因可选
依赖缺失跳过），四个 pack 的 `validate`、离线 `run`、`audit_ledger.py` 都能跑通；解析器
的 ZIP/XML 预检和“解析结果不自动升级为 Evidence”的边界做得比多数同类工具严谨。

但**“账本可信度”仍有两个能直接造出/抹掉证据的缺口**：

1. `--web` 会把页面里自动抽出的句子写进 `quotes` 并标 `quote_verified=true`，再审自己，
   两个不同 host 的无 quote `real_artifact` 来源就能被抬成单元级 `strong`；这与
   `docs/WEB.md` 的明文承诺相反。
2. `--web`/`--verify-quotes` 只在前 20,000 字符里做子串校验，20k 之后的真实 quote 会被
   判成 `false`（不是 `unknown`），从而把真证据降成 `mention`。

另外，适配器跨查询的 ID 冲突（issue #11 的 P0-4）实际没有修好：多查询 `--github/--gitee`
会在花掉 API 配额后以 `来源 ID 重复` 直接失败。基线审计也存在“跑错目录仍然 PASS”的盲区，
且 `run_demo.sh` 会在不重新验证的情况下覆盖 `runs/weak-current-demo` 的 3 strong 基线。

## 1. 本次实际跑了什么

| 项 | 结果 |
| --- | --- |
| `python3 -m unittest discover -s tests` | 191 tests，OK，20 skipped |
| 四个 pack 的 `validate`（含 `--strict`） | 全部通过 |
| 四个 pack 的离线 `run` | 与提交的 demo 数值一致（weak-current 除外，见 P0-3） |
| committed demo 的 `claims` | 2 条 claim 正常输出，均为 low（proprietary 封顶生效） |
| `tools/audit_ledger.py`（默认参数） | PASS |
| 复现用例 | 见下文各条；全部离线或 localhost |

需要说明：weak-current 的提交产物是 `--verify-quotes --require-web-verify` 的 **联网快照**，
离线重跑得到 `0 strong / 23 evidence / 8 mention / 6 none`；提交产物是
`3 / 20 / 8 / 6`。两者都“正确”，但 README 快速开始没有说明这个前提（见 P0-3）。

---

## 2. P0：会直接产出错误结论或让账本失真

### P0-1 `--web` 自产自证，可把单元级覆盖抬成 `strong`

**现象**

`radar/web.py:162-164`（`apply_web`）会把页面自动抽出的句子并入 `quotes`；如果来源原本没有
quote，就直接写 `quote_verified="true"`、`quote_verified_by="web"`。`radar/model.py:251`
再把这个来源判成来源级 `strong`；`radar/coverage.py:31-36` 只要求“2 条已验证、2 个独立
host”，于是两个都没有人工 quote 的 `real_artifact` 来源，就能在没有人类挑选任何引文的情况下
产出单元级 `strong`。

**复现（离线，无需网络）**

```python
from radar.web import apply_web
from radar.coverage import compute_coverage

pack = {"pack": "p", "title": "T",
        "modules": [{"id": "M01", "name": "Alpha", "artifacts": ["docs"], "keywords": ["alpha"]}],
        "subsystems": [{"id": "S01", "name": "Beta", "artifacts": ["docs"], "keywords": ["beta"]}]}
page = {"title": "Doc", "description": "",
        "text": "Alpha is fully described in this documentation page with implementation details.",
        "quotes": ["Alpha is fully described in this documentation page with implementation details."]}

srcs = []
for i, host in enumerate(("a.example.com", "b.example.com"), 1):
    src = {"id": "SRC-%d" % i, "url": "https://%s/doc" % host, "platform": "web",
           "evidence_level": "real_artifact", "covers": ["M01"], "quotes": [],
           "status": "selected", "artifact_type": "article", "access_status": "public",
           "license": "unknown", "license_status": "needs_review",
           "quote_verified": "unknown", "quote_verified_by": None}
    srcs.append(apply_web(src, page))

print([(s["id"], s["quote_verified"], s["quotes"]) for s in srcs])
print(compute_coverage(pack, srcs)["modules"][0]["level"])   # -> strong
```

实测输出：两条来源都得到同一句自动 quote、都是 `true/web`，M01 为 `strong`。

**影响**

- 违反 `docs/WEB.md:24`：“不因为抓到正文就自动把来源升级成 `strong`”。
- `docs/QUOTES.md:16-17` 又确实写了“新加入的页面 quote 来自正文，标 `true`”，两处文档互相矛盾。
- 这是自证循环：工具自己挑句子，再拿同一页校验自己；“verified quote”不再代表“有人认定这句话支持这个模块”。

**涉及文件**

- `radar/web.py`（`apply_web`、`_Extractor`）
- `radar/model.py`（`level_for_source`）
- `radar/coverage.py`（`_row`）
- `docs/WEB.md`、`docs/QUOTES.md`

**验收标准（建议按 A 修）**

A. 自动抽取的 quote 必须带来源标记（如 `quote_source="web_extract"`），并且
   `quote_verified_by="web"` 的 `true` 不能单独满足 strong 门禁；只有人工/独立 quote 才能
   计入 `verified`。加回归测试：两条无 quote 的 `real_artifact` 来源 + `--web`，单元最高
   `evidence`。
B. 若坚持保留现语义，则把 `docs/WEB.md:24` 改成实际行为，并在 `report.md` 明示
   “本单元 strong 由工具自动抽取的 quote 支撑”，同时补回归测试固化该行为。

---

### P0-2 GitHub/Gitee 跨查询来源 ID 冲突（issue #11 P0-4 未真正修复）

**现象**

`radar/adapters.py:69` 与 `:116` 用 `id_offset + i + 1` 生成 ID，其中 `i` 是**响应条目下标**；
而 `collect_github` / `collect_gitee` 在 `:99` / `:163` 只按**已输出条数**推进 `offset`。
一旦某次查询里前面有被 `infer_covers` 过滤掉的条目，下一次查询就会生成重复 ID。

**复现（mock 两次查询）**

```python
import radar.adapters as A

pack = __import__("json").load(open("packs/weak-current/pack.json"))
def item(name, desc):
    return {"full_name": name, "description": desc, "topics": [],
            "html_url": "https://github.com/" + name,
            "license": {"spdx_id": "MIT"}, "updated_at": "2020", "stargazers_count": 1}

responses = [
    [item("x/nomatch", "nothing"), item("y/match", "报价 投标 弱电")],
    [item("z/match2", "报价 投标 弱电"), item("w/nomatch", "nothing")],
]
A._curl_json = lambda *a, **k: (responses.pop(0), None)

got, warn = A.collect_github(pack, limit_per_query=3, max_queries=2)
print([(g["id"], g["url"]) for g in got])
# -> [('GH-002', '.../y/match'), ('GH-002', '.../z/match2')]
```

随后 `radar/model.py` 的 `merge_sources` 最后一道唯一性断言会抛
`RadarError: 来源 ID 重复: ['GH-002']`，整次 run 在写完任何产物前失败。Gitee 同样可复现
（`GT-002` 重复）。

**影响**

- `--github/--gitee --max-queries > 1` 是 README 推荐用法；多查询时随时可能在花掉 API 配额后失败。
- `tests/test_radar.py:586-588` 把“偏移量等于响应下标”固化成期望，属于错误语义的回归测试。
- issue #11 的验收要求“3 个查询各返回 1 条 → 3 个不同 ID”，目前并未满足。

**涉及文件**

- `radar/adapters.py:69`、`:99`、`:116`、`:163`
- `tests/test_radar.py:578-588`

**验收标准**

用一个“已输出计数器”生成 ID（或先过滤再编号），保证 N 次查询的产出去重后 ID 唯一；
补 3 查询各含被过滤条目的回归测试；保留 `merge_sources` 的唯一性断言作为最后防线。

---

### P0-3 基线审计有盲区：跑错目录/覆盖基线都会 PASS，README 的 3 strong 不可复现

**现象**

1. `tools/audit_ledger.py:37-47`：`--run` 指向不存在的目录时打印
   `state_hashes: no sample run`，并把 `hash_ok` 设为 `True`，最终 `audit: PASS`。
2. `docs/BASELINE-DATA-CENTER.md:14` 给出的命令用的是 `runs/data-center-demo`，实际目录是
   `runs/data-center-ops-demo`。因此**文档里的审计命令会静默跳过哈希校验并 PASS**。
3. `run_demo.sh:6-8` 会 `rm -rf runs/weak-current-demo` 后**不带** `--verify-quotes` 重跑；
   结果是提交基线从 `3 strong / 20 evidence` 变成 `0 / 23`，而 README:102、
   `docs/BASELINE.md` 仍写 3 strong，`audit_ledger.py` 仍然 PASS（它只检查 seeds 的宽 covers /
   短 quote / 文件哈希，不检查覆盖数字）。

**复现**

```bash
python3 tools/audit_ledger.py --pack packs/data-center-ops/pack.json \
  --seeds seeds/data-center-ops.json --run runs/data-center-demo
# -> state_hashes: no sample run / audit: PASS   (退出码 0)

python3 -m radar run --pack packs/weak-current/pack.json \
  --seeds seeds/weak-current.json --title t --out /tmp/wc
# -> 0 strong / 23 evidence / 8 mention / 6 none
```

`run_demo.sh` 会直接覆盖已提交基线，**不要在不打算改基线时运行**。

**影响**

CI 的“Audit weak-current source ledger”看起来在保护基线，实际上无法发现基线被替换或
文档数字漂移；这对一个以“证据账本可复查”为卖点的仓库是信任问题。

**涉及文件**

- `tools/audit_ledger.py`
- `run_demo.sh`
- `docs/BASELINE-DATA-CENTER.md:14`
- `README.md:102`、`docs/BASELINE.md:10`
- `tests/test_radar.py`（`TestAudit` 只断言退出码 0）

**验收标准**

- `--run` 目录不存在 / 缺 `state.json` / 缺 `sources.jsonl` 时退出码非 0，不再“no sample run 即通过”。
- 审计至少校验 `coverage.json` 的 `summary` 与基线文档/期望值一致；或增加
  `--expect-strong 3 --expect-evidence 20` 一类显式断言。
- 修正 data-center 审计路径；CI 增加一条“文档基线数字 == 提交产物”的测试。
- `run_demo.sh` 要么使用与基线一致的验证参数，要么只写 `runs/local-demo`，不覆盖证据基线。

---

### P0-4 正文截断到 20k 后仍判 `false`，真实 quote 会被降级

**现象**

`radar/web.py:60` 的 `extract_html(..., max_chars=20000)` 先截断正文；`verify_quotes`
（`radar/web.py:138-147`）在“页面够长但找不到 quote”时返回 `false`。于是 20k 之后的真实
引文被判成“抓到了正文但 quote 不在里面”，`level_for_source` 降为 `mention`，claims 得到
`no_verified_source`。

**复现**

```python
from radar.web import extract_html, verify_quotes
page = "<html><body>" + ("padding sentence. " * 2000) + \
       "<p>THE REAL QUOTE IS AT THE END.</p></body></html>"
ex = extract_html(page)
print(len(ex["text"]))  # 20000
print(verify_quotes(["THE REAL QUOTE IS AT THE END."], ex["text"]))  # false，实际原文存在
```

**影响**

长标准页、长 README、长文档页的真实引文会被系统性地误判为“假”，比 `unknown` 更糟：
`false` 会主动降级，`unknown` 只是不升级。

**涉及文件**

- `radar/web.py:60`、`:138-147`
- `radar/verify.py:113`（web 分支走 `extract_html`）

**验收标准**

正文被截断时，缺失 quote 只能返回 `unknown`（或对完整正文做有上限的流式查找，命中即停）；
补一个“quote 在 20k 之后”的测试，断言不是 `false`。

---

## 3. P1：方向对，但会造成误导或运维风险

### P1-1 `scan` 失败仍留下完整 run 产物；`--out == --base` 会自毁基线

`radar/cli.py:245-257` 先执行 `cmd_run` 写完整产物（`state.mode="run"`），再读 base 做 diff。
`--base` 不存在时进程退出 1，但目录里已有 `coverage.json / report.md / state.json` 等一整套
“看起来成功”的 run。`--out` 与 `--base` 相同时，会先覆盖 base，再把它与自己比较，得到 0 变化，
并把原 base 的 `state.mode` 改成 `scan`、`since` 指向自己。

**验收**：`cmd_scan` 在写任何产物前校验 base（`coverage.json` + `sources.jsonl` + `state.json`）；
拒绝 `out == base`；`state.json` 最后写或增加 `status`；补两条 CLI 回归测试。

### P1-2 “来源级 strong”与“单源永不 strong”的文档/语义冲突

README:7-9、`.dsh/skills/radar/SKILL.md` 的硬规则、`docs/MVP.md` 都写“单源最高 evidence”，
但 `radar/model.py:251` 允许单条来源返回 `strong`，`report.md`/`coverage.md` 也直接展示它。
提交基线里 `SRC-001` 被标成 `strong`，而 M01 实际还需要 `SRC-008` 才能 strong，读者无法从
表格看出这一点。

**验收**：来源上下文改名为 `strong_candidate`，或单源级别封顶为 `evidence`，把 strong 只留给
单元覆盖层；同步 README、SKILL、QUOTES、report 文案；补断言测试。

### P1-3 非法 seeds/pack 类型会 traceback（新增的 P1-8 同类问题）

`normalize_source` 不校验 `quotes` 元素类型；`load_pack` 不校验 `query_templates` /
`source_map` 类型。`quotes: [123]` 能通过 `validate`，但 `--verify-quotes`/`--web` 在
`radar/web.py:140` 触发 `AttributeError`，CLI 直接打印栈（`main` 只捕获
`RadarError/OSError/ValueError`）。`query_templates` 写成字符串时，`gaps.md` 会输出
逐字符的“查询建议”。

**验收**：`model.normalize_source` 校验 `quotes` 为字符串数组；`load_pack` 校验
`query_templates` 为字符串数组、`source_map` 为 `{str: [str]}`；失败走 `RadarError` 并输出
`[fail]`；补 CLI 测试并断言 stderr 无 `Traceback`。

### P1-4 `diff` 用原始 URL，`changes` 用 canonical URL，同一来源会“删了又加”

`radar/diff.py:28-31` 以 `s["url"]` 为键；`radar/state.py` 的 `compare_sources` 用
`canonical_url`。把 `https://Example.com/a/` 改成 `https://example.com/a` 后，`diff.md` 同时
报告“新增 SRC-1 / 移除 SRC-1”，而 `changes.md` 认为未变。

**验收**：`diff_runs` 统一使用 `canonical_url`；补尾斜杠/scheme/`www` 的对照测试。

### P1-5 验证失败只是 warning；定时扫描会把“网络失败”报成“覆盖变化”

`verify_sources` 把 401/403/超时写进 warnings，退出码仍是 0；配合
`--require-web-verify`，所有未验证来源被重置为 `unknown`，strong 会静默掉成 evidence。
`scripts/scan_all.sh` 只看 0/1/2，于是 GitHub 速率限制（未认证 60 次/小时）看起来像“来源
内容变了”。另外 `cmd_run` 的 curl 预检（`radar/cli.py:119`）没有包含 `--verify-quotes`，
`--respect-robots` 也只覆盖 `--web`，不覆盖验证抓取。

**验收**：增加 `--fail-on-verify-error`（或验证错误数超过阈值时非 0），在 `state.json` 记录
验证成功/失败计数；`scan_all.sh` 把验证失败按“运行失败”处理；把 `--verify-quotes` 纳入 curl
预检并说明 robots 覆盖范围；用 mock 403 写测试。

### P1-6 `needs_review` 来源可以参与 strong

`radar/coverage.py:25` 只排除 `rejected`，`needs_review` 与 `selected` 同等计入
`verified`/`verified_hosts`。data-center 的 40 条里有 30 条 `needs_review`；只要其中出现
`real_artifact` + 验证 quote，就可能在没有人工复核的情况下产出 strong。

**验收**：明确语义。若“needs_review 必须人工复核后才算数”，则 strong 的 `verified` 只取
`selected`，或在 `state`/report 中显著标注“strong 含未复核来源”；补测试与文档。

### P1-7 `--fetch` 的全量默认和正文哈希会让变更检测长期噪声化

- `--fetch-limit` 默认 `0` 表示**不限条数**（`radar/fetch.py:78-83`），`--fetch` 会抓全部来源；
  负数则静默地一条都不抓（`if limit and count >= limit` 对 -1 恒真）。
- `content_hash` 是整个响应体的 SHA-256。实测：HTTP 头 `ETag` 不变、正文因 nonce 变化时，
  `compare_sources` 报告 `content_hash` 变化；真实动态页（GitHub HTML 等）会持续制造
  “来源变了”。

**验收**：显式定义并校验 limit（0=全部 或 默认 N，拒绝负数）；变更判定优先 `ETag` /
`Last-Modified`，把 `content_hash` 标为辅助证据；补“ETag 稳定但正文变化”的测试。

### P1-8 `merge_sources` 会静默丢掉被合并来源的 ID

同 canonical URL 的两条来源合并后只保留一个 ID，另一个只进 `_merged_from`
（`radar/model.py:271-319`）。任何引用被丢 ID 的 claim 都会在 `validate_claims` 报
“sources 含不存在的来源”。当前四个 seeds 没有重复 URL，但 `--github` / `--snowball` 可能制造。

**验收**：保留 ID 别名供 claim 解析，或在合并时输出 warning/非 0；补 claim + merge 的集成测试。

### P1-9 产物溯源不完整；claims 的 `state.json` 不符合 state 契约

- `state.options`（`radar/cli.py:183-189`）没有记录 `snowball_per_source`、`snowball_max`、
  `fetch_timeout`、`web_timeout`、`verify_limit`、`verify_timeout`，无法从产物精确复现一次运行。
- `claims` 也写 `out/state.json`（`radar/claims.py:191`），但字段集与
  `schemas/state.schema.json` 完全不同，且 README/`docs/CLAIMS.md` 没有列出这个文件。

**验收**：记录所有影响结果的参数；claims 元数据改名（如 `claims-state.json`）或补独立
schema 与文档；state schema 测试覆盖两种产物。

### P1-10 安全与隐私加固

- `report.md` / `sources.jsonl` 原样输出种子 URL；若 URL 带 `user:pass@` 或未知
  `?token=` 查询参数，会进入公开 run。`canonical_url` 只剥离已知跟踪参数。
- seeds 是外部输入，`--fetch/--web/--verify-quotes` 会带着 curl 访问其中任意 http(s) URL，
  没有 private/loopback/link-local 防护（本地 CLI 风险有限，但公开 pack 生态下值得明确）。
- `_curl_text`（`radar/verify.py`）没有 `--max-filesize`，与 `fetch_text` / `fetch_one` 不一致。
- `_gitee_token`（`radar/cli.py:40-47`）不检查 token 文件权限，而 README 建议 `chmod 600`。

**验收**：对 URL 做 userinfo/敏感 query 脱敏或拒绝；为网络选项增加可选的私网限制；给
`_curl_text` 加大小上限；token 文件权限不是 600 时给出 warning。

---

## 4. 文档与契约漂移（按“文件:说法 → 实际”列）

| 文件 | 文档说法 | 实际 |
| --- | --- | --- |
| `README.md:256`、`:278`、`HANDOFF.md:22`、`ROADMAP.md` 多处 | 77 个单测 | 191 tests（20 个可选依赖 skip）；PR #43 自己也写 191 |
| `docs/MIGRATION.md:31` | 软件版本 `1.2.0` | `radar/__init__.py` 为 `1.7.0` |
| `docs/MVP.md:5-6`、`:29` | CLI 只有 5 个命令；weak-current 34 条；第二个真实 pack 没做 | 已有 `parse`；35 条；已有 4 个 pack |
| `docs/BASELINE-DATA-CENTER.md:14` | `--run runs/data-center-demo` | 实际 `runs/data-center-ops-demo`，且该命令会静默 PASS |
| `docs/M14-COMPONENT-INVENTORY.md:24-31` | PDF 无解析器；列出 `radar/code_analyzer.py`、`ledger_*.py`、`business_graph.py`、对应 tests/docs | 当前 checkout 没有这些文件；PDF 解析器已存在。该文档更像另一条分支/另一仓库的盘点，需标注或重写 |
| `docs/OPEN_SOURCE_COMPONENT_SELECTION.md:58` | “尚未发现 pyproject.toml / requirements.txt” | 两者都存在，且已有 4 份 hashed requirements |
| `docs/architecture/dependency-management.md:28` | 解析器落地后才加 optional extras | 4 个解析器已落地，但依赖走 `requirements-*.txt`，`pyproject.toml` 没有 extras |
| `docs/SCHEMA.md` 文件表 | 4 份 schema | 实际 5 份，`discovery.schema.json` 未列入 |
| `docs/DISCOVERY-DATA-MODEL.md`、`schemas/discovery.schema.json`、`tests/test_discovery.py:132` | “八类领域对象” | `radar/discovery.py:13-16` 有 11 类（新增 `lef_/lmn_/lar_`），schema 的 ID pattern 和 `oneOf` 都不含 ledger 类型 |
| `docs/WEB.md:24` | 不会因抓正文升级成 strong | 见 P0-1，可升级 |
| `docs/context/RADAR-NOTES.md` | 4 个相对链接指向仓库外文件 | 断链；按 AGENTS 只应改指向，不搬运内容 |

**建议**：给 `docs/architecture/dependency-management.md` 和 `docs/M14-COMPONENT-INVENTORY.md`
补“生效分支/日期/是否历史快照”，或者把 M14 盘点移到分支文档；否则读者会把不存在的能力当成现状。

### 4.1 discovery 契约特别说明

`radar/discovery.py` 新增的 `ledger_effect`、`ledger_manifest`、
`ledger_aggregation_rule` 有必填字段、枚举、Workspace 存储集合和不可变约束，但没有：

- JSON Schema 定义（`schemas/discovery.schema.json` 的 `id` pattern 只允许 8 个前缀）；
- `docs/DISCOVERY-DATA-MODEL.md` 的语义说明；
- 一个“PREFIXES 必须被 schema 覆盖”的测试（现有测试只检查 8 个名字存在）。

**验收**：把 3 类 ledger 记录补进 schema 和文档，并加测试断言
`set(PREFIXES.values()) == schema id 前缀集合`；或明确把这 3 类标为 v2 实验能力并从 v1 契约中移出。

---

## 5. CI 与依赖治理

- `tests.yml` 在 `main` 和 PR 上跑完整测试 + 4 个 pack validate + weak-current audit，这是当前真正的门禁；本次本地复跑结果与之一致。
- `package-smoke.yml` 只在 `feat/requirement-driven-discovery` / `feat/m15-dependency-governance` 两个分支触发（`:5-8`），又要求路径命中；因此 `uv lock --check`、wheel/sdist、CLI entry point 在 `main` 上**从未被验证**。
- `capability-registry-tests.yml:6-11` 有重复分支名，且只覆盖若干 feature 分支；`discovery-domain-tests.yml` 的 push 也只有一个分支。建议这些工作流至少在 `main` + `pull_request` 生效，或合并进 `tests.yml`。
- `uv.lock` 目前只锁 editable 项目本身；4 个可选解析器的依赖由 `pip install --require-hashes -r requirements-*.txt` 安装，和 `pyproject.toml` 的 optional extras 方案不一致。两套方案都可行，但需要二选一并写进 `dependency-management.md`。
- 可选解析器矩阵（PDF/DOCX/XLSX/PPTX）设计是合理的：Core 不依赖它们，缺失时返回 `unavailable` 而不是空成功；本地 20 个 skip 就是这套机制在工作。

---

## 6. 做得好的地方（不是客套）

- **证据分层的核心不变量真实存在**：单元级 strong 要求 ≥2 来源、≥2 独立 host、≥1 条
  web 验证过的 `real_artifact` 以上；`rejected` 不计入；同 host 会在 `gaps.md` 标“同源待印证”。
- **合并保留并集**：issue #11 的 P0-3（合并丢 covers/quotes）已修好，`_merged_from` 也保留。
- **claim 层**：双向矛盾标记、单源/无 quote/proprietary/未验证来源的封顶、CSV 注入基础防护都在。
- **解析器的安全边界**：ZIP 条目/解压总量/压缩比/XML 声明检查、宏内容拒绝、`evidence_promoted=False`；
  可选依赖缺失时显式 `unavailable`，不伪装成功。
- **Capability 契约**：显式注册、无 entry-point 扫描、执行异常只返回错误码和异常类型、
  token 从 warning 中脱敏；CLI 懒加载网络/解析模块（有测试）。
- **产物溯源意识**：`state.json` 记录 pack/seeds 哈希、版本、commit；文档对 strong 的集中度
  风险（3 个 strong 都依赖 SRC-001）有主动披露，没有藏数字。

---

## 7. 建议处理顺序

1. **P0-1**（`--web` 自证）——先决定语义：要么给自动 quote 打标并禁止其单独支撑 strong，要么改文档并加显著提示。这是“证据雷达”定位的核心。
2. **P0-2**（ID 冲突）——改动小、验收明确，且 issue #11 已有先例；优先级高。
3. **P0-4**（20k 截断）——改动小，但会系统性误杀真证据。
4. **P0-3**（审计盲区 + 基线覆盖 + 路径 typo）——修复成本低，直接影响 CI 的可信度。
5. **P1-3 / P1-4**（输入校验、diff canonical）——同类“小修 + 回归测试”。
6. **P1-1**（scan 原子性/自比较）——避免失败留下可误读产物。
7. **P1-5**（验证失败信号）——定时扫描上线前必须解决。
8. **P1-2 / P1-6 / P1-8 / P1-9**（语义与溯源口径）——需要所有者先拍板。
9. **文档与 discovery/依赖契约批量对齐**——建议单独一个 docs/contract PR，避免和逻辑修复混在一起。
10. **P1-10**（安全加固）——作为长期 hardening，不阻塞前 8 项。

## 8. 本次复核的边界

- 没有使用真实的 GitHub/Gitee Token 跑 `--github/--gitee/--verify-quotes`；相关结论来自代码路径 + mock/HTTP 本地服务复现。
- 没有安装 4 个可选解析器依赖，因此本地有 20 个 skip；PDF/DOCX/XLSX/PPTX 的实际抽取质量未复核。
- 环境没有 `uv`，未执行 `uv lock --check` / `uv build`。
- 只在 Python 3.11 上跑过；3.9/3.13 的结论来自 CI 配置与既有 PR 记录，未在本机复跑。
- 除本文件外，没有修改仓库任何文件。
