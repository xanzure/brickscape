#!/usr/bin/env sh
# BrickScape installer:  curl -LsSf https://raw.githubusercontent.com/xanzure/brickscape/main/install.sh | sh
# Installs the brickscape and brickscape-mcp commands (with uv if available, else pip --user),
# then downloads the LDraw library, connection data and LEGO part data.
set -e
PKG="${BRICKSCAPE_PACKAGE:-brickscape}"
GIT="git+https://github.com/xanzure/brickscape"

if command -v uv >/dev/null 2>&1; then
  echo "Installing BrickScape with uv ..."
  uv tool install --force "$PKG" 2>/dev/null || uv tool install --force "$GIT"
  BIN="$(uv tool dir --bin 2>/dev/null || echo "$HOME/.local/bin")"
elif command -v python3 >/dev/null 2>&1; then
  echo "Installing BrickScape with pip (user install) ..."
  python3 -m pip install --user --upgrade "$PKG" 2>/dev/null || python3 -m pip install --user --upgrade "$GIT"
  BIN="$(python3 -c 'import site, os; print(os.path.join(site.getuserbase(), "bin"))')"
else
  echo "BrickScape needs Python 3.10+ (or uv: https://docs.astral.sh/uv/)." >&2
  exit 1
fi

"$BIN/brickscape" setup

echo
echo "BrickScape is installed. Add it to Claude Code with:"
echo "  claude mcp add brickscape -- $BIN/brickscape-mcp"
case ":$PATH:" in *":$BIN:"*) ;; *) echo "(add $BIN to your PATH to run 'brickscape' directly)";; esac
