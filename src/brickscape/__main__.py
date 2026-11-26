"""brickscape command line.

  brickscape setup                          download the LDraw library + Blender add-on (via
                                            ldraw-mcp), connection data and LEGO part data
  brickscape serve                          run the MCP server (stdio), same as brickscape-mcp
  brickscape build PLAN.json [--source S]   compile a build plan -> brickscape-out/<name>/
  brickscape render NAME                    the 4 standard views
  brickscape export NAME                    Studio .io file
  brickscape parts NAME [--source S]        parts.csv + BrickLink wanted list
  brickscape instructions NAME [--per-step N]   PDF instructions
  brickscape check MODEL [--source S]       strict validation of any .ldr/.mpd/.io
  brickscape guide                          print the plan guide (all operations)

Part source S: lego (default) or gobricks.
"""
import argparse, sys


def setup():
    from brickscape.catalog import lego
    from brickscape.core import snaps
    import subprocess
    print("LDraw library + Blender add-on (ldraw-mcp-setup) ...")
    subprocess.run([sys.executable, "-m", "ldraw_mcp.setup_cli"], check=False)
    print("official LEGO part data (Rebrickable) ->", lego.download())
    print("connection data (LDCad shadow library) ->", snaps.download())


def main(argv=None):
    ap = argparse.ArgumentParser(prog="brickscape", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("setup"); sub.add_parser("serve"); sub.add_parser("guide")
    for c in ("build", "check", "parts"):
        p = sub.add_parser(c); p.add_argument("arg"); p.add_argument("--source", default="lego")
    for c in ("render", "export"):
        p = sub.add_parser(c); p.add_argument("arg")
    p = sub.add_parser("instructions"); p.add_argument("arg"); p.add_argument("--per-step", type=int, default=10)
    a = ap.parse_args(argv)
    if a.cmd == "setup":
        return setup()
    if a.cmd == "serve":
        from brickscape.server import main as serve
        return serve()
    from brickscape import server as S
    if a.cmd == "guide":
        print(S.guide())
    elif a.cmd == "build":
        print(S.build(open(a.arg).read(), source=a.source))
    elif a.cmd == "check":
        print(S.check(a.arg, source=a.source))
    elif a.cmd == "parts":
        print(S.parts_list(a.arg, source=a.source))
    elif a.cmd == "render":
        from brickscape.review.views import standard_views
        import os
        d = S._dir(a.arg)
        print(standard_views(os.path.join(d, "model.ldr"), os.path.join(d, "renders"))["sheet"])
    elif a.cmd == "export":
        print(S.export(a.arg))
    elif a.cmd == "instructions":
        print(S.instructions(a.arg, parts_per_step=a.per_step))


if __name__ == "__main__":
    main()
