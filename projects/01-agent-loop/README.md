# P0 · 最小 agent loop

这个项目里的 `main.py` **由你自己写**。仓库只提供脚手架和任务卡。

agent 的骨架只有四步：

```python
while True:
    resp = model(messages, tools)     # 问模型
    messages.append(resp)             # 记录它说了什么
    if not resp.tool_calls: break     # 没有工具调用 = 结束
    for call in resp.tool_calls:      # 有就执行，结果塞回上下文
        messages.append(run(call))
```

看懂这 6 行只要一分钟，自己写出来是另一回事——尤其是流式下 `tool_calls` 的分片拼接。

## 从哪里开始

读 [TASK.md](TASK.md)，五张任务卡，从「任务 1 · 发出第一个请求」开始。

```bash
cd projects/01-agent-loop
cp .env.example .env      # 填 API_KEY，按需改 BASE_URL / MODEL
python3 main.py "你好"
```

零依赖，只用标准库。Python 3.10+。

## 我已经写好的部分（脚手架）

```
01-agent-loop/
├─ TASK.md           # 五张任务卡 + 验收标准
├─ main.py           # ← 你的战场（现在是骨架，全是 NotImplementedError）
├─ tools.py          # 三个工具 + JSON Schema + 路径沙箱，已写好
├─ sandbox/          # agent 的工作目录
│  ├─ hello.py       # 故意写坏了：sum_items 多跑一次循环
│  └─ test_hello.py  # 验收测试
├─ tests/
│  ├─ mock_provider.py   # 假模型服务，不花 token 也能跑通 loop
│  └─ smoke_test.sh      # 一键冒烟测试
└─ .env.example
```

`tools.py` 里值得一读的是三件事：JSON Schema 怎么写、返回值怎么截断、怎么把路径限制在沙箱内。

## 参考实现

```bash
git switch ref/p0        # 完整实现，卡住 30 分钟以上再看
git switch main          # 回来继续写
```

先自己写，再对照。顺序反了就白做了。

## 做完之后

```bash
bash tests/smoke_test.sh
```

用假模型把整个 loop 跑一遍：读取坏文件 → 写入修复 → 跑测试 → 输出结论。不花一分钱。

然后回答 TASK.md 末尾的四个问题。答不上来，说明代码是抄的不是写的。

## 已知局限（P1 / P2 再补）

- 上下文无限增长，没有压缩
- 工具串行执行，没有并行
- 危险操作没有人工审批（P2）
- 不能中断恢复（P2）
- 没有评估集，改 prompt 只能靠肉眼看（P3）
