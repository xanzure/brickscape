"""Step-by-step building instructions as a PDF, made from any valid build.

1. Build order from the connection graph: a part can only be added once something it connects
   to is already there, and lower parts go first (so every step can really be built).
2. Steps of about `per_step` parts, kept to one layer where possible, neighbours together.
3. One Blender run renders every step from the same camera, plus a thumbnail of every part.
4. Pages: step number, a parts box (thumbnail x quantity), the step render. Saved as a PDF.

The ordered model is also written as an .ldr with 0 STEP lines, which BrickLink Studio's
Instruction Maker reads.
"""
import collections, math, os, subprocess
from brickscape.config import LDRAW, blender


def build_order(b):
    """Part indices (baseplates excluded) in a buildable order, and their step groups."""
    from brickscape.validate import connections
    edges, _ = connections(b)
    adj = collections.defaultdict(set)
    for i, j in edges:
        adj[i].add(j); adj[j].add(i)
    P = b.pieces
    placed = set(b.roots)
    left = set(range(len(P))) - placed
    order = []
    bottom = lambda i: -P[i].hi[1]             # height of the part's bottom (LDU, up = +)
    while left:
        ready = [i for i in left if adj[i] & placed]
        if not ready:                          # unconnected leftovers (validate reports them)
            ready = list(left)
        low = min(bottom(i) for i in ready)
        layer = [i for i in ready if bottom(i) <= low + 4]
        layer.sort(key=lambda i: (round(P[i].lo[2] / 80), P[i].lo[0]))
        order += layer
        placed |= set(layer)
        left -= set(layer)
    return order


def steps_of(b, order, per_step=10):
    """Split the order into steps: at most per_step parts, a new step when the layer changes."""
    P = b.pieces
    out, cur, h = [], [], None
    for i in order:
        hb = round(-P[i].hi[1] / 8)
        if cur and (len(cur) >= per_step or (h is not None and hb != h and len(cur) >= per_step // 2)):
            out.append(cur); cur = []
        cur.append(i); h = hb
    if cur:
        out.append(cur)
    return out


def write_ordered(b, steps, path):
    lines = [f"0 {b.name} - instructions", f"0 Name: {os.path.basename(path)}", "0 Author: brickscape", ""]
    for i in sorted(b.roots):
        lines.append(b.pieces[i].line())
    lines.append("0 STEP")
    for s in steps:
        lines += [b.pieces[i].line() for i in s] + ["0 STEP"]
    open(path, "w").write("\n".join(lines) + "\n")


def _content_box(im, margin=0.04):
    from PIL import Image, ImageChops
    bg = Image.new("RGB", im.size, im.getpixel((1, 1)))
    bb = ImageChops.difference(im, bg).convert("L").point(lambda v: 255 if v > 10 else 0).getbbox() or (0, 0, *im.size)
    m = int(margin * max(bb[2] - bb[0], bb[3] - bb[1]))
    return (max(0, bb[0] - m), max(0, bb[1] - m), min(im.width, bb[2] + m), min(im.height, bb[3] + m))


def _fit(im, w, h):
    s = min(w / im.width, h / im.height)
    return im.resize((max(1, int(im.width * s)), max(1, int(im.height * s))))


def make(b, out_dir, per_step=10, size=1000, samples=12, title=None, timeout=7200):
    """Instructions for Build b into out_dir. -> {"pdf", "ldr", "steps", "pages"}."""
    from PIL import Image, ImageDraw, ImageFont
    os.makedirs(out_dir, exist_ok=True)
    order = build_order(b)
    steps = steps_of(b, order, per_step)
    ordered = os.path.join(out_dir, "model_steps.ldr")
    write_ordered(b, steps, ordered)
    # cumulative object counts per step (baseplates first)
    counts, n = [], len(b.roots)
    for s in steps:
        n += len(s); counts.append(n)
    # thumbnails of every part/colour
    tdir = os.path.join(out_dir, "parts")
    os.makedirs(tdir, exist_ok=True)
    kinds = sorted({(b.pieces[i].part, b.pieces[i].color) for i in order})
    thumbs, todo = {}, []
    for part, col in kinds:
        f = os.path.join(tdir, f"{part}_{col}.ldr")
        thumbs[(part, col)] = f[:-4] + ".png"
        if not os.path.exists(thumbs[(part, col)]):
            open(f, "w").write(f"0 part\n1 {col} 0 0 0 1 0 0 0 1 0 0 0 1 {part}.dat\n")
            todo.append(f)
    plist = os.path.join(out_dir, "thumbs.txt")
    open(plist, "w").write("\n".join(todo) + "\n")
    script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "blender_steps.py")
    rdir = os.path.join(out_dir, "steps")
    os.makedirs(rdir, exist_ok=True)
    cmd = [blender(), "-b", "--factory-startup", "-P", script, "--", "--ldr", ordered,
           "--steps", ",".join(map(str, counts)), "--out", rdir, "--size", str(size),
           "--samples", str(samples), "--ldraw-dir", LDRAW] + (["--parts", plist] if todo else [])
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    if not os.path.exists(os.path.join(rdir, f"step_{len(steps):03d}.png")):
        raise RuntimeError("instruction render failed:\n" + "\n".join((p.stdout + p.stderr).splitlines()[-12:]))
    # pages
    try:
        font = ImageFont.truetype("DejaVuSans-Bold.ttf", 44)
        small = ImageFont.truetype("DejaVuSans.ttf", 22)
    except OSError:
        font = small = ImageFont.load_default()
    pages = []
    W, H = 1240, 1754                               # A4 at 150 dpi
    cover = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(cover)
    d.text((80, 80), title or b.name, fill=(30, 30, 30), font=font)
    d.text((80, 150), f"{len(order)} parts, {len(steps)} steps", fill=(90, 90, 90), font=small)
    final = Image.open(os.path.join(rdir, f"step_{len(steps):03d}.png")).convert("RGB")
    box = _content_box(final)                       # same crop for every step: the finished model
    final = _fit(final.crop(box), W - 160, H - 400)
    cover.paste(final, ((W - final.width) // 2, 260))
    pages.append(cover)
    for k, s in enumerate(steps):
        page = Image.new("RGB", (W, H), "white")
        d = ImageDraw.Draw(page)
        d.text((60, 50), str(k + 1), fill=(20, 20, 20), font=font)
        cnt = collections.Counter((b.pieces[i].part, b.pieces[i].color) for i in s)
        # parts box
        x, y, rowh = 160, 50, 0
        boxes = []
        for (part, col), q in sorted(cnt.items()):
            t = Image.open(thumbs[(part, col)]).convert("RGBA")
            t.thumbnail((110, 110))
            if x + t.width > W - 60:
                x, y = 160, y + rowh + 40
                rowh = 0
            boxes.append((x, y, t, q))
            x += t.width + 40
            rowh = max(rowh, t.height)
        bh = y + rowh + 40
        d.rounded_rectangle((140, 35, W - 50, bh), radius=18, outline=(120, 160, 200), width=3, fill=(236, 244, 252))
        for (bx, by, t, q) in boxes:
            page.paste(t, (bx, by), t)
            d.text((bx + t.width - 10, by + t.height - 5), f"{q}x", fill=(20, 20, 20), font=small)
        im = Image.open(os.path.join(rdir, f"step_{k + 1:03d}.png")).convert("RGB").crop(box)
        im = _fit(im, W - 100, H - bh - 120)
        page.paste(im, ((W - im.width) // 2, bh + 40))
        d.text((W - 160, H - 60), f"{k + 2}", fill=(150, 150, 150), font=small)
        pages.append(page)
    pdf = os.path.join(out_dir, "instructions.pdf")
    pages[0].save(pdf, save_all=True, append_images=pages[1:], resolution=150)
    return {"pdf": pdf, "ldr": ordered, "steps": len(steps), "pages": len(pages)}
