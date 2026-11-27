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


def report(run_dir, docs=None):
    prompts = {p["id"]: p for p in json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "prompts.json")))}
    rows = []
    for pid in sorted(os.listdir(run_dir)):
        d = os.path.join(run_dir, pid)
        if not os.path.exists(os.path.join(d, "judge.json")):
            continue
        j = json.load(open(os.path.join(d, "judge.json")))
        jl = os.path.join(d, "judge_looks.json")
        row = {"id": pid, "kind": prompts.get(pid, {}).get("kind", "?"), "outcome": j["outcome"],
               "outcome_looks": json.load(open(jl))["outcome"] if os.path.exists(jl) else None,
               "reasons": [r.get("reason", "") for r in j["rounds"]]}
        for c in ("mcp", "base"):
            ck = json.load(open(os.path.join(d, c, "check.json")))
            s = json.load(open(os.path.join(d, c, "session.json")))
            row[c] = {"valid": bool(ck.get("valid")), "pieces": ck.get("pieces", 0),
                      "collisions": ck.get("collisions"), "loose": ck.get("loose"),
                      "minutes": round(s.get("wall_s", 0) / 60, 1), "cost": s.get("total_cost_usd")}
        rows.append(row)
    n = len(rows) or 1
    wins = sum(r["outcome"] == "win" for r in rows)
    ties = sum(r["outcome"] == "tie" for r in rows)
    losses = len(rows) - wins - ties
    valid = {c: sum(r[c]["valid"] for r in rows) for c in ("mcp", "base")}
    lw = sum(r["outcome_looks"] == "win" for r in rows)
    lt = sum(r["outcome_looks"] == "tie" for r in rows)
    summ = {"prompts": len(rows), "wins": wins, "ties": ties, "losses": losses,
            "win_rate": round(100 * wins / n), "win_or_tie_rate": round(100 * (wins + ties) / n),
            "valid_rate": {c: round(100 * valid[c] / n) for c in valid},
            "looks_only": {"wins": lw, "ties": lt, "win_rate": round(100 * lw / n),
                           "win_or_tie_rate": round(100 * (lw + lt) / n)},
            "cost_usd": {c: round(sum(r[c]["cost"] or 0 for r in rows), 2) for c in ("mcp", "base")},
            "minutes": {c: round(sum(r[c]["minutes"] for r in rows), 1) for c in ("mcp", "base")}}
    json.dump({"summary": summ, "rows": rows}, open(os.path.join(run_dir, "results.json"), "w"), indent=1)
    docs = docs or os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "docs", "bench")
    os.makedirs(docs, exist_ok=True)
    open(os.path.join(docs, "outcomes.svg"), "w").write(_stack_svg(
        "brickscape vs plain Claude: judged outcomes",
        [("win", wins, COL["win"]), ("tie", ties, COL["tie"]), ("loss", losses, COL["loss"])]))
    open(os.path.join(docs, "outcomes_looks.svg"), "w").write(_stack_svg(
        "Judged on the renders alone (no checker report)",
        [("win", lw, COL["win"]), ("tie", lt, COL["tie"]), ("loss", len(rows) - lw - lt, COL["loss"])]))
    open(os.path.join(docs, "validity.svg"), "w").write(_bar_svg(
        "Builds that pass the strict checker", [("valid builds", [("with brickscape", summ["valid_rate"]["mcp"], COL["mcp"]),
                                                                 ("plain Claude", summ["valid_rate"]["base"], COL["base"])])], 100, "%"))
    open(os.path.join(docs, "per_prompt.svg"), "w").write(_bar_svg(
        "Parts per build", [(r["id"], [("brickscape", r["mcp"]["pieces"], COL["mcp"]), ("plain", r["base"]["pieces"], COL["base"])])
                            for r in rows], max([max(r["mcp"]["pieces"], r["base"]["pieces"]) for r in rows] + [1])))
    md = ["| prompt | kind | outcome | looks only | brickscape: parts / valid | plain: parts / valid |",
          "|---|---|---|---|---|---|"]
    for r in rows:
        md.append(f"| {r['id']} | {r['kind']} | **{r['outcome']}** | {r['outcome_looks'] or '-'} | {r['mcp']['pieces']} / {'yes' if r['mcp']['valid'] else 'no'} "
                  f"| {r['base']['pieces']} / {'yes' if r['base']['valid'] else 'no'} |")
    open(os.path.join(docs, "table.md"), "w").write("\n".join(md) + "\n")
    return json.dumps(summ, indent=1) + "\n" + "\n".join(md)


if __name__ == "__main__":
    print(report(sys.argv[1]))
