#!/usr/bin/env python3
"""
P0 · 最小 agent loop —— 这个文件由你实现。

按 TASK.md 的五张任务卡逐步填。目标不是写出 200 行，而是搞清四件事：

    1. 请求体里到底要放什么
    2. SSE 一行一行读下来长什么样
    3. tool_calls 为什么是分片的、怎么拼
    4. 循环靠什么结束

`tools.py` 已经写好了（三个工具 + schema + 路径沙箱），你只需要调用它。
参考实现放在 `ref/p0` 分支，卡住超过 30 分钟再看。
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from tools import TOOLS, WORKSPACE, run_tool

PROJECT_DIR = Path(__file__).resolve().parent
RUNS_DIR = PROJECT_DIR / "runs"

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


def load_env(path: Path) -> None:
    """任务 1：读 KEY=VALUE 格式的 .env，写进 os.environ。

    要求：忽略注释和空行；已存在的环境变量不要被覆盖。
    """
    raise NotImplementedError("任务 1")


def stream_turn(url: str, api_key: str, model: str, messages: list[dict]):
    """任务 2 + 3：发一次流式请求，返回 (content, tool_calls, usage)。

    返回值约定：
        content    str    模型说的文字
        tool_calls list   形如 [{"id":..., "type":"function", "function":{"name":..., "arguments":...}}]
        usage      dict|None   token 统计

    提示：用 urllib.request；响应体一行一行读，只处理 "data:" 开头的行。
    """
    raise NotImplementedError("任务 2")


def run(task: str, model: str, max_steps: int) -> int:
    """任务 4 + 5：主循环。返回值会作为进程退出码。"""
    raise NotImplementedError("任务 4")


def main() -> None:
    parser = argparse.ArgumentParser(description="P0 最小 agent loop")
    parser.add_argument("task", help="要 agent 做的事")
    parser.add_argument("--max-steps", type=int, default=20)
    parser.add_argument("--model", default="deepseek-chat")
    args = parser.parse_args()
    sys.exit(run(args.task, args.model, args.max_steps))


if __name__ == "__main__":
    main()
