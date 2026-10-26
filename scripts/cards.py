#!/usr/bin/env python3
"""Image cards for the X posts: 1200 x 675 PNGs in the site's colours, drawn with the same Chrome that makes the
PDFs. A card carries a label and date, the headline, how people and the media feel (a meter from negative to positive,
with the tone in words, never a score), one line of context (comments, or the most discussed themes) and the account.
Posts with an image reach more people on X than text alone.

  spec = {"eyebrow", "title", "people": tone or None, "media": tone or None, "line"}
  render(cfg, spec, lang, out)   -> True when the PNG was made
  python scripts/cards.py [dir]  -> sample cards of the latest story, day and week, to look at (default .cards-sample/)
"""
import html
import pathlib
import struct
import subprocess
import sys
import tempfile
import zlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import brand  # noqa: E402
import pages  # noqa: E402
import report_pdf  # noqa: E402

WORDS = {"en": {"people": "People", "media": "Media", "neg": "Negative", "pos": "Positive"},
         "ar": {"people": "الناس", "media": "وسائل الإعلام", "neg": "سلبي", "pos": "إيجابي"}}

CSS = """*{box-sizing:border-box}html,body{margin:0;width:1200px;height:675px}
body{background:#F7F1E3;color:#1A1814;font-family:"IBM Plex Sans","IBM Plex Sans Arabic",sans-serif}
.card{width:1200px;height:675px;padding:44px 64px 40px;display:flex;flex-direction:column;border-top:16px solid #8A6420}
.brand{display:flex;align-items:center;gap:14px;font-weight:600;font-size:27px}.brand svg{width:46px;height:46px}
.eyebrow{margin-top:30px;font-size:25px;font-weight:600;color:#8A6420}
h1{font-family:"IBM Plex Serif","Noto Naskh Arabic",serif;font-weight:600;font-size:54px;line-height:1.2;margin:12px 0 0;
   display:-webkit-box;-webkit-line-clamp:3;-webkit-box-orient:vertical;overflow:hidden}
[dir=rtl] h1{font-size:52px;line-height:1.45}
.meters{margin-top:auto;display:grid;gap:16px}
.m{display:grid;grid-template-columns:210px 1fr 300px;align-items:center;gap:22px;font-size:25px}
.m .who{font-weight:600}.m .word{font-weight:600}
.scale{position:relative}.track{height:14px;border-radius:7px;background:linear-gradient(90deg,#A3303C,#A7ABA3 50%,#256454)}
[dir=rtl] .track{background:linear-gradient(270deg,#A3303C,#A7ABA3 50%,#256454)}
.dot{position:absolute;top:7px;width:32px;height:32px;margin:-16px;border-radius:50%;background:#fff;border:6px solid #1A1814}
.ends{display:flex;justify-content:space-between;font-size:16px;color:#6B6559;margin-top:6px}
.foot{display:flex;justify-content:space-between;gap:24px;margin-top:26px;padding-top:16px;border-top:2px solid #E2D9C5;font-size:22px;color:#45413A}
.foot .acc{direction:ltr;white-space:nowrap;font-weight:600;color:#8A6420}"""


def meter(label: str, v, lang: str) -> str:
    w = WORDS[lang]
    if v is None:
        return ""
    v = max(-1.0, min(1.0, float(v)))
    side = "right" if lang == "ar" else "left"                   # negative sits where reading starts
    return (f'<div class="m"><span class="who">{html.escape(label)}</span><div class="scale"><div class="track"></div>'
            f'<span class="dot" style="{side}:{(v + 1) * 50:.1f}%"></span><div class="ends"><span>{w["neg"]}</span><span>{w["pos"]}</span></div></div>'
            f'<span class="word">{html.escape(pages.tone_label(v, lang))}</span></div>')


def card_html(cfg: dict, spec: dict, lang: str) -> str:
    w = WORDS[lang]
    handle = pages.x_profile(cfg).rsplit("/", 1)[-1]
    domain = pages.site_url(cfg).replace("https://", "").replace("www.", "")
    account = spec.get("account") or ((f"@{handle} · " if handle else "") + domain)   # Facebook cards show the site only
    rows = meter(w["people"], spec.get("people"), lang) + meter(w["media"], spec.get("media"), lang)
    return (f'<!doctype html><html lang="{lang}" dir="{"rtl" if lang == "ar" else "ltr"}"><head><meta charset="utf-8">{pages.FONTS}<style>{CSS}</style></head>'
            f'<body><div class="card"><div class="brand">{brand.mark_svg("#8A6420", "#F7F1E3")}<span>{html.escape(pages.site_title(cfg, lang))}</span></div>'
            f'<div class="eyebrow">{html.escape(spec.get("eyebrow") or "")}</div><h1>{html.escape(spec.get("title") or "")}</h1>'
            f'<div class="meters">{rows}</div>'
            f'<div class="foot"><span>{html.escape(spec.get("line") or "")}</span><span class="acc">{html.escape(account)}</span></div></div></body></html>')


def crop_png(path: pathlib.Path, height: int) -> bool:
    """Keep the top `height` rows of an 8-bit, non-interlaced RGB or RGBA PNG (what Chrome writes). Chrome's headless
    window draws a shorter area than the screenshot it saves, so the card is drawn in a taller window and cut here."""
    data = path.read_bytes()
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        return False
    pos, chunks = 8, []
    while pos < len(data):
        n, kind = struct.unpack(">I4s", data[pos:pos + 8])
        chunks.append((kind, data[pos + 8:pos + 8 + n]))
        pos += 12 + n
    w, h, depth, ctype, _, _, interlace = struct.unpack(">IIBBBBB", chunks[0][1])
    if depth != 8 or ctype not in (2, 6) or interlace or h < height:
        return False
    bpp = 3 if ctype == 2 else 4
    raw, stride = zlib.decompress(b"".join(c for k, c in chunks if k == b"IDAT")), w * bpp
    rows, prev = [], bytearray(stride)
    for y in range(height):                                  # undo the row filters
        f, line = raw[y * (stride + 1)], bytearray(raw[y * (stride + 1) + 1:(y + 1) * (stride + 1)])
        for i in range(stride):
            a = line[i - bpp] if i >= bpp else 0
            b, c = prev[i], prev[i - bpp] if i >= bpp else 0
            if f == 1:
                line[i] = (line[i] + a) & 255
            elif f == 2:
                line[i] = (line[i] + b) & 255
            elif f == 3:
                line[i] = (line[i] + (a + b) // 2) & 255
            elif f == 4:
                pa, pb, pc = abs(b - c), abs(a - c), abs(a + b - 2 * c)
                line[i] = (line[i] + (a if pa <= pb and pa <= pc else b if pb <= pc else c)) & 255
        rows.append(b"\x00" + bytes(line))
        prev = line
    def chunk(kind: bytes, body: bytes) -> bytes:
        return struct.pack(">I", len(body)) + kind + body + struct.pack(">I", zlib.crc32(kind + body) & 0xFFFFFFFF)
    path.write_bytes(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, height, 8, ctype, 0, 0, 0))
                     + chunk(b"IDAT", zlib.compress(b"".join(rows), 9)) + chunk(b"IEND", b""))
    return True


def render(cfg: dict, spec: dict, lang: str, out: pathlib.Path) -> bool:
    binary = report_pdf.chrome()
    if not binary or not spec.get("title"):
        return False
    with tempfile.TemporaryDirectory() as tmp:
        page = pathlib.Path(tmp) / "card.html"
        page.write_text(card_html(cfg, spec, lang), encoding="utf-8")
        cmd = [binary, "--headless=new", "--disable-gpu", "--no-sandbox", "--hide-scrollbars", "--force-device-scale-factor=1",
               "--window-size=1200,875", "--virtual-time-budget=8000", f"--screenshot={out}", page.as_uri()]
        try:
            subprocess.run(cmd, capture_output=True, text=True, timeout=90)
        except subprocess.TimeoutExpired:
            return False
    return out.exists() and crop_png(out, 675) and out.stat().st_size > 5000


if __name__ == "__main__":
    import social
    import pipeline as P
    cfg = P.load_config()
    out = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else pages.ROOT / ".cards-sample"   # not saved in the repository
    out.mkdir(exist_ok=True)
    state = social.load_state()
    import datetime as dt
    now = dt.datetime.now(dt.timezone.utc)
    samples = []
    for n, gap in social.story_candidates(cfg, state, now)[:1]:
        samples.append(("story", social.story_card(cfg, n, "ar")))
    yesterday = (now.date() - dt.timedelta(days=1)).isoformat()
    for kind, ident in (("daily", yesterday), ("weekly", (social.latest("weekly") or {}).get("week"))):
        for lang in ("ar", "en"):
            p = social.compose_x(cfg, kind, ident, lang) if ident else None
            if p and p.get("card"):
                samples.append((f"{kind}-{lang}", p["card"]))
    for name, spec in samples:
        lang = "en" if name.endswith("-en") else "ar"
        print(name, render(cfg, spec, lang, out / f"{name}.png"))
