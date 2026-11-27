#!/usr/bin/env bash
# Install BrickScape like a new user would, in a throwaway sandbox (fresh HOME, nothing from this
# checkout), then exercise every tool over MCP.
#   tools/sandbox_test.sh pip  [git-ref]     pip install git+https://github.com/xanzure/brickscape
#   tools/sandbox_test.sh curl [git-ref]     curl ... install.sh | sh
#   tools/sandbox_test.sh pypi               pip install brickscape (after it's on PyPI)
# Blender isn't installed by BrickScape: set LDRAW_MCP_BLENDER (or have blender on PATH) to test
# renders; set NO_RENDER=1 to skip them.
set -euo pipefail
MODE="${1:-pip}"; REF="${2:-main}"
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(mktemp -d "${TMPDIR:-/tmp}/brickscape-sandbox-$MODE-XXXX")"
export HOME="$ROOT/home"; mkdir -p "$HOME" "$ROOT/work"
export PATH="$HOME/.local/bin:$PATH"
export BRICKSCAPE_OUT="$ROOT/work/out"
GIT="git+https://github.com/xanzure/brickscape@$REF"
echo "sandbox: $ROOT  (mode $MODE, ref $REF)"

case "$MODE" in
  pip)  python3 -m venv "$ROOT/venv"
        "$ROOT/venv/bin/pip" install -q "$GIT"
        BIN="$ROOT/venv/bin"; "$BIN/brickscape" setup ;;
  pypi) python3 -m venv "$ROOT/venv"
        "$ROOT/venv/bin/pip" install -q brickscape
        BIN="$ROOT/venv/bin"; "$BIN/brickscape" setup ;;
  curl) curl -LsSf "https://raw.githubusercontent.com/xanzure/brickscape/$REF/install.sh" \
          | BRICKSCAPE_PACKAGE="$GIT" sh
        BIN="$(uv tool dir --bin 2>/dev/null || echo "$HOME/.local/bin")" ;;
  *) echo "mode: pip | curl | pypi" >&2; exit 2 ;;
esac

echo; echo "== smoke test =="
# the smoke client only needs the MCP SDK: run it with the sandbox's own python
PY="$ROOT/venv/bin/python"; [ -x "$PY" ] || PY="$(dirname "$(readlink -f "$BIN/brickscape-mcp")")/python"
cd "$ROOT/work"
"$PY" "$HERE/smoke_client.py" "$BIN/brickscape-mcp" ${NO_RENDER:+--no-render}
