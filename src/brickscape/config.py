"""Where brickscape finds things. Everything can be overridden with environment variables.

  LDRAW_LIBRARY_PATH   LDraw parts library (default ~/.ldraw; `ldraw-mcp-setup` installs it)
  LDRAW_MCP_BLENDER    Blender binary (default: `blender` on PATH, via ldraw-mcp)
  BRICKSCAPE_DATA      catalog cache (default ~/.cache/brickscape)
  BRICKSCAPE_SOURCE    default part source: "lego" (default) or "gobricks"
"""
import os

LDRAW = os.path.expanduser(os.environ.get("LDRAW_LIBRARY_PATH", "~/.ldraw"))
DATA = os.path.expanduser(os.environ.get("BRICKSCAPE_DATA", "~/.cache/brickscape"))
SOURCE = os.environ.get("BRICKSCAPE_SOURCE", "lego")
PKG = os.path.dirname(os.path.abspath(__file__))


def blender():
    from ldraw_mcp.render import find_blender
    b = find_blender()
    if not b:
        raise RuntimeError("Blender not found: install Blender 4.x or set LDRAW_MCP_BLENDER")
    return b


def blender_script():
    import ldraw_mcp
    return os.path.join(os.path.dirname(ldraw_mcp.__file__), "blender_script.py")
