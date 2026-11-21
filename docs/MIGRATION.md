# 迁移与兼容

## 版本线

| 版本 | 变化 |
| --- | --- |
| 0.1 | pack/seeds/覆盖度/缺口 |
| 0.2.1 | Seed Lite：6 字段可用，`--strict` 保留 12 字段 |
| 0.2.2 | `scan --since` + `changes.md` |
| 0.2.3 | Gitee metadata |
| 0.2.4/0.2.5 | forks / `--fetch` |
| 0.3 | 静态网页抽取 + 许可提示 |
| 0.4 | claim 账本 + 置信度 |
| 0.5 | weak-current 34 条 + 审计 |
| 0.6 | `quote_verified` 强证据门禁 |
| 0.6.1 | `--require-web-verify` / claims cap / 端口 / rejected |
| 0.7 | video-kb 第二真实 pack |
| 1.0 | schema 文件化 + 迁移/handoff 冻结 |
| 1.1 | `--verify-quotes` 抓正文验证，weak-current 恢复 3 strong |
| 1.3 | claim 只认本次 web 验证来源，covers 需与已验证来源有交集 |
| 1.4 | `scan --fail-on-change` + `scripts/scan_all.sh` 定时扫描 |
| 1.4.1 | 补 weak M02/M10、video S07/S13；GitHub blob 文件校验 |
| 1.5 | 通用来源底座 + 1 条国标来源；第三 pack 后续 |
| 1.5.1 | 第三真实 pack：data-center-ops（40 条来源） |
| 1.6 | data-center 厂商具体页补证，20 evidence / 6 mention |
| 1.7 | 短关键词边界 + canonical URL 去重 |

## schema_version 与 __version__

- `schema_version`：数据格式，当前 `1`，不随软件版本自动变；
- `__version__`：软件版本，当前 `1.2.0`；
- 新字段默认可选；旧数据缺失时由 `normalize_source` 补默认值。

## 旧 run 读取

- 缺 `radar_version`：显示 `?`，不阻断；
- 缺 `quote_verified`：按 `unknown`，最高 evidence；
- 缺 `independent_count` / `evidence_count`：重新 `run` 生成；
- 缺 `state.schema_version`：视为 v0.x 产物，仅作只读参考。

## 升级动作

```bash
python3 -m unittest discover -s tests -v
python3 tools/audit_ledger.py
python3 -m radar run --pack packs/weak-current/pack.json \
  --seeds seeds/weak-current.json --title "upgrade check" --out runs/upgrade-check
```

不提供自动改写旧 run 的脚本；需要时按 `docs/SCHEMA.md` 手动迁移。
