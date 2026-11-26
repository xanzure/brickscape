<p align="center"><img src="assets/logo/logo.png" alt="BrickScape spelled in LEGO bricks on a green baseplate with trees, rocks and a stream" width="720"></p>

# brickscape

Landscape, but for bricks. An MCP server that lets an AI design LEGO builds that can actually
be built: it places parts on real studs and connection points, checks every build for
collisions and loose parts, and delivers a Studio `.io` file, renders and a part list.

> Work in progress. The full README (tools, benchmark, gallery) lands with the first release.

## Install (dev)

```bash
pip install -e ".[test]"
brickscape setup        # LDraw library, Blender add-on, connection data, LEGO part data
brickscape check model.ldr
```

Needs Python 3.10+ and Blender 4.x for renders.

## Credits

- [LDraw](https://www.ldraw.org) parts library (CC BY 4.0)
- [ldraw-mcp](https://github.com/musharna/ldraw-mcp) for Blender rendering (MIT)
- [ImportLDraw](https://github.com/TobyLobster/ImportLDraw) Blender add-on
- [LDCad shadow library](https://github.com/RolandMelkert/LDCadShadowLibrary) by Roland Melkert,
  connection data (CC BY-SA 4.0, downloaded at setup, not bundled)
- [Rebrickable](https://rebrickable.com/downloads/) part and colour data (downloaded at setup)

LEGO is a trademark of the LEGO Group, which does not sponsor or endorse this project.
