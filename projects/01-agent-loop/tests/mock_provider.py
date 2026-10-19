#!/usr/bin/env python3
"""
假的模型服务：没有 API key 也能验证 agent loop。

它按脚本返回固定的工具调用序列，报文格式和 OpenAI 的
/v1/chat/completions 流式响应一致，所以 main.py 一行都不用改。

    python3 tests/mock_provider.py --port 8765

然后：
    API_KEY=dummy BASE_URL=http://127.0.0.1:8765/v1 MODEL=mock-model python3 main.py "修好 hello.py"
"""

from __future__ import annotations

import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

FIXED_HELLO = '''def sum_items(items):
    total = 0
    for item in items:
        total += item
    return total


if __name__ == "__main__":
    print(sum_items([1, 2, 3]))
'''

# 按「请求里已经有几个 assistant 轮次」决定这一步做什么
SCRIPT = [
    {"tool": "read_file", "args": {"path": "hello.py"}},
    {"tool": "write_file", "args": {"path": "hello.py", "content": FIXED_HELLO}},
    {"tool": "run_shell", "args": {"command": "python3 test_hello.py"}},
    {"text": "测试通过了。bug 在 sum_items：循环范围多了一次，改成直接遍历 items 即可。"},
]


def _chunk(delta: dict, finish: str | None = None) -> dict:
    return {
        "id": "chatcmpl-mock",
        "object": "chat.completion.chunk",
        "created": 0,
        "model": "mock-model",
        "choices": [{"index": 0, "delta": delta, "finish_reason": finish}],
    }


def _usage(prompt_tokens: int, completion_tokens: int) -> dict:
    return {
        "id": "chatcmpl-mock",
        "object": "chat.completion.chunk",
        "created": 0,
        "model": "mock-model",
        "choices": [],
        "usage": {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
        },
    }


def build_events(step: dict, call_index: int) -> list[dict]:
    if "text" in step:
        text = step["text"]
        pieces = [text[i : i + 12] for i in range(0, len(text), 12)]
        events = [_chunk({"role": "assistant", "content": ""})]
        events += [_chunk({"content": p}) for p in pieces]
        events += [_chunk({}, finish="stop"), _usage(900, len(text))]
        return events

    # 工具调用：参数故意拆成两片，用来验证客户端的分片拼接逻辑
    args = json.dumps(step["args"], ensure_ascii=False)
    mid = len(args) // 2
    events = [
        _chunk({"role": "assistant", "content": ""}),
        _chunk({"tool_calls": [{
            "index": 0,
            "id": f"call_{call_index}",
            "type": "function",
            "function": {"name": step["tool"], "arguments": ""},
        }]}),
        _chunk({"tool_calls": [{"index": 0, "function": {"arguments": args[:mid]}}]}),
        _chunk({"tool_calls": [{"index": 0, "function": {"arguments": args[mid:]}}]}),
        _chunk({}, finish="tool_calls"),
        _usage(800, 40),
    ]
    return events


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):  # 静音访问日志
        pass

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length) or b"{}")
        messages = body.get("messages", [])
        assistant_turns = sum(1 for m in messages if m.get("role") == "assistant")
        step = SCRIPT[min(assistant_turns, len(SCRIPT) - 1)]

        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "close")
        self.end_headers()

        for event in build_events(step, assistant_turns):
            self.wfile.write(f"data: {json.dumps(event, ensure_ascii=False)}\n\n".encode())
        self.wfile.write(b"data: [DONE]\n\n")
        self.close_connection = True


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    print(f"mock provider listening on http://127.0.0.1:{args.port}/v1")
    server.serve_forever()


if __name__ == "__main__":
    main()
