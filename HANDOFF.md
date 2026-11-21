# 如何把雷达交给其他 Agent

## 方式 A：DSH Agent（推荐）

```bash
# 目标 agent 的工作区
bash <radar-repo>/install.sh <target-workspace>
```

然后新开一个会话，让 agent 读 `.dsh/skills/radar/SKILL.md`，按 `AGENT-TASK.md` 执行。

## 方式 B：普通 CLI Agent

给对方的包：

```text
radar/
├── radar/             # CLI
├── packs/             # 行业包
├── seeds/             # 种子来源
├── docs/              # PACK/MVP
├── tests/             # 77 个单测
├── runs/weak-current-demo/  # 样例输出
├── README.md
├── AGENT-TASK.md
└── install.sh
```

对方需要：Python 3.9+、能读文件、能跑 shell。不需要安装依赖。

```bash
cd <repo>
python3 -m unittest discover -s tests -v
python3 -m radar run --pack packs/weak-current/pack.json --seeds seeds/weak-current.json \
  --title "弱电管理系统" --out runs/handoff-demo
```

## 方式 C：只读 Agent（不能跑命令）

只给：

- `runs/weak-current-demo/`（toc/coverage/gaps/report/sources）
- `packs/weak-current/pack.json`
- `AGENT-TASK.md`

它能读结果，但不能自己跑；让它基于样例做评审/对比。

## 不要给什么

- 聊天记录；
- 你的账号密码/Token；
- 专有来源全文；
- “必须写成完美 PRD”的要求。

## 版本

- 仓库：`<radar-repo>`
- 当前提交：以 `git log -1` 为准
- 版本：`1.7.0`（tag 由 owner 打）
- 运行模式：`run` / `scan --base` / `diff`

## 还没接

- MCP：没有。要给 MCP 客户端用，需要另写一个薄 server 包 CLI；
- Plugin：没有打包成 DSH 插件；目前是 skill + CLI；
- 定时任务：`scan` 可手动跑，未接 cron/DSH schedule。
