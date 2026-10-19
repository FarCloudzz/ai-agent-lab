# AI Agent 开发学习计划

> 项目驱动，一人一仓。目标不是"会调框架"，而是能从零写出、调试、评估一个 agent，
> 并且知道框架替你做了什么。

---

## 0. 原则

1. **先裸写，后框架。** 一个 agent = `while` 循环 + `messages` 数组 + 工具表 + 停止条件。
   不亲手写一遍，后面所有框架都是黑盒。
2. **项目驱动。** 以"能做出来"推进，不以"看完教程"推进。每个阶段有可验证的验收标准。
3. **第一天就有 trace 和 eval。** 没有度量就没有迭代，改 prompt 全靠感觉 = 浪费时间。
4. **一次只加一个复杂度。** 工具、上下文、状态、多 agent、评估，逐个引入，每加一层都保证回归通过。
5. **写下来。** 每个阶段结束写一篇 `notes/`，讲清楚自己踩的坑。讲不清 = 没学会。

---

## 1. 环境基线

当前机器状态（2026-10 实测）：

| 项 | 现状 | 处理 |
|---|---|---|
| Python | 3.8.10 | **太旧**，多数 agent SDK 要求 3.10+，用 uv 装 3.12 |
| Node | v22.15.1 | 可用（TS 备选路线） |
| pnpm | 10.10.0 | 可用 |
| git | 2.32.0 | 可用 |
| uv | 未安装 | 第一步装 |
| gh CLI | 未安装 | 可选，纯 git 也能推 |

初始化：

```powershell
winget install --id astral-sh.uv -e    # 或 pip install --user uv
uv python install 3.12
uv python list                          # 确认 3.12 已就位
```

主语言定为 **Python**（生态最全、SDK 最先发），需要做 Web UI 时再上 TypeScript。

---

## 2. 阶段总览

总周期约 8–10 周，按每周 8–10 小时估算。可压缩，但不要跳阶段。

| 阶段 | 主题 | 周期 | 核心产出 | 验收标准 |
|---|---|---|---|---|
| **P0** | 裸 agent loop | 1 周 | 无框架 CLI agent，3 个工具 | 自主修好一个故意写坏的 `hello.py` |
| **P1** | 工具与上下文 | 1–2 周 | 工具规范 + 上下文管理 + 错误恢复 | 连续 20 轮不崩，token 有硬上限 |
| **P2** | 状态与人审 | 2 周 | 显式状态机 + checkpoint + 审批 | 中途 kill 进程后能恢复；危险操作必须人工确认 |
| **P3** | 评估与可观测 | 1–2 周 | 任务集 + 评分脚本 + trace 面板 | 有一张自己的通过率表，能证明改动有效 |
| **P4** | 专精方向 | 2 周+ | 一个可演示的作品 | 别人能 5 分钟内跑起来 |

---

## 3. 各阶段明细

### P0 · 裸 agent loop（1 周）

不做任何抽象，一个文件跑通 agent 的本质。

- [ ] 搭项目骨架：`projects/01-agent-loop/`，uv 管理依赖，`.env` 存 key
- [ ] 调用模型 API，支持流式输出
- [ ] 定义工具 schema（name / description / JSON Schema 参数）
- [ ] 实现循环：调模型 → 解析 tool_calls → 执行 → 结果回填 → 直到无工具调用或达到 `max_steps`
- [ ] 3 个工具：`read_file`、`write_file`、`run_shell`（限制工作目录内）
- [ ] 工具错误不要抛给用户，而是作为 `tool` 消息回传给模型，看它怎么自救
- [ ] 打印每一步：step 序号、工具名、参数、耗时、token 数

**要不要用 SDK：** 用官方 SDK 的 function calling 即可，不要用任何 agent 框架。

**验收：** 给一个带 `IndexError` 的 `hello.py`，让 agent 自己读、改、跑测试并修好，
全程不人工干预。录一份完整终端日志进 `notes/`。

**必须想明白的问题：**
- 模型为什么有时候不调用工具？→ 看 tool 的 description 和参数校验错误
- 循环什么时候停？→ 停止条件写在哪，`max_steps` 打满时怎么处理
- 上下文里到底放了什么？→ 每次把 messages 序列化下来看一眼

### P1 · 工具与上下文（1–2 周）

从"能跑"到"好用"的距离，几乎全在这里。

- [ ] **工具设计**：命名、description 写法、参数粒度（别做 swiss-army-knife 工具）
- [ ] 工具返回值截断（大文件、长日志），超限时给模型可操作的提示
- [ ] 并行 tool calls：多个独立调用并发执行
- [ ] 超时、重试、幂等；工具结果缓存
- [ ] **上下文管理**：system prompt 分层（身份 / 规则 / 环境 / 工具说明）
- [ ] 历史压缩策略：滑动窗口 / 摘要 / 关键信息抽取，三者对比
- [ ] 结构化输出：让模型稳定吐 JSON（schema 校验 + 失败重试）
- [ ] 读一遍 MCP 协议规范（工具协议的事实标准）

**验收：** 一次会话连续 20 轮以上，总 token 有硬上限，超出时自动压缩且不丢关键信息；
工具调用错误率可统计。

**坑：** 工具 description 写成"读取文件"必然失败；要写清楚什么时候用、什么参数、
返回什么、失败返回什么。

### P2 · 状态与人审（2 周）

agent 从"玩具"变成"能交付"的分水岭。

- [ ] 引入显式状态：每轮的状态快照（消息、待办、已执行动作、预算）
- [ ] checkpoint：每步持久化（JSONL 或 sqlite），支持从任意步恢复
- [ ] 中断与恢复：`Ctrl+C` 后能接着跑，不重复副作用
- [ ] **人工审批闸门**：危险工具（写文件、跑命令、发请求）执行前暂停等确认
- [ ] 预算控制：步数上限、token 上限、时间上限，超限优雅退出
- [ ] 此时再引入 LangGraph，用同一任务对照实现，读懂 graph / node / checkpoint 抽象
- [ ] 写对比笔记：手写版 200 行 vs 框架版，"框架替我做了什么"

**验收：** 长任务跑到第 8 步时直接 kill 进程，重新启动能从第 8 步继续；
删除文件的操作必须等待人工确认。

### P3 · 评估与可观测（1–2 周）

最容易被跳过、也最能拉开差距的一步。

- [ ] 建任务集 `evals/tasks/*.yaml`：任务描述、初始环境、成功判定
- [ ] 成功判定三种来源：字符串/文件断言、测试退出码、LLM-as-judge（慎用，需校准）
- [ ] 评分脚本 `evals/run.py`：批量跑、并发、记录 pass@1、步数、token、时延
- [ ] Trace：每步记录 `{step, tool, args, result, tokens, latency, error}` 到 JSONL
- [ ] 基线存档：`evals/results/<日期>-<标签>/`，改 prompt 前后对比
- [ ] 做一个最小可视化（HTML 或终端表格）看 trace

**验收：** 15 条任务，跑出通过率基线；做一次 prompt 改动，用数据说明提升或退步。

**坑：** LLM-as-judge 不稳定，先用人工标注校准 20 条，judge 和人工一致率 >85% 才敢用。

### P4 · 专精方向（2 周+，选一个深挖）

| 方向 | 学什么 | 最小作品 |
|---|---|---|
| **Coding agent** | 代码检索、编辑策略、测试驱动、沙箱 | 能修仓库里真实 issue 的 CLI |
| **RAG / Memory** | 切分、检索、重排、长期记忆写入与遗忘 | 能记住历史偏好并引用的问答 agent |
| **Browser / GUI** | 元素定位、动作空间、失败恢复 | 自动完成一个多步网页任务 |
| **Multi-agent** | 拓扑、消息协议、仲裁、成本 | 编排 vs 单 agent 的量化对比 |
| **MCP 生态** | 协议实现、写一个 server | 把自己写的工具暴露成 MCP server |

**验收：** 有 README、能一键跑、有评估数据、有 3 分钟演示录屏。

---

## 4. 目录结构

```
AI Agent/
├─ PLAN.md               # 本文件
├─ README.md             # 仓库说明
├─ notes/                # 学习笔记、踩坑记录、阶段复盘
│  └─ decisions/         # 关键技术选择的理由（ADR）
├─ projects/
│  ├─ 01-agent-loop/     # P0
│  ├─ 02-tools-context/  # P1
│  ├─ 03-stateful/       # P2
│  └─ 04-eval/           # P3
├─ experiments/          # 一次性实验，按 日期-主题 命名
└─ evals/                # 任务集与评分脚本，跨项目复用
```

一个仓库装全部阶段：公共能力（模型调用、trace、eval）可以互相复用，
`notes/decisions/` 能看清自己是怎么一步步想明白的。

---

## 5. 技术选型

| 用途 | 选择 | 理由 |
|---|---|---|
| 包与 Python 版本 | uv | 装 Python、锁依赖、跑脚本，一条命令 |
| 模型调用 | 官方 SDK（OpenAI / DeepSeek / Anthropic 兼容层） | 先吃透原生 function calling |
| 结构化输出 | Pydantic + 手动校验重试 | 不依赖 SDK 的 magic |
| 状态机（P2） | 先手写，后 LangGraph | 对照学习 |
| Trace | 先 JSONL，后 OpenTelemetry | 别一上来上平台 |
| 评估 | 自己写 100 行脚本 | 先跑通再考虑 eval 平台 |
| UI（可选） | 先 CLI，后 FastAPI + 简单网页 | 界面是最不值钱的部分 |

框架全景可参考：[12 Best AI Agent Frameworks in 2026](https://www.respan.ai/articles/best-ai-agent-frameworks)。
结论：LangGraph 做复杂状态、Vercel AI SDK / Mastra 做 TS、Claude Agent SDK 做编码类，
但**前三个阶段一律不用框架**。

---

## 6. 每周节奏

- **工作日碎片（30 分钟/天）**：读文档、看 trace、写笔记
- **周末整块（4–6 小时）**：写代码，推进当前阶段
- **每阶段末**：跑一次评估 → 写复盘 → 打 tag（`git tag p0-done`）

复盘模板：

```markdown
## P0 复盘（日期）
做了什么：
验收是否通过：
最大的坑：
下次会怎么做：
还想搞明白的问题：
```

---

## 7. 资源清单

**必读**
- Anthropic《Building Effective Agents》—— 工作流 vs agent 的边界
- OpenAI《A Practical Guide to Building Agents》
- MCP 协议规范（工具、资源、提示三原语）
- LangGraph 文档的 State / Checkpoint / Interrupt 三章（P2 再读）

**参考工程**
- `smolagents`：几百行的最小 agent，适合读源码
- Claude Code / Codex CLI：观察成熟 harness 的工具设计与权限模型

**社区经验**
- [Google：Agent Bake-Off 的 5 条经验](https://developers.googleblog.com/en/build-better-ai-agents-5-developer-tips-from-the-agent-bake-off/)
- [Arize：agent 架构与评估实践](https://arize.com/blog/building-smarter-ai-agents-architecture-evals-and-lessons-from-the-field/)

---

## 8. 进度记录

| 阶段 | 开始 | 结束 | 验收 | 复盘 |
|---|---|---|---|---|
| P0 | | | ☐ | |
| P1 | | | ☐ | |
| P2 | | | ☐ | |
| P3 | | | ☐ | |
| P4 | | | ☐ | |

---

## 9. 现在就开始

```powershell
winget install --id astral-sh.uv -e
uv python install 3.12
cd projects/01-agent-loop
uv init --python 3.12
```

第一行代码之前，先回答：**我的 agent 循环，在什么条件下停下来？**
