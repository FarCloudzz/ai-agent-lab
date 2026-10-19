# P0 任务卡

五张卡，按顺序做。规则只有三条：

1. **一次只做一张**，通过验收再进下一张，每张做完 commit 一次。
2. **卡住超过 30 分钟**再看 `ref/p0` 分支的参考实现（`git switch ref/p0`），看完切回来接着写。
3. 验收不过不算完成。跑不通就是没做完。

---

## 任务 1 · 发出第一个请求（非流式）

**目标**：`python3 main.py "你好"` 能打印出模型的回答。

**要做**
- 实现 `load_env`，把 `.env` 里的 `API_KEY` / `BASE_URL` / `MODEL` 读进环境变量
- 用 `urllib.request` 构造 POST 请求

**提示**
- 请求体最少只要两个字段：`model` 和 `messages`
- `messages` 从 `[{"role": "user", "content": task}]` 开始
- 这一张先不要碰 `tools`，先让它能说话

**验收**
```
$ python3 main.py "用一句话解释什么是 agent"
（打印出模型的一句话回答）
```

**常见坑**
- `BASE_URL` 要不要带 `/v1`：看 provider 文档，代码里自己拼 `/chat/completions`
- 报 400 时把响应体打印出来，错误信息通常直接告诉你是哪个字段不对

---

## 任务 2 · 改成流式输出

**目标**：回答一个字一个字往外蹦，而不是等半天一次性出现。

**要做**
- 请求体加 `"stream": true`
- 逐行读响应，只处理 `data:` 开头的行，遇到 `[DONE]` 停止
- 每行 JSON 里取 `choices[0].delta.content`，非空就打印

**提示**
- `print(text, end="", flush=True)` 才能看到实时效果
- `flush` 忘了加，看起来就像没流式

**验收**
```
$ python3 main.py "写 100 字介绍你自己"
（文字逐渐出现，能明显看到是分块的）
```

**常见坑**
- `choices` 可能是空数组（比如带 usage 的那个 chunk），要先判断
- 最后一行是 `data: [DONE]`，它不是 JSON，直接 `json.loads` 会崩

---

## 任务 3 · 把工具交给模型

**目标**：模型知道有哪些工具，并且会主动要求调用。

**要做**
- 请求体加上 `"tools": TOOLS` 和 `"tool_choice": "auto"`
- 打印出模型返回的 `tool_calls`（先不执行）

**提示**
- `tools.py` 里的 `TOOLS` 就是 JSON Schema 数组，直接传
- 模型决定调用工具时，`content` 往往是空字符串，重点在 `tool_calls`

**验收**
```
$ python3 main.py "看看 hello.py 里有什么"
（输出里出现 read_file 及其参数）
```

**常见坑**
- 不传 `tools` 时，模型会自己用文字描述"我应该读文件"，但不会真的调用

---

## 任务 4 · 执行工具并回填结果

**目标**：真正的循环——模型调用工具，你执行，把结果还给模型。

**要做**
- 把流式收到的 `tool_calls` 拼完整（**这是全篇最坑的一步**）
- 逐个执行，结果作为 `{"role": "tool", "tool_call_id": ..., "content": ...}` 追加
- 循环直到模型不再返回 `tool_calls`

**提示**
- 流式下每一片可能是：新的工具（带 `index`/`id`/`name`）、或参数的一小段（只有 `function.arguments`）
- `index` 相同的属于同一个调用，`arguments` 是字符串，要一段段累加
- 拼好的 assistant 消息要**原样**放回 `messages`，包括 `tool_calls` 字段，否则下一轮直接 400

**验收**
```
$ git checkout -- sandbox/hello.py      # 先恢复成坏版本
$ python3 main.py "修好 hello.py 里的 bug"
$ cat sandbox/hello.py                  # 确实被改对了
$ python3 sandbox/test_hello.py         # ok: 所有断言通过
```

**常见坑**
- `arguments` 拼出来是字符串，不是 dict，执行前要 `json.loads`
- 模型可能一步返回多个 tool_calls，要都执行
- 工具抛异常时，把错误**作为字符串返回给模型**，而不是让程序崩掉

---

## 任务 5 · 收尾：停止条件、预算、追踪

**目标**：让它在该停的时候停，并且留下可复盘的记录。

**要做**
- 没有 `tool_calls` 就退出，打印步数 / 耗时 / token
- `max_steps` 保护，打满上限时明确告诉用户"任务可能没做完"
- 每一步写一行 JSONL 到 `runs/<时间戳>.jsonl`（工具名、参数、结果、耗时）

**验收**
```
$ python3 main.py "修好 hello.py 里的 bug"
[完成] 4 步 · 6.2s · in=3184 out=412
[trace] runs/20261019-211500.jsonl

$ python3 main.py "修好 hello.py 里的 bug" --max-steps 2
[停止] 达到 max_steps=2，任务可能没做完
```

**常见坑**
- 没有上限时，模型可能在同一个错误上无限打转
- trace 要 `flush`，否则进程被 kill 时最后几步会丢

---

## 全部做完之后

跑一遍冒烟测试（用假模型，不花钱）：

```bash
bash tests/smoke_test.sh
```

然后**不看代码**回答这四个问题：

1. 为什么 `messages` 里要保留 assistant 那条带 `tool_calls` 的消息？
2. 流式下 `arguments` 为什么必须累加而不是覆盖？
3. 如果把 `max_steps` 去掉，最坏情况会发生什么？
4. 工具返回的错误信息，怎么写才能让模型更容易自救？

答不上来就回去看自己写的那段代码——比看别人的实现有用得多。
