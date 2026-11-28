# Changelog

## Unreleased

- New `waterfall` operation: a column of transparent blue bricks against a cliff face, with
  foam where it lands.
- `hill` with `style: rock` takes `lean` (how far the face steps back per brick; 0 = vertical,
  no rubble at the foot) and `accent_amount` (share of the accent colour).
- Fix: operations now claim every cell their parts cover. A rotation check used the wrong
  matrix entry, so later operations could be placed on top of earlier terrain's overhangs.
- Prompts work when a client sends no arguments at all (Glama's inspector currently does):
  they ask the user for the missing description, photo or file instead of erroring.

## 0.1.3 (2026-11-27)

- `build` takes the plan as JSON text in one field. Its schema used `$ref` definitions that
  form-based MCP inspectors (Glama's) can't resolve, so the tool couldn't be called there and
  plans had to be entered field by field. The full plan schema stays available as the
  `brickscape://schema/plan` resource and in `guide`; invalid plans still name the exact field.
- `search_parts` is about 25x faster after the first call (part descriptions are indexed once).
- `part_info` rounds sizes sensibly.
- Prompts accept empty or text arguments (form-based clients send empty boxes as ""), which
  made `design_scene` fail with an internal error.
- The guide no longer says boards must be multiples of 16 studs (any size from 4 to 192 works).

## 0.1.2 (2026-11-27)

- The MCP server downloads its part data by itself on first start when it's missing (LDraw
  library, LEGO part tables, connection data; about 150 MB, roughly 30 seconds). Until it's
  done, tools answer "downloading part data, try again in a minute". Hosted sandboxes such as
  Glama's and anyone who skips `brickscape setup` get working tools. Turn it off with
  `BRICKSCAPE_NO_AUTO_SETUP=1`.

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
