# AI Agent Lab

学习 AI Agent 开发的个人仓库：从零手写 agent loop，到工具设计、状态管理、评估与可观测，
最后选一个方向做深。

## 从哪里开始

先读 [PLAN.md](PLAN.md)，里面有完整的阶段划分、验收标准和资源清单。

## 目录

| 目录 | 内容 |
|---|---|
| `notes/` | 学习笔记、踩坑记录、阶段复盘、技术决策 |
| `projects/` | 按阶段编号的完整项目 |
| `experiments/` | 一次性小实验，`日期-主题` 命名 |
| `evals/` | 任务集与评分脚本 |

## 环境

- Python 3.12（uv 管理）
- Node 22 / pnpm 10（TypeScript 备选）
- 模型 API key 放 `.env`，**不要提交**

```powershell
uv python install 3.12
uv sync
```

## 进度

见 [PLAN.md 第 8 节](PLAN.md#8-进度记录)。
