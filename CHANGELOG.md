# Changelog

## 0.1.1 (2026-11-27)

Fixes
- `brickscape setup` now downloads the LDraw parts library itself: library.ldraw.org refuses
  Python's default user agent, so the download through ldraw-mcp failed on fresh machines.
- `brickscape setup` prepares Blender's add-on folder, so the ImportLDraw add-on installs on a
  machine where Blender has never been opened (renders work straight after setup).
- Tools that need part data now say clearly when the LDraw library isn't installed.

New
- MCP prompts: `design_scene`, `recreate_photo`, `check_model`.
- MCP resources: `brickscape://guide`, `brickscape://schema/plan`, `brickscape://colours`,
  `brickscape://examples/{forest-clearing,garden-20,showcase}` (example plans now ship in the package).
- Server instructions, title and website published to clients.
- Every tool has a title, read-only / write hints, a description for every input, and a fuller
  description of when to use it, what it returns and which files it writes.
- One-line installer: `curl -LsSf https://raw.githubusercontent.com/xanzure/brickscape/main/install.sh | sh`.
- Agent skill: `skills/brickscape/SKILL.md`.
- `tools/sandbox_test.sh`: install like a new user into a throwaway HOME and exercise every tool.

Docs
- README images use Markdown so MCP directories (Glama) display them; square icon in `assets/logo/icon.png`.

## 0.1.0 (2026-11-26)

First release: build plans, strict collision and connection checks, LEGO / GoBricks part
sources, Studio .io export, parts lists, renders, PDF instructions, benchmark.
