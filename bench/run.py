"""brickscape benchmark: Claude with the brickscape MCP vs plain Claude, judged blind.

    python bench/run.py [--prompts id,id] [--run NAME] [--workers 3] [--stage build|judge|report|all]

For every prompt (bench/prompts.json):
  1. build: two fresh headless Claude Code sessions, same brief, each in its own empty folder
     (no CLAUDE.md, no memory, no other MCP servers). "mcp" gets the brickscape server; "base"
     gets the same file and shell tools and the LDraw library path, nothing else. Each must
     leave ./model.ldr.
  2. render + check: both models go through the same renderer (the 4 standard views, same
     camera angles) and the same strict checker.
  3. score three categories, each win / tie / loss for brickscape:
     - efficiency (measured): cost and wall time; better on both = win, worse on both = loss.
     - accuracy (judged): brief + measured facts (size, parts, colours, checker results).
     - looks (judged): the render sheets only.
     Each judged category uses two fresh Claude sessions with A/B swapped, so position can't
     decide it: brickscape wins both rounds = win, one each = tie, none = loss.
Results go to bench/results/<run>/results.json; `report` draws the charts in docs/.
"""
import argparse, concurrent.futures as cf, datetime, glob, json, os, shutil, subprocess, sys, time
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "src"))
MCP_BIN = os.path.join(os.path.dirname(sys.executable), "brickscape-mcp")

RULES = """Requirements:
- Use real official LEGO parts in colours LEGO actually makes them in.
- It must be physically buildable: every part held by a real connection (studs, clips, bars,
  hinges), nothing floating, no two parts intersecting.
- Minifig scale. Build on baseplates / a plate floor of the size the brief gives (or 32 x 32).
- Deliver the finished model as an LDraw file named model.ldr in the current directory.
Work on your own until it is done; do not ask questions."""

MCP_NOTE = """You have the brickscape MCP tools: start with its `guide` tool. When the build is
final, copy its model.ldr (the path the build tool reports) to ./model.ldr."""

BASE_NOTE = """The LDraw parts library is at {ldraw} (part files describe each part's geometry).
You can write and run Python or any other tool you like to produce the file."""

JUDGE = {
"accuracy": """You are judging two LEGO designs made for the same brief, on ACCURACY only: how
closely each one delivers what the brief asks for and how well it keeps the brief's limits
(board size, part count, colours, required features), and whether it can really be built.
Ignore how pretty it is; another judge scores looks.

Brief: {prompt}

A.png and B.png each show one design from the same 4 standard camera angles (front-left,
front-right, back-right, back-left). Measured facts:
- A: {va}
- B: {vb}

Use the Read tool on A.png and B.png. Then answer with ONLY a JSON object:
{{"winner": "A" or "B", "reason": "one sentence"}}""",
"looks": """You are judging two LEGO designs on LOOKS only: which one looks better as a
LEGO display model (natural and organic rather than blocky, good detail, colour and
composition). Ignore whether it follows any brief or can be built; other judges score that.

A.png and B.png each show one design from the same 4 standard camera angles.
Use the Read tool on A.png and B.png. Then answer with ONLY a JSON object:
{{"winner": "A" or "B", "reason": "one sentence"}}""",
}
MODES = ("accuracy", "looks")


def claude(prompt, cwd, tools, mcp_config=None, timeout=3600, model=None):
    cmd = ["claude", "-p", prompt, "--output-format", "json", "--no-session-persistence",
           "--strict-mcp-config", "--setting-sources", "", "--allowedTools", *tools]
    if mcp_config:
        cmd += ["--mcp-config", mcp_config]
    if model:
        cmd += ["--model", model]
    t = time.time()
    try:
        p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout)
        out = p.stdout
    except subprocess.TimeoutExpired as e:
        out = (e.stdout or b"").decode() if isinstance(e.stdout, bytes) else (e.stdout or "")
    try:
        r = json.loads(out.strip().splitlines()[-1])
    except (json.JSONDecodeError, IndexError):
        r = {"result": out[-2000:], "is_error": True}
    r["wall_s"] = round(time.time() - t, 1)
    return r


def build_one(run_dir, pr, cond, ldraw):
    d = os.path.join(run_dir, pr["id"], cond)
    if os.path.exists(os.path.join(d, "session.json")):
        return
    os.makedirs(d, exist_ok=True)
    tools = ["Read", "Write", "Edit", "Glob", "Grep", "Bash"]
    cfg = None
    if cond == "mcp":
        cfg = os.path.join(d, ".mcp.json")
        json.dump({"mcpServers": {"brickscape": {"command": MCP_BIN, "args": [],
                                                 "env": {"BRICKSCAPE_OUT": os.path.join(d, "brickscape-out")}}}},
                  open(cfg, "w"))
        tools.append("mcp__brickscape")
        note = MCP_NOTE
    else:
        note = BASE_NOTE.format(ldraw=ldraw)
    prompt = f"Brief: {pr['prompt']}\n\n{RULES}\n\n{note}"
    r = claude(prompt, d, tools, cfg)
    if "limit" in str(r.get("result", "")).lower() and r.get("is_error"):
        print(f"{pr['id']} {cond}: usage limit hit, rerun later", flush=True)
        return                                  # no session.json: a rerun redoes this build
    if not os.path.exists(os.path.join(d, "model.ldr")):          # fall back to the last build
        hits = sorted(glob.glob(os.path.join(d, "brickscape-out", "*", "model.ldr")), key=os.path.getmtime)
        if hits:
            shutil.copy(hits[-1], os.path.join(d, "model.ldr"))
    json.dump(r, open(os.path.join(d, "session.json"), "w"), indent=1)


def check_render(run_dir, pr, cond):
    from brickscape.core.brick import from_ldr
    from brickscape.validate import validate
    from brickscape.review.views import standard_views
    d = os.path.join(run_dir, pr["id"], cond)
    f = os.path.join(d, "model.ldr")
    res = {"exists": os.path.exists(f)}
    if res["exists"]:
        try:
            b = from_ldr(f)
            for p in b.pieces:
                p.soft = p.free = False
            v = validate(b, source="lego")
            c = v["checks"]
            res.update(pieces=v["pieces"], collisions=len(c["collisions"]), loose=len(c["not_connected"]),
                       bad_parts=len(c["parts"]) + sum(v["source"]["missing"].values()),
                       bad_colours=sum(v["source"]["bad_colour"].values()))
            res["valid"] = not (res["collisions"] or res["loose"] or res["bad_parts"])
            from brickscape.plan import colours as _cn
            names = {v: k for k, v in _cn().items()}
            body = [p for i, p in enumerate(b.pieces) if i not in b.roots] or b.pieces
            res["size_studs"] = [round((max(p.hi[0] for p in b.pieces) - min(p.lo[0] for p in b.pieces)) / 20),
                                 round((max(p.hi[2] for p in b.pieces) - min(p.lo[2] for p in b.pieces)) / 20)]
            res["height_bricks"] = round(-min(p.lo[1] for p in body) / 24, 1)
            res["colours"] = sorted({names.get(p.color, str(p.color)) for p in body})
        except Exception as e:                                       # unreadable model
            res["error"] = f"{type(e).__name__}: {e}"
        try:
            res["sheet"] = standard_views(f, os.path.join(d, "renders"), resolution=560, samples=12)["sheet"]
        except Exception as e:
            res["render_error"] = str(e)[-300:]
    json.dump(res, open(os.path.join(d, "check.json"), "w"), indent=1)
    return res


def summary(c):
    if not c.get("exists"):
        return "no model file was produced"
    if "error" in c:
        return f"model could not be read ({c['error'][:100]})"
    return (f"{c['pieces']} parts on a {c.get('size_studs', ['?', '?'])[0]} x {c.get('size_studs', ['?', '?'])[1]} stud area, "
            f"{c.get('height_bricks', '?')} bricks tall; colours: {', '.join(c.get('colours', []))}; "
            f"checker: {c['collisions']} intersecting part pairs, {c['loose']} parts not connected, "
            f"{c['bad_parts']} unknown/unavailable parts, {c['bad_colours']} parts in colours LEGO doesn't make")


def judge(run_dir, pr, mode="accuracy"):
    """Two fresh judge sessions (A/B swapped) for one category: accuracy or looks."""
    d = os.path.join(run_dir, pr["id"])
    out = os.path.join(d, f"judge_{mode}.json")
    if os.path.exists(out):
        return json.load(open(out))
    cm, cb = (json.load(open(os.path.join(d, c, "check.json"))) for c in ("mcp", "base"))
    rounds = []
    for k, order in enumerate((("mcp", "base"), ("base", "mcp"))):
        jd = os.path.join(d, f"judge_{mode}{k + 1}")
        os.makedirs(jd, exist_ok=True)
        ca, cbb = (cm if o == "mcp" else cb for o in order)
        if not ca.get("sheet") and not cbb.get("sheet"):
            rounds.append({"winner": None, "reason": "neither build rendered"})
            continue
        if not ca.get("sheet") or not cbb.get("sheet"):
            w = "A" if ca.get("sheet") else "B"
            rounds.append({"winner": order[0 if w == "A" else 1], "reason": "only one build rendered"})
            continue
        shutil.copy(ca["sheet"], os.path.join(jd, "A.png"))
        shutil.copy(cbb["sheet"], os.path.join(jd, "B.png"))
        r = claude(JUDGE[mode].format(prompt=pr["prompt"], va=summary(ca), vb=summary(cbb)), jd, ["Read"], timeout=900)
        txt = r.get("result", "")
        try:
            v = json.loads(txt[txt.index("{"):txt.rindex("}") + 1])
            win = order[0] if v["winner"].strip().upper() == "A" else order[1]
            rounds.append({"winner": win, "reason": v.get("reason", ""), "shown_as_A": order[0]})
        except (ValueError, KeyError, AttributeError):
            rounds.append({"winner": None, "reason": "unparseable verdict: " + txt[:200]})
    wins = sum(1 for r in rounds if r["winner"] == "mcp")
    if all(r["winner"] is None for r in rounds):
        res = {"rounds": rounds, "outcome": "void"}       # nothing to judge: rerun, don't score
    else:
        res = {"rounds": rounds, "outcome": "win" if wins == 2 else "loss" if wins == 0 else "tie"}
    json.dump(res, open(out, "w"), indent=1)
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--prompts", default="")
    ap.add_argument("--run", default=datetime.date.today().isoformat())
    ap.add_argument("--workers", type=int, default=3)
    ap.add_argument("--stage", default="all")
    a = ap.parse_args()
    from brickscape.config import LDRAW
    prompts = json.load(open(os.path.join(HERE, "prompts.json")))
    if a.prompts:
        keep = a.prompts.split(",")
        prompts = [p for p in prompts if p["id"] in keep]
    run_dir = os.path.join(HERE, "results", a.run)
    os.makedirs(run_dir, exist_ok=True)
    if a.stage in ("build", "all"):
        with cf.ThreadPoolExecutor(a.workers) as ex:
            list(ex.map(lambda t: build_one(run_dir, *t, LDRAW), [(p, c) for p in prompts for c in ("mcp", "base")]))
        for p in prompts:
            for c in ("mcp", "base"):
                print(p["id"], c, summary(check_render(run_dir, p, c)), flush=True)
    if a.stage in ("judge", "all"):
        for p in prompts:
            print(p["id"], *(f"{m}: {judge(run_dir, p, m)['outcome']}" for m in MODES), flush=True)
    if a.stage in ("report", "all"):
        from report import report
        print(report(run_dir))


if __name__ == "__main__":
    main()
