---
name: brickscape
description: Design LEGO builds that can actually be built, using the BrickScape MCP server. Use when the user wants a LEGO scene, diorama, landscape, terrain, garden, cliff, river or tree designed, recreated from a photo, checked for buildability, or delivered as a BrickLink Studio .io file, parts list or building instructions. Works with official LEGO parts (default) or GoBricks.
---

# BrickScape: LEGO design that can be built

BrickScape is an MCP server. You never write LDraw coordinates by hand: you send a JSON
**build plan** of operations (hill, path, water, tree, ...) to the `build` tool, and BrickScape
places every part on real studs, removes anything that doesn't fit, swaps colours to ones that
really exist, and checks the result strictly (real parts and colours, no intersecting parts,
every part connected down to the baseplate).

## Setup (once)

```bash
pip install brickscape          # or: pip install git+https://github.com/xanzure/brickscape
brickscape setup                # LDraw library, Blender add-on, connection data, LEGO part data
claude mcp add brickscape -- brickscape-mcp
```
Renders and instructions need Blender 4.x. If the `brickscape` tools are not available, tell
the user to run the setup above rather than writing LDraw files by hand.

## Workflow

1. **Brief.** Restate the subject, board size (studs), main features and where they go,
   palette, and any limits (part count, colours, size). Ask only if something essential is
   missing; otherwise pick sensible defaults (32 x 32 board, green baseplate).
2. **Read the guide.** Call `guide` once per session: it lists every operation and field.
   The `build` tool's schema validates every field, and errors name the exact one.
3. **Plan.** Order matters: terrain first (`hill`, `block`), then `water` and `path`, then
   `boulder`, `tree`, `plant`, and `scatter` last. Later operations sit on earlier ones.
4. **Build** and read the report. `VALID` means it passed every check. Note what repair
   removed or recoloured.
5. **Look.** Call `render` and inspect all four views. Do at least one improvement round:
   change the plan, build again. A valid build is not yet a good one.
6. **Deliver** what the user asked for: `export` (Studio .io), `parts_list` (CSV + BrickLink
   wanted list), `instructions` (PDF, slow for big builds). Give the file paths.

## Coordinates

- Board `width` x `depth` in studs. x runs left to right; **z = 0 is the front edge** (nearest
  the viewer), z grows towards the back. "Along the back" means high z.
- Heights are plates: 3 plates = 1 brick. "4 bricks tall" = `"height": 12`.
- Areas: `{"rect": [x0, z0, x1, z1]}` (end exclusive), `{"ellipse": [cx, cz, rx, rz]}`,
  `{"polygon": [[x, z], ...]}` or `{"cells": [[x, z], ...]}`, plus optional `"rough": 0..1`.
- Any board size works: multiples of 16 get baseplates, others a two-layer plate floor.
  Nothing may reach past the board edge; repair removes it.

## Operations (summary; `guide` has the full reference)

| op | what it builds | key fields |
|---|---|---|
| `hill` | raised ground: `terraces` (grass and earth steps) or `rock` (cliff faces leaning back) | area, height (plates), style, falloff |
| `block` | hollow raised platform, tiles / studs / grass on top | area, height, colour, top, top_colour |
| `water` | a stream along points, or a pond over an area, with raised banks | points + width, or area |
| `path` | cobble or dirt path set into the ground | points, width, style |
| `boulder` | rounded rocks, 1 / 2 / 4 / 6 studs | at: [[x, z, size], ...] |
| `tree` | oak (small, medium, tall, fat, big), birch, pine, palm, cypress | kind, size, at, leaf, bark |
| `plant` | one plant: tuft, flower, flowers, bush, big_bush, fern, leafy, reeds, bamboo, cactus, succulent, stone | kind, at |
| `scatter` | many plants over an area | area, kinds, density (0.03-0.12), keep_clear |
| `brick` / `ldraw` | exact parts, for anything the generators don't cover | part, colour, at / lines |

## Design rules that score well

- **Make the main subject obvious and put it where the brief says.** A cliff "along the back"
  is a `hill` with `style: rock` over a strip at high z (e.g. `rect [0, 9, 32, 16]` on a
  32 x 16 board) with open ground in front, not rock spread over the whole board.
- **Respect every limit in the brief**: board size, part count, colours. Check the report's
  part count; reduce `scatter` density or tree size if over.
- Rock: `height` 12-36 with `falloff` 4-6 reads as a real cliff. Mix dark and light bluish grey.
- Trees: one big tree (`fat` or `big`) beats several small ones as a focal point. Keep other
  trees smaller and away from it.
- Water sits low with banks raised beside it; paths are set into the ground. Don't put
  plants in water or on paths (`keep_clear`).
- Fewer, better plants: `scatter` density 0.05-0.08 for most scenes, leave open ground.
- Use 2-3 greens and 2 rock greys. Colour names or LDraw codes both work.

## References

If the user gives a photo or a build file, use it, it makes a big difference:
- **Photo:** read the layout (what goes where, sizes in studs, colours), plan it, build, then
  call `compare` with the photo and a matching camera (renderer azimuth 225 = front-left,
  270 = front, 180 = left; elevation in degrees) and fix the biggest differences first.
- **Build file (.io / .ldr):** `study_reference` reports its footprint, height, density,
  hollowness, colours and most used parts; match its proportions and palette.

## Brick companies

Pass `source: "gobricks"` to `build`, `check`, `parts_list`, `search_parts` and `part_info`
to design for GoBricks parts, colours and prices instead of official LEGO (the default).

## Example

```json
{"name": "forest clearing", "board": {"width": 32, "depth": 32}, "seed": 1,
 "ops": [
  {"op": "hill", "area": {"ellipse": [22, 24, 9, 7], "rough": 0.5}, "height": 8, "style": "terraces"},
  {"op": "hill", "area": {"ellipse": [6, 26, 5, 4]}, "height": 12, "style": "rock"},
  {"op": "path", "points": [[0, 10], [14, 13], [31, 9]], "width": 3, "style": "cobble"},
  {"op": "boulder", "at": [[12, 3, 4], [20, 4, 2]]},
  {"op": "tree", "kind": "oak", "size": "medium", "at": [27, 4]},
  {"op": "scatter", "area": {"rect": [0, 0, 32, 32]}, "kinds": ["tuft", "flower", "bush"], "density": 0.06}
 ]}
```

## Checking other models

`check` validates any .ldr, .mpd or Studio .io file, including ones not made by BrickScape,
and lists intersecting parts, loose parts, unavailable parts and impossible colours.
