"""Deliverables: BrickLink Studio .io files and part lists.

Studio's .io is a ZIP (traditional PKWARE encryption, password "soho0909") holding model.ldr
(LDraw colours), a .info JSON with the version and part count, and optionally thumbnail.png.
Python's zipfile can read that encryption but not write it, so the writer is here.
"""
import binascii, collections, csv, io, json, os, struct, time, zlib, random
from xml.sax.saxutils import escape

PASSWORD = b"soho0909"
_CRC = [binascii.crc32(bytes([i])) ^ 0 for i in range(256)]


def _crc_table():
    t = []
    for i in range(256):
        c = i
        for _ in range(8):
            c = (c >> 1) ^ 0xEDB88320 if c & 1 else c >> 1
        t.append(c)
    return t


_T = _crc_table()


class _ZipCrypto:
    def __init__(self, pw):
        self.k = [305419896, 591751049, 878082192]
        for c in pw:
            self._update(c)

    def _update(self, c):
        k = self.k
        k[0] = (k[0] >> 8) ^ _T[(k[0] ^ c) & 0xFF]
        k[1] = (k[1] + (k[0] & 0xFF)) & 0xFFFFFFFF
        k[1] = (k[1] * 134775813 + 1) & 0xFFFFFFFF
        k[2] = (k[2] >> 8) ^ _T[(k[2] ^ (k[1] >> 24)) & 0xFF]

    def encrypt(self, data):
        out = bytearray(len(data))
        for i, p in enumerate(data):
            t = (self.k[2] | 2) & 0xFFFF
            out[i] = p ^ (((t * (t ^ 1)) >> 8) & 0xFF)
            self._update(p)
        return bytes(out)


def _dos_time(t=None):
    t = time.localtime(t)
    return ((t.tm_hour << 11) | (t.tm_min << 5) | (t.tm_sec // 2),
            ((t.tm_year - 1980) << 9) | (t.tm_mon << 4) | t.tm_mday)


def write_encrypted_zip(path, files, password=PASSWORD):
    """files: {name: bytes}. Deflated, ZipCrypto-encrypted members."""
    tm, dt = _dos_time()
    body, central = bytearray(), bytearray()
    for name, data in files.items():
        nb = name.encode()
        crc = zlib.crc32(data) & 0xFFFFFFFF
        comp = zlib.compressobj(9, zlib.DEFLATED, -15)
        raw = comp.compress(data) + comp.flush()
        zc = _ZipCrypto(password)
        header = bytearray(random.getrandbits(8) for _ in range(11)) + bytes([crc >> 24])
        enc = zc.encrypt(bytes(header)) + zc.encrypt(raw)
        off = len(body)
        body += struct.pack("<IHHHHHIIIHH", 0x04034B50, 20, 1, 8, tm, dt, crc, len(enc), len(data), len(nb), 0)
        body += nb + enc
        central += struct.pack("<IHHHHHHIIIHHHHHII", 0x02014B50, 20, 20, 1, 8, tm, dt, crc, len(enc),
                               len(data), len(nb), 0, 0, 0, 0, 0, off) + nb
    end = struct.pack("<IHHHHIIH", 0x06054B50, 0, 0, len(files), len(files), len(central), len(body), 0)
    with open(path, "wb") as f:
        f.write(bytes(body) + bytes(central) + end)
    return path


def write_io(ldr_path, out_path, thumbnail=None):
    """A Studio .io from an .ldr file (optionally with a PNG thumbnail)."""
    text = open(ldr_path, errors="ignore").read()
    n = sum(1 for l in text.splitlines() if l.startswith("1 "))
    files = {"model.ldr": text.replace("\r\n", "\n").replace("\n", "\r\n").encode(),
             ".info": json.dumps({"version": "2.2.11_1", "total_parts": n}).encode(),
             "errorPartList.err": b"[]"}
    if thumbnail and os.path.exists(thumbnail):
        files["thumbnail.png"] = open(thumbnail, "rb").read()
    return write_encrypted_zip(out_path, files)


# ----------------------------------------------------------------------------- part lists
# LDraw colour code -> BrickLink colour id, for the colours LEGO uses today. Colours missing
# here are written without a BrickLink colour (the list says so).
BRICKLINK_COLOUR = {
    0: 11, 1: 7, 2: 6, 4: 5, 5: 47, 6: 8, 10: 36, 13: 23, 14: 3, 15: 1, 19: 2, 25: 4, 26: 71,
    27: 34, 28: 69, 29: 104, 30: 157, 31: 154, 70: 88, 71: 86, 72: 85, 73: 42, 84: 150, 85: 89,
    92: 28, 191: 110, 226: 103, 272: 63, 288: 80, 308: 120, 320: 59, 321: 153, 322: 156, 323: 152,
    326: 158, 330: 155, 378: 48, 379: 55, 484: 68,
    33: 14, 34: 20, 36: 17, 40: 13, 43: 15, 46: 19, 47: 12,
}


def counts(ldr_path, skip=("3811", "3867", "4186", "3857", "3645", "6098")):
    """{(part, colour): n} of an .ldr (sub-files flattened), baseplates listed separately."""
    from brickscape.io.analyze_ref import load
    parts, _ = load(ldr_path)
    c = collections.Counter((p, int(col)) for p, col, M in parts)
    base = {k: v for k, v in c.items() if k[0] in skip}
    return {k: v for k, v in c.items() if k[0] not in skip}, base


def parts_list(ldr_path, out_dir, source="lego", include_baseplates=True):
    """Writes parts.csv and bricklink.xml; returns a summary dict."""
    from brickscape.core.brick import info
    from brickscape.plan import colours
    from brickscape import catalog
    names = {v: k.title() for k, v in colours().items()}
    c, base = counts(ldr_path)
    if include_baseplates:
        c = {**c, **base}
    src = catalog.get(source)
    os.makedirs(out_dir, exist_ok=True)
    rows = []
    for (p, col), n in sorted(c.items(), key=lambda kv: (-kv[1], kv[0])):
        try:
            desc = info(p)["desc"]
        except ValueError:
            desc = "?"
        rows.append({"part": p, "description": desc, "colour": names.get(col, str(col)), "ldraw_colour": col,
                     "bricklink_colour": BRICKLINK_COLOUR.get(col, ""), "quantity": n,
                     "price_each_usd": src.price(src.resolve(p) or p) or ""})
    with open(os.path.join(out_dir, "parts.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]) if rows else ["part"])
        w.writeheader()
        w.writerows(rows)
    xml = ["<INVENTORY>"]
    for r in rows:
        xml.append("  <ITEM><ITEMTYPE>P</ITEMTYPE><ITEMID>%s</ITEMID>%s<MINQTY>%d</MINQTY></ITEM>" % (
            escape(r["part"]), f"<COLOR>{r['bricklink_colour']}</COLOR>" if r["bricklink_colour"] != "" else "",
            r["quantity"]))
    xml.append("</INVENTORY>")
    open(os.path.join(out_dir, "bricklink.xml"), "w").write("\n".join(xml) + "\n")
    total = sum(r["quantity"] for r in rows)
    cost = sum(r["quantity"] * r["price_each_usd"] for r in rows if r["price_each_usd"] != "")
    return {"pieces": total, "lots": len(rows), "csv": os.path.join(out_dir, "parts.csv"),
            "bricklink_xml": os.path.join(out_dir, "bricklink.xml"),
            "no_bricklink_colour": sorted({r["colour"] for r in rows if r["bricklink_colour"] == ""}),
            "estimated_cost_usd": round(cost, 2) if source == "gobricks" else None,
            "top": [(r["quantity"], r["part"], r["colour"], r["description"]) for r in rows[:12]]}
