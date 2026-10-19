"""
P0 的三个工具。

工具设计的三条经验：
1. description 写清楚「什么时候用」和「返回什么」，模型靠它选工具。
2. 返回结果要截断，否则一个大文件就能把上下文吃满。
3. 出错时返回可读的错误字符串，而不是抛异常——模型能据此自救。
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent
WORKSPACE = Path(os.getenv("WORKSPACE_ROOT") or PROJECT_DIR / "sandbox").resolve()

MAX_OUTPUT = 4000          # 单次工具返回的字符上限
MAX_WRITE_PREVIEW = 80


def _resolve(rel_path: str) -> Path:
    """把相对路径解析到工作目录内，越界直接拒绝。"""
    path = (WORKSPACE / rel_path).resolve()
    if path != WORKSPACE and WORKSPACE not in path.parents:
        raise ValueError(f"路径越界：{rel_path}（只能访问 {WORKSPACE} 以内的文件）")
    return path


def _truncate(text: str) -> str:
    if len(text) <= MAX_OUTPUT:
        return text
    omitted = len(text) - MAX_OUTPUT
    return f"{text[:MAX_OUTPUT]}\n...（已截断 {omitted} 个字符，需要更多内容请用 start_line 分段读）"


def read_file(path: str, start_line: int = 1, max_lines: int = 300) -> str:
    """读文件，带行号。大文件用 start_line / max_lines 分段。"""
    target = _resolve(path)
    if not target.exists():
        raise FileNotFoundError(f"文件不存在：{path}")
    if not target.is_file():
        raise IsADirectoryError(f"这是目录不是文件：{path}")

    lines = target.read_text(encoding="utf-8", errors="replace").splitlines()
    start = max(1, start_line)
    chunk = lines[start - 1 : start - 1 + max_lines]
    if not chunk:
        return f"（{path} 共 {len(lines)} 行，start_line={start} 超出范围）"

    body = "\n".join(f"{start + i:4d} | {line}" for i, line in enumerate(chunk))
    tail = ""
    if start - 1 + len(chunk) < len(lines):
        tail = f"\n...（共 {len(lines)} 行，还有 {len(lines) - (start - 1 + len(chunk))} 行未显示）"
    return _truncate(body + tail)


def write_file(path: str, content: str) -> str:
    """写入文件（覆盖），目录不存在会自动创建。"""
    target = _resolve(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    preview = content.replace("\n", "\\n")[:MAX_WRITE_PREVIEW]
    return f"已写入 {path}（{len(content)} 字符，{len(content.splitlines())} 行）：{preview}"


def run_shell(command: str, timeout: int = 60) -> str:
    """在工作目录执行 shell 命令，返回退出码和输出。"""
    try:
        proc = subprocess.run(
            command,
            shell=True,
            cwd=WORKSPACE,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return f"TIMEOUT: 命令超过 {timeout}s 未结束，可能死循环了"

    parts = [f"exit={proc.returncode}"]
    if proc.stdout:
        parts.append(f"stdout:\n{proc.stdout}")
    if proc.stderr:
        parts.append(f"stderr:\n{proc.stderr}")
    if not proc.stdout and not proc.stderr:
        parts.append("（无输出）")
    return _truncate("\n".join(parts))


# ---------------------------------------------------------------- 工具表
# 这张表就是 agent 的「能力边界」：模型只能调用这里注册的东西。
REGISTRY = {
    "read_file": read_file,
    "write_file": write_file,
    "run_shell": run_shell,
}

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": (
                "Read a text file inside the workspace. Returns numbered lines. "
                "Use start_line/max_lines to page through large files."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "File path relative to the workspace root"},
                    "start_line": {"type": "integer", "description": "1-based first line, default 1"},
                    "max_lines": {"type": "integer", "description": "Max lines to return, default 300"},
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": (
                "Write text to a file inside the workspace, overwriting it. "
                "Parent directories are created automatically. Always read a file before overwriting it."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "File path relative to the workspace root"},
                    "content": {"type": "string", "description": "Full new file content"},
                },
                "required": ["path", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_shell",
            "description": (
                "Run a shell command in the workspace root and return exit code, stdout and stderr. "
                "Use it to run tests, linters or scripts. Prefer read_file over 'cat'."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "Shell command to execute"},
                    "timeout": {"type": "integer", "description": "Seconds before timeout, default 60"},
                },
                "required": ["command"],
            },
        },
    },
]


def run_tool(name: str, args: dict) -> str:
    func = REGISTRY.get(name)
    if func is None:
        return f"ERROR: 未知工具 {name}，可用工具：{', '.join(REGISTRY)}"
    return func(**args)
