"""brickscape command line.

  brickscape setup                 download the LDraw library, connection data and LEGO part data
  brickscape check MODEL [--source lego|gobricks]   strict validation report
"""
import argparse, json, sys


def setup():
    from brickscape.catalog import lego
    from brickscape.core import snaps
    import subprocess
    print("LDraw library + Blender add-on (via ldraw-mcp-setup) ...")
    subprocess.run([sys.executable, "-m", "ldraw_mcp.setup_cli"], check=False)
    print("official LEGO part data (Rebrickable) ...", lego.download())
    print("connection data (LDCad shadow library) ...", snaps.download())


def main(argv=None):
    ap = argparse.ArgumentParser(prog="brickscape", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("setup")
    p = sub.add_parser("check"); p.add_argument("model"); p.add_argument("--source", default=None)
    a = ap.parse_args(argv)
    if a.cmd == "setup":
        setup()
    elif a.cmd == "check":
        from brickscape.core.brick import from_ldr
        from brickscape.validate import validate
        print(json.dumps(validate(from_ldr(a.model), source=a.source or "lego"), indent=1))


if __name__ == "__main__":
    main()
