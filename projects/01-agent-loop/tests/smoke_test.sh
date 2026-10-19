#!/usr/bin/env bash
# 用假模型服务跑一遍 P0：验证 loop、流式解析、三个工具都能工作。
# 先在项目目录里 source .venv/bin/activate，然后 bash tests/smoke_test.sh

set -euo pipefail

cd "$(dirname "$0")/.."

PORT="${PORT:-8765}"
PYTHON="${PYTHON:-python3}"
TMP="$(mktemp -d)"
cp sandbox/*.py "$TMP"/

"$PYTHON" tests/mock_provider.py --port "$PORT" >/dev/null 2>&1 &
MOCK_PID=$!
trap 'kill "$MOCK_PID" 2>/dev/null || true; rm -rf "$TMP"' EXIT

sleep 0.6

echo "=== 在临时沙箱里跑 agent: $TMP ==="
API_KEY=dummy \
BASE_URL="http://127.0.0.1:$PORT/v1" \
MODEL=mock-model \
WORKSPACE_ROOT="$TMP" \
"$PYTHON" main.py "修好 hello.py 里的 bug" --max-steps 6

echo
echo "=== 直接验证修好没有 ==="
(cd "$TMP" && "$PYTHON" test_hello.py)
