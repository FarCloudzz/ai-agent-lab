#!/usr/bin/env python3
"""
P0 · 最小 agent loop（零依赖，只用标准库）

整个 agent 只有四件事：
    while True:
        response = model(messages, tools)      # 1. 问模型
        messages.append(response)              # 2. 记录它说了什么
        if not response.tool_calls: break      # 3. 没有工具调用 = 结束
        for call in response.tool_calls:       # 4. 有就执行，结果塞回上下文
            messages.append(run(call))

不用任何 SDK，直接发 HTTP 请求，这样能看到协议到底长什么样：
messages 数组怎么组织、tools schema 怎么传、SSE 流怎么分片。

运行：
    python3 main.py "修好 hello.py 里的 bug"
    python3 main.py "..." --max-steps 10 --model deepseek-chat
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

from tools import TOOLS, WORKSPACE, run_tool

PROJECT_DIR = Path(__file__).resolve().parent
RUNS_DIR = PROJECT_DIR / "runs"
ENV_FILE = PROJECT_DIR / ".env"

SYSTEM_PROMPT = f"""你是一个在沙箱里工作的编码 agent。

工作目录：{WORKSPACE}
所有相对路径都相对于这个目录，run_shell 也在这个目录下执行。

规则：
1. 先读文件再修改，不要凭空猜测内容。
2. 改完必须验证：运行测试或脚本，用输出证明真的修好了。
3. 一次只修一个问题，改完立刻验证。
4. 工具报错时先读懂错误信息，再决定下一步；不要原样重试。
5. 任务完成就停下，不要做额外的事。
"""


# ---------------------------------------------------------------- 配置
def load_env(path: Path) -> None:
    """极简 .env 解析：KEY=VALUE，忽略注释和空行。已存在的环境变量优先。"""
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())


def chat_endpoint(base_url: str) -> str:
    base = base_url.rstrip("/")
    if base.endswith("/chat/completions"):
        return base
    return f"{base}/chat/completions"


# ---------------------------------------------------------------- 追踪
class Trace:
    """把每一步落成 JSONL，方便事后复盘 / 算 token。"""

    def __init__(self, model: str, task: str) -> None:
        RUNS_DIR.mkdir(exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        self.path = RUNS_DIR / f"{stamp}.jsonl"
        self._fh = self.path.open("w", encoding="utf-8")
        self._write({"kind": "start", "model": model, "task": task, "workspace": str(WORKSPACE)})

    def _write(self, obj: dict) -> None:
        obj["ts"] = datetime.now().isoformat(timespec="milliseconds")
        self._fh.write(json.dumps(obj, ensure_ascii=False) + "\n")
        self._fh.flush()

    def assistant(self, step, content, tool_calls, usage, dt) -> None:
        self._write({
            "kind": "assistant",
            "step": step,
            "content": content,
            "tool_calls": [
                {"name": c["function"]["name"], "arguments": c["function"]["arguments"]}
                for c in tool_calls
            ],
            "tokens": usage,
            "duration": round(dt, 3),
        })

    def tool(self, step, name, arguments, result, dt) -> None:
        self._write({
            "kind": "tool",
            "step": step,
            "name": name,
            "arguments": arguments,
            "result": result,
            "duration": round(dt, 3),
        })

    def end(self, status, totals, elapsed) -> None:
        self._write({"kind": "end", "status": status, "tokens": totals, "elapsed": round(elapsed, 2)})
        self._fh.close()


# ---------------------------------------------------------------- 模型调用
def stream_turn(url: str, api_key: str, model: str, messages: list[dict]):
    """一次模型调用，边收 SSE 边打印。返回 (content, tool_calls, usage)。"""
    payload = {
        "model": model,
        "messages": messages,
        "tools": TOOLS,
        "tool_choice": "auto",
        "stream": True,
        "stream_options": {"include_usage": True},
    }
    request = urllib.request.Request(
        url,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
            "Accept": "text/event-stream",
        },
    )

    parts: list[str] = []
    calls: dict[int, dict] = {}
    usage = None

    try:
        with urllib.request.urlopen(request, timeout=180) as response:
            for raw in response:
                line = raw.decode("utf-8", errors="replace").strip()
                if not line.startswith("data:"):
                    continue
                data = line[5:].strip()
                if data == "[DONE]":
                    break

                chunk = json.loads(data)
                if chunk.get("usage"):
                    usage = chunk["usage"]
                if not chunk.get("choices"):
                    continue

                delta = chunk["choices"][0].get("delta") or {}
                if delta.get("content"):
                    parts.append(delta["content"])
                    print(delta["content"], end="", flush=True)

                # 流式下 tool_calls 按 index 分片到达，参数 JSON 会被切开，要自己拼
                for tc in delta.get("tool_calls") or []:
                    slot = calls.setdefault(tc["index"], {"id": None, "name": "", "arguments": ""})
                    if tc.get("id"):
                        slot["id"] = tc["id"]
                    fn = tc.get("function") or {}
                    if fn.get("name"):
                        slot["name"] += fn["name"]
                    if fn.get("arguments"):
                        slot["arguments"] += fn["arguments"]

    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        sys.exit(f"\nAPI 返回 {exc.code}：{body[:800]}")
    except urllib.error.URLError as exc:
        sys.exit(f"\n连接失败：{exc.reason}（检查 BASE_URL 和网络）")

    tool_calls = [
        {
            "id": calls[i]["id"] or f"call_{i}",
            "type": "function",
            "function": {"name": calls[i]["name"], "arguments": calls[i]["arguments"] or "{}"},
        }
        for i in sorted(calls)
    ]
    return "".join(parts), tool_calls, usage


def assistant_message(content: str, tool_calls: list[dict]) -> dict:
    msg = {"role": "assistant", "content": content or ""}
    if tool_calls:
        msg["tool_calls"] = tool_calls
    return msg


# ---------------------------------------------------------------- 主循环
def run(task: str, model: str, max_steps: int) -> int:
    load_env(ENV_FILE)
    api_key = os.getenv("API_KEY")
    if not api_key:
        sys.exit("缺少 API_KEY：复制 .env.example 为 .env 并填写")

    base_url = os.getenv("BASE_URL") or "https://api.deepseek.com/v1"
    url = chat_endpoint(base_url)

    messages: list[dict] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": task},
    ]
    trace = Trace(model=model, task=task)
    totals = {"in": 0, "out": 0}
    started = time.time()

    for step in range(1, max_steps + 1):
        t0 = time.time()
        content, tool_calls, usage = stream_turn(url, api_key, model, messages)
        dt = time.time() - t0

        if usage:
            totals["in"] += usage.get("prompt_tokens", 0)
            totals["out"] += usage.get("completion_tokens", 0)

        messages.append(assistant_message(content, tool_calls))
        trace.assistant(step, content, tool_calls, usage, dt)
        print()

        if not tool_calls:
            elapsed = time.time() - started
            print(f"[完成] {step} 步 · {elapsed:.1f}s · in={totals['in']} out={totals['out']}")
            print(f"[trace] {trace.path}")
            trace.end("done", totals, elapsed)
            return 0

        for call in tool_calls:
            name = call["function"]["name"]
            raw_args = call["function"]["arguments"]
            print(f"[step {step}] {name}({raw_args})")

            t1 = time.time()
            try:
                result = run_tool(name, json.loads(raw_args or "{}"))
            except Exception as exc:  # 工具错误交还给模型，而不是直接崩
                result = f"ERROR: {type(exc).__name__}: {exc}"
            dt_tool = time.time() - t1

            messages.append({"role": "tool", "tool_call_id": call["id"], "content": result})
            trace.tool(step, name, raw_args, result, dt_tool)

            preview = result.replace("\n", " ")[:120]
            more = "..." if len(result) > 120 else ""
            print(f"           → {preview}{more} ({dt_tool:.2f}s)")

    print(f"\n[停止] 达到 max_steps={max_steps}，任务可能没做完")
    trace.end("max_steps", totals, time.time() - started)
    return 1


def main() -> None:
    parser = argparse.ArgumentParser(description="P0 最小 agent loop")
    parser.add_argument("task", help="要 agent 做的事，用自然语言描述")
    parser.add_argument("--max-steps", type=int, default=20, help="最多几轮，默认 20")
    parser.add_argument("--model", default=os.getenv("MODEL") or "deepseek-chat")
    args = parser.parse_args()

    sys.exit(run(args.task, args.model, args.max_steps))


if __name__ == "__main__":
    main()
