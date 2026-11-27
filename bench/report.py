"""Benchmark report: summary numbers, a markdown table and SVG charts for the README.

    python bench/report.py bench/results/<run>
"""
import json, os, sys

COL = {"win": "#2f9e5b", "tie": "#c9a227", "loss": "#c4523d", "mcp": "#2f6fb0", "base": "#9aa3ad"}


def _bar_svg(title, rows, maxv, unit="", w=560):
    """Horizontal grouped bars: rows = [(label, [(series, value, colour), ...])]."""
    rh, pad, lw = 26, 14, 150
    h = 40 + len(rows) * (rh * max(len(r[1]) for r in rows) + pad) + 30
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" font-family="Helvetica,Arial,sans-serif" font-size="13">',
           f'<rect width="100%" height="100%" fill="white"/><text x="12" y="24" font-size="15" font-weight="bold">{title}</text>']
    y = 40
    for label, series in rows:
        out.append(f'<text x="12" y="{y + rh * len(series) / 2 + 4}">{label}</text>')
        for name, v, c in series:
            bw = 0 if maxv == 0 else (w - lw - 70) * v / maxv
            out.append(f'<rect x="{lw}" y="{y + 3}" width="{bw:.1f}" height="{rh - 6}" fill="{c}" rx="3"/>')
            out.append(f'<text x="{lw + bw + 6:.1f}" y="{y + rh - 9}">{v:g}{unit} {name}</text>')
            y += rh
        y += pad
    out.append("</svg>")
    return "\n".join(out)


def _stack_svg(title, parts, w=560):
    """One stacked bar: parts = [(label, count, colour)]."""
    total = sum(n for _, n, _ in parts) or 1
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="110" font-family="Helvetica,Arial,sans-serif" font-size="13">',
           f'<rect width="100%" height="100%" fill="white"/><text x="12" y="24" font-size="15" font-weight="bold">{title}</text>']
    x, bw = 12, w - 24
    for label, n, c in parts:
        ww = bw * n / total
        if ww > 0:
            out.append(f'<rect x="{x:.1f}" y="40" width="{ww:.1f}" height="34" fill="{c}"/>')
            if ww > 50:
                out.append(f'<text x="{x + 8:.1f}" y="62" fill="white" font-weight="bold">{label} {n}</text>')
        x += ww
    out.append(f'<text x="12" y="96" fill="#555">{total} prompts, each judged twice with the order swapped</text></svg>')
    return "\n".join(out)


def efficiency(m, b):
    """win if brickscape is cheaper AND faster, loss if worse on both, tie otherwise."""
    if not b.get("ok"):
        return "win" if m.get("ok") else "void"
    if not m.get("ok"):
        return "loss"
    cheaper, faster = (m["cost"] or 0) < (b["cost"] or 0), m["minutes"] < b["minutes"]
    return "win" if cheaper and faster else "loss" if not cheaper and not faster else "tie"


CATS = ("efficiency", "accuracy", "looks")


def report(run_dir, docs=None):
    prompts = {p["id"]: p for p in json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "prompts.json")))}
    rows = []
    for pid in sorted(os.listdir(run_dir)):
        d = os.path.join(run_dir, pid)
        if not os.path.exists(os.path.join(d, "judge_accuracy.json")):
            continue
        row = {"id": pid, "kind": prompts.get(pid, {}).get("kind", "?"), "reasons": {}}
        for c in ("mcp", "base"):
            ck = json.load(open(os.path.join(d, c, "check.json")))
            ss = json.load(open(os.path.join(d, c, "session.json")))
            row[c] = {"ok": bool(ck.get("sheet")), "valid": bool(ck.get("valid")), "pieces": ck.get("pieces", 0),
                      "minutes": round(ss.get("wall_s", 0) / 60, 1), "cost": ss.get("total_cost_usd")}
        row["efficiency"] = efficiency(row["mcp"], row["base"])
        for m in ("accuracy", "looks"):
            j = json.load(open(os.path.join(d, f"judge_{m}.json")))
            row[m] = j["outcome"]
            row["reasons"][m] = [r.get("reason", "") for r in j["rounds"]]
        rows.append(row)
    summ = {"prompts": len(rows), "categories": {}}
    for cat in CATS:
        scored = [r[cat] for r in rows if r[cat] != "void"]
        n = len(scored) or 1
        w, t = scored.count("win"), scored.count("tie")
        summ["categories"][cat] = {"wins": w, "ties": t, "losses": len(scored) - w - t, "scored": len(scored),
                                   "win_rate": round(100 * w / n), "win_or_tie_rate": round(100 * (w + t) / n)}
    n = len(rows) or 1
    summ["valid_rate"] = {c: round(100 * sum(r[c]["valid"] for r in rows) / n) for c in ("mcp", "base")}
    summ["cost_usd"] = {c: round(sum(r[c]["cost"] or 0 for r in rows), 2) for c in ("mcp", "base")}
    summ["minutes"] = {c: round(sum(r[c]["minutes"] for r in rows), 1) for c in ("mcp", "base")}
    json.dump({"summary": summ, "rows": rows}, open(os.path.join(run_dir, "results.json"), "w"), indent=1)
    docs = docs or os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "docs", "bench")
    os.makedirs(docs, exist_ok=True)
    for cat in CATS:
        k = summ["categories"][cat]
        open(os.path.join(docs, f"{cat}.svg"), "w").write(_stack_svg(
            f"{cat.title()}: BrickScape vs plain Claude",
            [("win", k["wins"], COL["win"]), ("tie", k["ties"], COL["tie"]), ("loss", k["losses"], COL["loss"])]))
    open(os.path.join(docs, "validity.svg"), "w").write(_bar_svg(
        "Builds that pass the strict checker", [("valid builds", [("with BrickScape", summ["valid_rate"]["mcp"], COL["mcp"]),
                                                                 ("plain Claude", summ["valid_rate"]["base"], COL["base"])])], 100, "%"))
    mx = max([max(r["mcp"]["minutes"], r["base"]["minutes"]) for r in rows] + [1])
    open(os.path.join(docs, "minutes.svg"), "w").write(_bar_svg(
        "Minutes per build", [(r["id"], [("BrickScape", r["mcp"]["minutes"], COL["mcp"]), ("plain", r["base"]["minutes"], COL["base"])])
                              for r in rows], mx))
    md = ["| prompt | kind | efficiency | accuracy | looks | BrickScape: parts, valid, min, $ | plain: parts, valid, min, $ |",
          "|---|---|---|---|---|---|---|"]
    f = lambda c: f"{c['pieces']}, {'yes' if c['valid'] else 'no'}, {c['minutes']}, {c['cost'] or 0:.2f}"
    for r in rows:
        md.append(f"| {r['id']} | {r['kind']} | {r['efficiency']} | {r['accuracy']} | {r['looks']} | {f(r['mcp'])} | {f(r['base'])} |")
    open(os.path.join(docs, "table.md"), "w").write("\n".join(md) + "\n")
    return json.dumps(summ, indent=1) + "\n" + "\n".join(md)


if __name__ == "__main__":
    print(report(sys.argv[1]))
