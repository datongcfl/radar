# Quote 验证（v1.1）

## 字段

每个 source 增加 `quote_verified`：

| 值 | 含义 | 最高覆盖 |
| --- | --- | --- |
| `true` | 抓取成功，quote 归一化后是正文子串 | strong |
| `false` | 抓到了正文，但 quote 不在里面 | mention |
| `unknown` | 没验证过（默认） | evidence |

## 怎么产生

- `--web` 抓取公开 HTML 后，会拿已有 quote 与提取正文做归一化子串匹配；
- 来源原本没有 quote 时，`--web` 提取的候选句子只标 `unknown`（防止自产自证），需经人工确认挑选后再用 `--verify-quotes` 核验；
- 抓取失败或正文超过截取上限仍未命中时保持 `unknown`，不误判为 `false`。

## 当前基线

v1.1 用 `--verify-quotes --require-web-verify` 实抓：

- weak-current：**3 strong**（M01/M06/M13）、20 evidence、8 mention、6 none；
- video-kb：**0 strong**、26 evidence、0 mention、0 none。

没有匹配到正文的 quote 降为 mention。  
加 `--require-web-verify` 后，seeds 自带的 `quote_verified` 会被当作 `unknown`，只有本次验证通过才可能 strong。

## 边界

- 这是**机械子串校验**，不是语义真伪；引用被篡改/拼接仍可能通过；
- 不抓登录/付费页；
- `unknown` 不等于假，只是“没验证”，所以不能升 strong。
