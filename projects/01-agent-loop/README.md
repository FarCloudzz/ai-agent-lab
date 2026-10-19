# P0 · 最小 agent loop

不借助任何 agent 框架，用 ~250 行把 agent 的骨架写清楚：

```python
while True:
    resp = model(messages, tools)     # 问模型
    messages.append(resp)             # 记录它说了什么
    if not resp.tool_calls: break     # 没有工具调用 = 结束
    for call in resp.tool_calls:      # 有就执行，结果塞回上下文
        messages.append(run(call))
```

## 结构

```
01-agent-loop/
├─ main.py           # 循环、流式解析、trace
├─ tools.py          # 三个工具 + schema + 路径沙箱
├─ sandbox/          # agent 的工作目录（hello.py 故意写坏了）
│  ├─ hello.py
│  └─ test_hello.py
├─ tests/
│  ├─ mock_provider.py   # 假模型服务，不用 key 也能跑
│  └─ smoke_test.sh      # 一键冒烟测试
└─ .env.example
```

## 快速开始

```bash
cd projects/01-agent-loop
cp .env.example .env      # 填 API_KEY，按需改 BASE_URL / MODEL
python3 main.py "修好 hello.py 里的 bug"
```

**零依赖**：只用 Python 标准库直接发 HTTP 请求，不需要 `pip install`。
Python 3.10+ 即可。这也是刻意的选择——你看得到 `messages` 数组、`tools` schema、
SSE 分片到底长什么样，而不是被 SDK 挡住。

跑完会看到类似：

```
[step 1] read_file({"path": "hello.py"})
           → 12 | def sum_items(items):...  (0.00s)
[step 2] write_file({"path": "hello.py", "content": "..."})
           → 已写入 hello.py（168 字符，9 行）  (0.00s)
[step 3] run_shell({"command": "python3 test_hello.py"})
           → exit=0 stdout: ok: 所有断言通过  (0.05s)
[完成] 4 步 · 6.2s · in=3184 out=412
[trace] runs/20261019-211500.jsonl
```

`runs/*.jsonl` 是完整轨迹：每一步的输入输出、token、耗时。

## 没有 API key 也能验证

起了个假模型服务，返回格式和 OpenAI 的流式响应一致，用来验证 loop 和工具接线：

```bash
bash tests/smoke_test.sh
```

它会复制一份 sandbox 到临时目录，跑 agent，最后验证 `test_hello.py` 真的通过。

## 三个工具的设计要点

| 工具 | 关键点 |
|---|---|
| `read_file` | 带行号返回，支持分页；大文件不一次性全塞进上下文 |
| `write_file` | 自动建目录；返回写入摘要，而不是回显全文 |
| `run_shell` | 固定 cwd 在 sandbox；超时 60s；stdout/stderr 分开 |

共同约定：**工具出错不抛给用户，而是作为 `tool` 消息返回错误字符串**，让模型自己读错误、调整策略。这是 agent 和普通脚本最大的区别之一。

## 值得盯着看的几件事

1. **模型为什么有时候不调工具** —— 看 `tools.py` 里的 description，写不清楚它就猜。
2. **流式下 `tool_calls` 是分片的** —— 参数 JSON 会拆成好几块，`index` 相同的要拼起来，`main.py::stream_turn` 里有完整处理。
3. **上下文是单调增长的** —— 每轮都往 `messages` 里追加，20 步之后 token 会很难看。这是 P1 要解决的问题。
4. **工具报错的信息量决定 agent 能不能自救** —— 把 `FileNotFoundError: hello.py` 换成 `文件不存在：hello.py，当前目录有：...` 效果完全不同。

## 练习（做完再进 P1）

1. 加第 4 个工具 `list_dir`，只返回文件名和大小。
2. 加 `--max-tokens` 预算，超了就提前停止并让模型总结已完成的部分。
3. 让 `run_shell` 支持 `python3 test_hello.py` 之外的工作目录参数，想清楚怎么保证不越界。
4. 打开 trace 文件，统计每个工具的耗时分布，找出瓶颈。
5. 故意把 system prompt 里的「先读再改」删掉，观察 agent 行为怎么变差——这就是 prompt 的作用。

## 已知局限（P1 / P2 再补）

- 上下文无限增长，没有压缩
- 工具串行执行，没有并行
- 危险操作没有人工审批（P2）
- 只支持一次性任务，不能中断恢复（P2）
- 没有评估集，改 prompt 只能靠肉眼看（P3）
