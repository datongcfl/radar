# 视频转知识库 · 雷达运行报告

Run: `20261121-081357` · Pack: `video-kb` v0.1.0 · Radar: v1.7.0

## 一句话

本次用 32 条来源，覆盖 10 个管理模块 + 16 个子系统；强/证据/提及/空 = 0/26/0/0。

## 平台覆盖

| 平台 | 来源数 |
| --- | ---: |
| docs | 8 |
| github | 24 |

## 低星但高覆盖的发现

- 本次没有「低星（≤50）但覆盖 ≥2 格」的来源；这不代表没有低星好资料。

## 访问/许可需要注意

- `SRC-002` access=public, license_status=needs_review：['仓库未声明许可证，不能直接复用代码', '依赖 Gemini API（非纯本地）', 'covers 仅保留 quote 能直接支撑的单元', '仅短标题/描述，降为 mention']
- `SRC-013` access=public, license_status=needs_review：['GitHub 显示 NOASSERTION，许可需人工复核', '传统复习工具，不含视频链路']
- `SRC-024` access=public, license_status=needs_review：['仅公开 README/官网/metadata，未读代码；参考用']
- `SRC-025` access=public, license_status=needs_review：['仅公开 README/官网/metadata，未读代码；参考用', '仅页面 meta/标题，未作为正文 quote；降为 mention']
- `SRC-026` access=public, license_status=needs_review：['仅公开 README/官网/metadata，未读代码；参考用', '仅页面 meta/标题，未作为正文 quote；降为 mention']
- `SRC-027` access=public, license_status=needs_review：['仅公开 README/官网/metadata，未读代码；参考用']
- `SRC-028` access=public, license_status=needs_review：['仅公开 README/官网/metadata，未读代码；参考用', 'covers 仅保留 quote 能直接支撑的单元']
- `SRC-029` access=public, license_status=needs_review：['仅公开 README/官网/metadata，未读代码；参考用']
- `SRC-030` access=public, license_status=needs_review：['仅公开 README/官网/metadata，未读代码；参考用', 'covers 仅保留 quote 能直接支撑的单元', '官网旧标语，未保留 quote；降为 mention']
- `SRC-031` access=public, license_status=needs_review：['仅公开帮助文档，未读代码；参考用']
- `SRC-032` access=public, license_status=needs_review：['仅官网介绍，未读代码；参考用']

## 单源模块

- `M03` 文本结构化（evidence）
- `M07` 跨端与同步（evidence）
- `M08` 学习闭环（evidence）
- `M09` 隐私与本地化（evidence）
- `S01` 字幕优先抓取（evidence）
- `S06` LLM 摘要与大纲（evidence）
- `S07` 结构化笔记模板（evidence）
- `S09` 自动标签与聚类（evidence）
- `S12` 桌面客户端（evidence）
- `S13` 移动端（evidence）
- `S15` 复习/闪卡（evidence）
- `S16` 本地模型运行（evidence）

## 来源清单

| ID | 标题 | 平台 | 等级 | 许可 | 访问 |
| --- | --- | --- | --- | --- | --- |
| `SRC-001` | [bili2text — Bilibili 视频转文字](https://github.com/lanbinleo/bili2text) | github | evidence | MIT | public |
| `SRC-002` | [视频转文字工具 VideoTranscribe](https://github.com/Jane-xiaoer/claude-skill-video-transcribe) | github | mention | unknown（需复核） | public |
| `SRC-003` | [FunASR — 工业级语音识别工具包](https://github.com/modelscope/FunASR) | github | evidence | MIT | public |
| `SRC-004` | [whisper.cpp](https://github.com/ggml-org/whisper.cpp) | github | mention | MIT | public |
| `SRC-005` | [faster-whisper](https://github.com/SYSTRAN/faster-whisper) | github | mention | MIT | public |
| `SRC-006` | [SiYuan 思源笔记](https://github.com/siyuan-note/siyuan) | github | mention | AGPL-3.0 | public |
| `SRC-007` | [Memos](https://github.com/usememos/memos) | github | evidence | MIT | public |
| `SRC-008` | [Logseq](https://github.com/logseq/logseq) | github | mention | AGPL-3.0 | public |
| `SRC-009` | [Khoj — AI second brain](https://github.com/khoj-ai/khoj) | github | evidence | AGPL-3.0 | public |
| `SRC-010` | [Reor — 本地 AI 笔记](https://github.com/reorproject/reor) | github | evidence | AGPL-3.0 | public |
| `SRC-011` | [RAGFlow](https://github.com/infiniflow/ragflow) | github | mention | Apache-2.0 | public |
| `SRC-012` | [AnythingLLM](https://github.com/Mintplex-Labs/anything-llm) | github | mention | MIT | public |
| `SRC-013` | [Anki](https://github.com/ankitects/anki) | github | evidence | unknown（需复核） | public |
| `SRC-014` | [Fabric](https://github.com/danielmiessler/Fabric) | github | mention | MIT | public |
| `SRC-015` | [Private-ASR（FunClip 改）](https://github.com/MotorBottle/Private-ASR) | github | mention | MIT | public |
| `SRC-016` | [Whisper 官方多语种 ASR](https://github.com/openai/whisper) | github | evidence | MIT | public |
| `SRC-017` | [yt-dlp 视频/字幕下载](https://github.com/yt-dlp/yt-dlp) | github | evidence | Unlicense | public |
| `SRC-018` | [Docling 文档解析](https://github.com/docling-project/docling) | github | evidence | MIT | public |
| `SRC-019` | [Ollama 本地模型](https://github.com/ollama/ollama) | github | evidence | MIT | public |
| `SRC-020` | [Qdrant 向量库](https://github.com/qdrant/qdrant) | github | evidence | Apache-2.0 | public |
| `SRC-021` | [LangChain](https://github.com/langchain-ai/langchain) | github | evidence | MIT | public |
| `SRC-022` | [WhisperX 时间戳/说话人](https://github.com/m-bain/whisperX) | github | evidence | BSD-2-Clause | public |
| `SRC-023` | [pyannote 说话人分离](https://github.com/pyannote/pyannote-audio) | github | evidence | MIT | public |
| `SRC-024` | [OpenAI Speech to Text 文档](https://platform.openai.com/docs/guides/speech-to-text) | docs | mention | unknown（需复核） | public |
| `SRC-025` | [Ollama 官网](https://ollama.com/) | docs | mention | unknown（需复核） | public |
| `SRC-026` | [Qdrant 文档](https://qdrant.tech/documentation/) | docs | mention | unknown（需复核） | public |
| `SRC-027` | [LangChain 文档](https://docs.langchain.com/) | docs | mention | unknown（需复核） | public |
| `SRC-028` | [Obsidian 官网](https://obsidian.md/) | docs | evidence | unknown（需复核） | public |
| `SRC-029` | [Logseq 官网](https://logseq.com/) | docs | evidence | unknown（需复核） | public |
| `SRC-030` | [Anki 官网](https://apps.ankiweb.net/) | docs | mention | unknown（需复核） | public |
| `SRC-031` | [Obsidian Templates 文档](https://github.com/obsidianmd/obsidian-help/blob/master/en/Plugins/Templates.md) | github | evidence | unknown（需复核） | public |
| `SRC-032` | [Obsidian Mobile 官方页](https://obsidian.md/mobile) | docs | evidence | unknown（需复核） | public |

## 边界

- 大多数来源只到 metadata/readme/docs，不等于代码已验证；
- 专有来源只进参考池，不进可复用池；
- 覆盖度不是完整性证明，只是“有没有证据”的导航。
