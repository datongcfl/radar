# 给其他 Agent 的任务书（radar operator）

你负责**运行雷达**，不是重写雷达。先读 `README.md` 和 `.dsh/skills/radar/SKILL.md`。

## 输入

- 仓库路径：`<path>/radar`
- Pack：`packs/<industry>/pack.json`
- Seeds：`seeds/<industry>.json`
- 标题：用户给的一句需求
- 输出目录：`runs/<name>`

## 步骤

```bash
cd <path>/radar
python3 -m radar validate --pack <pack> --seeds <seeds>
python3 -m radar run --pack <pack> --seeds <seeds> --title "<title>" --out <out>
```

然后读：

- `toc.md`：模块/子系统 + 覆盖级别；
- `coverage.md`：模块×来源；
- `gaps.md`：无证据 + 单源待印证；
- `report.md`：汇总/低星/许可/来源；
- `sources.jsonl`：机器账本。

## 交付

1. 一句话结论：覆盖了多少模块/子系统，强/证据/提及/空各多少；
2. 3–5 个最值得看的来源（含许可/访问/为什么）；
3. 缺口清单：下一轮该搜什么；
4. 限制：哪些来源没读、哪些是单源、哪些不可复用。

## 硬规则

- 不改 `radar/` 引擎；需要新行业就加 `packs/<industry>/`；
- 补充来源可用 `python3 -m radar draft` 从 URL 起草，但必须人工/Agent 核对 `covers`、`license_status` 与正文原句 `quotes`（禁止用 `...` 拼接或改写总结充当 quote）；
- 单源最高 `evidence`，不能 `strong`；
- 专有来源只进参考池，不能复用；
- `needs_review`（含 GPL/AGPL 等强传染或未明许可）必须人工复核；
- 不绕过登录/付费/验证码；
- 不写完整 PRD；雷达只出目录/覆盖度/缺口。

## 如果 pack 不存在

按 `docs/PACK.md` 新建：模块 `M01…`、子系统 `S01…`、artifacts、keywords、source_map、query_templates。不要改引擎。
