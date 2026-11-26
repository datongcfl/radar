---
name: radar
description: 用行业 pack + 来源账本 + 覆盖度矩阵，产出目录/缺口/报告的最小行业雷达。
---

# radar

当用户要“按行业找需求、看覆盖度、找缺口”时使用；不是通用搜索，也不是自动写 PRD。

## 怎么用

```bash
cd <radar-repo>
python3 -m radar validate --pack packs/weak-current/pack.json --seeds seeds/weak-current.json
# 可选：--strict 要求 v0.1 的完整 12 字段
python3 -m radar draft --pack packs/weak-current/pack.json --url https://example.com/doc --covers M02 --seeds seeds/weak-current.json --out draft.json
python3 -m radar run --pack packs/weak-current/pack.json --seeds seeds/weak-current.json \
  --title "弱电管理系统" --out runs/weak-current-demo
# 可选：Gitee 需要 GITEE_TOKEN（env 或 ~/.config/radar/gitee_token）
python3 -m radar run ... --gitee --limit 3 --max-queries 3
# 可选：forward snowballing / 网络刷新
python3 -m radar run ... --snowball --snowball-max 5
python3 -m radar run ... --fetch --fetch-limit 5
# 可选：公开网页正文 + 许可提示
python3 -m radar run ... --web --web-limit 5 --respect-robots
python3 -m radar scan --pack packs/weak-current/pack.json --seeds seeds/weak-current.json \
  --title "弱电管理系统" --out runs/weak-current-demo-v2 --since runs/weak-current-demo
python3 -m radar diff --from runs/a --to runs/b --out runs/diff.md
python3 -m radar claims --pack packs/weak-current/pack.json --run runs/weak-current-demo \
  --claims examples/claims.weak-current.json --out runs/claims-demo
```

## 输出契约

- `toc.md`：模块/子系统 + 覆盖级别；
- `coverage.md`：模块×来源；
- `gaps.md`：无证据 + 单源待印证；
- `report.md`：汇总/低星/许可/来源清单；
- `sources.jsonl`：机器可读账本；
- `claims.md` / `claims.json` / `review.csv`：claim 账本与复核队列；
- `scan` 额外写 `changes.md`（来源级新增/移除/变化）和 `diff.md`（覆盖变化）。

## 硬规则

- 单源最高 `evidence`，不能 `strong`；
- 专有来源只进参考池，不能复用；
- `needs_review` 要人工复核；
- 网络选项需要 curl；非 2xx 不能当成功；
- 不绕过登录/付费/验证码；
- 不把行业结论写进引擎，写进 pack；
- 没有 quote 的来源最多 `mention`。

## 协同工作流（深挖源码 + 雷达验真）

1. **看缺口**：先跑 `run` 读 `gaps.md`，只针对 `none` / `mention` / 单源模块搜集；
2. **多源抓取与草稿**：每个缺口尽量跨 ≥2 个独立 host 检索（GitHub/Gitee/官网/标准/文档），先用 `radar draft` 自动拉取元数据与正文候选 quote，降低手填成本；
3. **源码深挖 + 原句核验**：在报告中可以深入读取目标开源仓库的数据模型/表结构/业务流程做参考，但写进 `seeds` 的 `quotes` **必须是页面正文或 README 里连续出现的原句子串（禁止用 `...` 拼接或 AI 改写总结）**，再用 `--web --verify-quotes --require-web-verify` 跑通机器核验；
4. **许可分池**：MIT/Apache/BSD 等宽松许可标记 `clear`，GPL/AGPL/LGPL/未知许可标记 `needs_review`，`All rights reserved` 标记 `proprietary`（只参考不复用）。

## 边界

- seeds 由人或 agent 填（可用 `radar draft` 辅助起草）；`--github` 只到 metadata；
- 不做 Gitee forks/GitHub dependents/浏览器/UI/自动 PRD；
- 结果用于“找缺口”，不是“证明完整”。
