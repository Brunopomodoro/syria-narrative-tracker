#!/usr/bin/env python3
"""The logo, and every file made from it.

The mark is a speech bubble carrying a pulse line: what is being said, and how it moves. It is drawn once here
(BUBBLE and PULSE, on a 64-unit square) and everything else is derived from it:

  assets/logo.svg                 the mark, brass on a transparent background (any size; the favicon)
  assets/logo-mono.svg            the mark in ink, for one-colour print
  assets/logo-wordmark.svg        mark + "Syria Narrative Tracker", the name as outlines (no font needed)
  assets/logo-wordmark-ar.svg     mark + the Arabic name          (-dark.svg versions: the name in paper, for dark backgrounds)
  assets/logo-wordmark.png, -ar   the same, for documents and posts (transparent, 1600 px wide)
  assets/og.png, og-ar.png        the preview card shown when a page is shared (1200 x 630)
  assets/logo-512.png, -192.png   the mark for app icons and the web manifest
  assets/apple-touch-icon.png     the mark on paper, 180 px, for iPhone and iPad home screens
  assets/favicon-32.png, -16.png  small PNG icons;  favicon.ico holds both
  assets/logo-144.png             the mark on paper, for the RSS feeds and the newsletter
  assets/avatar.png               the mark on paper, 1024 px, safe in a circle: profile pictures and the Meta app icon
  assets/cover-facebook.png       the Facebook Page cover (1640 x 624);  cover-x.png: the X header (1500 x 500)
  site.webmanifest                name, colours and icons for browsers

The PNGs are rendered with the Chrome that GitHub's runners and most computers already have (see report_pdf.py);
the outlines need the Python packages fonttools and uharfbuzz (pip install fonttools uharfbuzz) and the site's
fonts, which the script fetches from Google Fonts into a cache folder. Without Chrome or those packages it makes
what it can and says what it skipped.

Usage:  python scripts/brand.py [--fonts DIR] [--only svg|png]
"""
import argparse
import json
import pathlib
import re
import struct
import subprocess
import sys
import tempfile
import urllib.request

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import report_pdf  # noqa: E402  (finds Chrome)

ROOT = pathlib.Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"

BRASS, PAPER, INK, MUTED, FAINT = "#8A6420", "#F7F1E3", "#1A1814", "#45413A", "#6B6559"
NEG, NEU, POS = "#A3303C", "#A7ABA3", "#256454"

# the mark, on a 64 x 64 square: a rounded speech bubble (tail at the lower left) and a pulse line through it
BUBBLE = "M18 6H46A14 14 0 0 1 60 20V36A14 14 0 0 1 46 50H27L13 60L18 50A14 14 0 0 1 4 36V20A14 14 0 0 1 18 6Z"
PULSE = "13 28 22 28 27 19 32 38 37 14 42 34 46 28 51 28"
PULSE_WIDTH = 4.5

NAME, NAME_AR = "Syria Narrative Tracker", "متتبّع السرديات السورية"
HOST = "www.syrianpulse.org"
TAGLINE = ("What is being said about Syria online: public posts in Arabic, Kurdish and English, grouped into stories, "
           "with how people and outlets are reacting. Updated through the day.")
TAGLINE_AR = ("ما يُقال عن سوريا على الإنترنت: منشورات عامة بالعربية والكردية والإنجليزية، مجمّعة في قصص، "
              "مع كيفية تفاعل الناس ووسائل الإعلام معها. يُحدَّث على مدار اليوم.")

FONTS_CSS = ("https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Serif:wght@400;500;600"
             "&family=IBM+Plex+Sans+Arabic:wght@400;500;600&family=Noto+Naskh+Arabic:wght@500;600;700")


def mark_svg(fill: str = BRASS, line: str = PAPER, size: int | None = None, attrs: str = "") -> str:
    """The mark as an SVG element. fill/line may be colours or CSS variables (inline in a page)."""
    dim = f' width="{size}" height="{size}"' if size else ""
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64"{dim}{attrs}>'
            f'<path d="{BUBBLE}" fill="{fill}"/>'
            f'<polyline points="{PULSE}" fill="none" stroke="{line}" stroke-width="{PULSE_WIDTH}" stroke-linecap="round" stroke-linejoin="round"/></svg>')


def inline_mark(cls: str = "mark") -> str:
    """The mark for inline use in the site's pages: colours follow the theme, hidden from screen readers."""
    return mark_svg("var(--brass)", "var(--paper)", attrs=f' class="{cls}" aria-hidden="true" focusable="false"')


# ---------------------------------------------------------------- fonts and outlines

def fetch_fonts(folder: pathlib.Path) -> dict:
    """The site's fonts as TTF files, from Google Fonts, cached in folder. Returns {(family, weight): path}."""
    folder.mkdir(parents=True, exist_ok=True)
    css = folder / "fonts.css"
    if not css.exists():
        req = urllib.request.Request(FONTS_CSS, headers={"User-Agent": "curl/8"})   # a plain agent is served TTF files
        css.write_bytes(urllib.request.urlopen(req, timeout=30).read())
    fonts = {}
    for block in re.findall(r"@font-face\s*{([^}]*)}", css.read_text()):
        fam = re.search(r"font-family:\s*'([^']+)'", block).group(1)
        weight = int(re.search(r"font-weight:\s*(\d+)", block).group(1))
        url = re.search(r"url\((https://[^)]+)\)", block).group(1)
        path = folder / f"{fam.replace(' ', '')}-{weight}.ttf"
        if not path.exists():
            req = urllib.request.Request(url, headers={"User-Agent": "curl/8"})
            path.write_bytes(urllib.request.urlopen(req, timeout=60).read())
        fonts[(fam, weight)] = path
    return fonts


def text_outline(font_path: pathlib.Path, text: str, size: float, x: float, baseline: float, weight: int) -> tuple[str, float]:
    """The text as one SVG path (shaped with HarfBuzz, so Arabic joins correctly), and its advance width."""
    import uharfbuzz as hb
    from fontTools.pens.svgPathPen import SVGPathPen
    from fontTools.pens.transformPen import TransformPen
    from fontTools.ttLib import TTFont
    tt = TTFont(font_path)
    if "fvar" in tt:
        from fontTools.varLib import instancer
        tt = instancer.instantiateVariableFont(tt, {"wght": weight})
    face = hb.Face(font_path.read_bytes())
    font = hb.Font(face)
    if "fvar" in TTFont(font_path):
        font.set_variations({"wght": weight})
    buf = hb.Buffer()
    buf.add_str(text)
    buf.guess_segment_properties()
    hb.shape(font, buf, {"kern": True, "liga": True, "calt": True})
    glyphs, order = tt.getGlyphSet(), tt.getGlyphOrder()
    upem = tt["head"].unitsPerEm
    s = size / upem
    pen_x, parts = x, []
    for info, pos in zip(buf.glyph_infos, buf.glyph_positions):     # HarfBuzz returns glyphs in visual order
        pen = SVGPathPen(glyphs)
        glyphs[order[info.codepoint]].draw(TransformPen(pen, (s, 0, 0, -s, pen_x + pos.x_offset * s, baseline - pos.y_offset * s)))
        d = pen.getCommands()
        if d:
            parts.append(d)
        pen_x += pos.x_advance * s
    return " ".join(parts), pen_x - x


def wordmark_svg(fonts: dict, lang: str, text: str = INK) -> str:
    """The mark with the name beside it, as outlines. Arabic: the mark on the right, the name to its left.
    text is the name's colour: ink for light backgrounds, paper for dark ones."""
    if lang == "ar":
        d, width = text_outline(fonts[("Noto Naskh Arabic", 600)], NAME_AR, 36, 0, 37, 600)
        total = round(width + 20 + 64)
        name = f'<path d="{d}" fill="{text}"/>'
        mark = f'<g transform="translate({total - 64} 0)"><path d="{BUBBLE}" fill="{BRASS}"/><polyline points="{PULSE}" fill="none" stroke="{PAPER}" stroke-width="{PULSE_WIDTH}" stroke-linecap="round" stroke-linejoin="round"/></g>'
        return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {total} 64" width="{total}" height="64" role="img" aria-label="{NAME_AR}">'
                f'<title>{NAME_AR}</title>{mark}{name}</svg>')
    d, width = text_outline(fonts[("IBM Plex Serif", 600)], NAME, 33, 80, 40, 600)
    total = round(80 + width + 2)
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {total} 64" width="{total}" height="64" role="img" aria-label="{NAME}">'
            f'<title>{NAME}</title><path d="{BUBBLE}" fill="{BRASS}"/><polyline points="{PULSE}" fill="none" stroke="{PAPER}" stroke-width="{PULSE_WIDTH}" stroke-linecap="round" stroke-linejoin="round"/>'
            f'<path d="{d}" fill="{text}"/></svg>')


# ---------------------------------------------------------------- PNGs, with Chrome

def font_faces(fonts: dict) -> str:
    return "".join(f'@font-face{{font-family:"{fam}";font-weight:{w};src:url("{p.resolve().as_uri()}") format("truetype")}}'
                   for (fam, w), p in fonts.items())


def html_page(body: str, width: int, height: int, fonts: dict, background: str = "transparent", extra_css: str = "") -> str:
    return (f'<!doctype html><html><head><meta charset="utf-8"><style>{font_faces(fonts)}'
            f'html,body{{margin:0;padding:0}}body{{width:{width}px;height:{height}px;overflow:hidden;background:{background};position:relative}}'
            f'{extra_css}</style></head><body>{body}</body></html>')


def render_png(binary: str, html: str, out: pathlib.Path, width: int, height: int) -> bool:
    """Render the page's top-left width x height pixels to out. Chrome is given a larger window (its window has a
    minimum size, and the new headless mode's screenshot loses a band to the toolbar), and the image is cropped."""
    with tempfile.TemporaryDirectory() as tmp:
        page, shot = pathlib.Path(tmp) / "page.html", pathlib.Path(tmp) / "shot.png"
        page.write_text(html, encoding="utf-8")
        cmd = [binary, "--headless=new", "--disable-gpu", "--no-sandbox", "--hide-scrollbars", "--default-background-color=00000000",
               "--force-device-scale-factor=1", f"--window-size={max(width, 400) + 200},{max(height, 400) + 200}",
               "--run-all-compositor-stages-before-draw", "--virtual-time-budget=5000", f"--screenshot={shot}", page.resolve().as_uri()]
        subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if not shot.exists():
            return False
        w, h, rgba = png_read(shot)
        if w < width or h < height:
            return False
        png_write(out, width, height, png_crop(w, h, rgba, width, height))
    return out.exists() and out.stat().st_size > 100


def icon_html(size: int, fonts: dict, background: str = "transparent", inset: float = 0.0) -> str:
    inner = round(size * (1 - 2 * inset))
    pad = round(size * inset)
    return html_page(f'<div style="position:absolute;left:{pad}px;top:{pad}px">{mark_svg(size=inner)}</div>', size, size, fonts, background)


def og_html(lang: str, fonts: dict) -> str:
    ar = lang == "ar"
    title_font = "'Noto Naskh Arabic'" if ar else "'IBM Plex Serif'"
    text_font = "'IBM Plex Sans Arabic'" if ar else "'IBM Plex Sans'"
    name = NAME_AR if ar else NAME
    tagline = TAGLINE_AR if ar else TAGLINE
    neg, pos = ("سلبي", "إيجابي") if ar else ("Negative", "Positive")
    side = "right" if ar else "left"
    body = f'''<div dir="{'rtl' if ar else 'ltr'}" lang="{lang}" style="position:absolute;inset:0;font-family:{text_font},sans-serif;color:{INK}">
<div style="position:absolute;{side}:80px;top:78px;display:flex;align-items:center;gap:26px">{mark_svg(size=96)}
<div style="font-family:{title_font},serif;font-weight:600;font-size:{'60' if ar else '58'}px;line-height:1.1;letter-spacing:{'0' if ar else '-.5px'}">{name}</div></div>
<p style="position:absolute;{side}:80px;top:{'232' if ar else '240'}px;margin:0;width:980px;font-size:{'31' if ar else '30'}px;line-height:1.5;color:{MUTED}">{tagline}</p>
<div style="position:absolute;left:80px;right:80px;bottom:112px;height:14px;border-radius:7px;background:linear-gradient(90deg,{POS if ar else NEG},{NEU} 50%,{NEG if ar else POS})"></div>
<div style="position:absolute;left:80px;bottom:68px;font-size:22px;color:{FAINT}">{neg if not ar else pos}</div>
<div style="position:absolute;right:80px;bottom:68px;font-size:22px;color:{FAINT}">{pos if not ar else neg}</div>
<div style="position:absolute;{'left' if ar else 'right'}:80px;top:104px;font-size:26px;font-family:'IBM Plex Sans',sans-serif;color:{BRASS}" dir="ltr">syrianpulse.org</div>
</div>'''
    return html_page(body, 1200, 630, fonts, PAPER)


def cover_html(fonts: dict, width: int = 1640, height: int = 624) -> str:
    """A profile cover (Facebook 1640 x 624, X 1500 x 500): the mark and both names, centred so the phone crop
    and the profile picture leave them whole."""
    body = f'''<div style="position:absolute;inset:0;display:flex;flex-direction:column;align-items:center;justify-content:center;padding-bottom:70px;color:{INK}">
<div style="display:flex;align-items:center;gap:40px">{mark_svg(size=150)}
<div style="display:flex;flex-direction:column;gap:6px">
<div dir="rtl" style="font-family:'Noto Naskh Arabic',serif;font-weight:600;font-size:76px;line-height:1.15">{NAME_AR}</div>
<div style="font-family:'IBM Plex Serif',serif;font-weight:600;font-size:58px;line-height:1.1;letter-spacing:-.5px">{NAME}</div></div></div>
<div style="margin-top:34px;font-family:'IBM Plex Sans Arabic','IBM Plex Sans',sans-serif;font-size:30px;color:{MUTED}"><span dir="rtl">ما يُقال عن سوريا على الإنترنت</span> · What is being said about Syria online</div>
<div style="margin-top:30px;width:760px;height:12px;border-radius:6px;background:linear-gradient(90deg,{NEG},{NEU} 50%,{POS})"></div>
<div style="margin-top:16px;font-family:'IBM Plex Sans',sans-serif;font-size:26px;color:{BRASS}">syrianpulse.org</div></div>'''
    return html_page(body, width, height, fonts, PAPER)


def wordmark_png_html(svg: str, fonts: dict, width: int) -> tuple[str, int]:
    vb = re.search(r'viewBox="0 0 (\d+) 64"', svg).group(1)
    height = round(width * 64 / int(vb))
    body = svg.replace(f'width="{vb}" height="64"', f'width="{width}" height="{height}"')
    return html_page(f'<div style="position:absolute;left:0;top:0">{body}</div>', width, height, fonts), height


def png_read(path: pathlib.Path) -> tuple:
    """A PNG as (width, height, RGBA bytes). Handles Chrome's output: 8-bit RGB or RGBA, not interlaced."""
    import zlib
    data = path.read_bytes()
    assert data[:8] == b"\x89PNG\r\n\x1a\n", "not a PNG"
    pos, chunks, w = 8, [], None
    while pos < len(data):
        n = struct.unpack(">I", data[pos:pos + 4])[0]
        kind, body = data[pos + 4:pos + 8], data[pos + 8:pos + 8 + n]
        if kind == b"IHDR":
            w, h, depth, ctype, _, _, interlace = struct.unpack(">IIBBBBB", body)
            assert depth == 8 and ctype in (2, 6) and interlace == 0, "unexpected PNG format"
        elif kind == b"IDAT":
            chunks.append(body)
        pos += 12 + n
    bpp = 4 if ctype == 6 else 3
    raw, stride = zlib.decompress(b"".join(chunks)), w * bpp
    out, prev = bytearray(), bytearray(stride)
    for y in range(h):
        f = raw[y * (stride + 1)]
        line = bytearray(raw[y * (stride + 1) + 1:(y + 1) * (stride + 1)])
        for i in range(stride):
            a = line[i - bpp] if i >= bpp else 0
            b = prev[i]
            c = prev[i - bpp] if i >= bpp else 0
            if f == 1:
                line[i] = (line[i] + a) & 255
            elif f == 2:
                line[i] = (line[i] + b) & 255
            elif f == 3:
                line[i] = (line[i] + (a + b) // 2) & 255
            elif f == 4:
                pa, pb, pc = abs(b - c), abs(a - c), abs(a + b - 2 * c)
                line[i] = (line[i] + (a if pa <= pb and pa <= pc else b if pb <= pc else c)) & 255
        if bpp == 3:
            px = bytearray()
            for i in range(0, stride, 3):
                px += line[i:i + 3] + b"\xff"
            out += px
        else:
            out += line
        prev = line
    return w, h, bytes(out)


def png_write(path: pathlib.Path, w: int, h: int, rgba: bytes) -> None:
    import zlib
    def chunk(kind, body):
        return struct.pack(">I", len(body)) + kind + body + struct.pack(">I", zlib.crc32(kind + body) & 0xFFFFFFFF)
    rows = b"".join(b"\x00" + rgba[y * w * 4:(y + 1) * w * 4] for y in range(h))
    path.write_bytes(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0))
                     + chunk(b"IDAT", zlib.compress(rows, 9)) + chunk(b"IEND", b""))


def png_crop(w: int, h: int, rgba: bytes, cw: int, ch: int) -> bytes:
    return b"".join(rgba[y * w * 4:(y * w + cw) * 4] for y in range(ch))


def png_shrink(w: int, h: int, rgba: bytes, f: int) -> tuple:
    """Box-filter the image down by the whole-number factor f (premultiplied, so edges stay clean)."""
    ow, oh, out = w // f, h // f, bytearray()
    for oy in range(oh):
        for ox in range(ow):
            r = g = b = a = 0
            for y in range(oy * f, oy * f + f):
                base = (y * w + ox * f) * 4
                for x in range(f):
                    i = base + x * 4
                    al = rgba[i + 3]
                    r += rgba[i] * al
                    g += rgba[i + 1] * al
                    b += rgba[i + 2] * al
                    a += al
            if a:
                out += bytes((round(r / a), round(g / a), round(b / a), round(a / (f * f))))
            else:
                out += b"\x00\x00\x00\x00"
    return ow, oh, bytes(out)


def write_ico(pngs: list, out: pathlib.Path) -> None:
    """An .ico holding PNG images (every browser since 2010 reads those)."""
    head = struct.pack("<HHH", 0, 1, len(pngs))
    entries, data, offset = b"", b"", 6 + 16 * len(pngs)
    for size, png in pngs:
        entries += struct.pack("<BBBBHHII", size % 256, size % 256, 0, 0, 1, 32, len(png), offset)
        data += png
        offset += len(png)
    out.write_bytes(head + entries + data)


# ---------------------------------------------------------------- main

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fonts", default=str(pathlib.Path(tempfile.gettempdir()) / "syria-tracker-fonts"), help="where the fonts are cached")
    ap.add_argument("--only", choices=["svg", "png"], help="make only the SVG files, or only the PNGs")
    args = ap.parse_args()
    ASSETS.mkdir(exist_ok=True)
    skipped = []

    (ASSETS / "logo.svg").write_text(mark_svg() + "\n")
    (ASSETS / "logo-mono.svg").write_text(mark_svg(INK, "#FFFFFF") + "\n")
    print("ok   assets/logo.svg, assets/logo-mono.svg")
    (ROOT / "site.webmanifest").write_text(json.dumps({
        "name": NAME, "short_name": "Syria Tracker", "description": TAGLINE, "start_url": "/", "display": "browser",
        "background_color": PAPER, "theme_color": BRASS,
        "icons": [{"src": "assets/logo-192.png", "sizes": "192x192", "type": "image/png"}, {"src": "assets/logo-512.png", "sizes": "512x512", "type": "image/png"},
                  {"src": "assets/logo.svg", "sizes": "any", "type": "image/svg+xml"}]}, ensure_ascii=False, indent=1) + "\n")
    print("ok   site.webmanifest")

    try:
        fonts = fetch_fonts(pathlib.Path(args.fonts))
    except Exception as e:   # noqa: BLE001
        print(f"Fonts could not be fetched ({e}); the wordmarks and preview cards are not remade.")
        return 0

    wordmarks = {}
    if args.only != "png":
        try:
            for lang in ("en", "ar"):
                wordmarks[lang] = wordmark_svg(fonts, lang)
                (ASSETS / ("logo-wordmark-ar.svg" if lang == "ar" else "logo-wordmark.svg")).write_text(wordmarks[lang] + "\n", encoding="utf-8")
                (ASSETS / ("logo-wordmark-ar-dark.svg" if lang == "ar" else "logo-wordmark-dark.svg")).write_text(wordmark_svg(fonts, lang, PAPER) + "\n", encoding="utf-8")
            print("ok   assets/logo-wordmark.svg, assets/logo-wordmark-ar.svg (and the -dark ones, for dark backgrounds)")
        except ImportError as e:
            skipped.append(f"wordmark SVGs (pip install fonttools uharfbuzz: {e})")
    if args.only == "svg":
        return 0

    binary = report_pdf.chrome()
    if not binary:
        print("No Chrome or Chromium found; the PNGs are not remade.")
        return 0
    jobs = [("og.png", og_html("en", fonts), 1200, 630), ("og-ar.png", og_html("ar", fonts), 1200, 630),
            ("logo-512.png", icon_html(512, fonts), 512, 512), ("logo-192.png", icon_html(192, fonts), 192, 192),
            ("apple-touch-icon.png", icon_html(180, fonts, PAPER, 0.11), 180, 180), ("logo-144.png", icon_html(144, fonts, PAPER, 0.1), 144, 144),
            ("avatar.png", icon_html(1024, fonts, PAPER, 0.17), 1024, 1024), ("cover-facebook.png", cover_html(fonts), 1640, 624),
            ("cover-x.png", cover_html(fonts, 1500, 500), 1500, 500)]
    for lang, svg in wordmarks.items() or [(l, (ASSETS / ("logo-wordmark-ar.svg" if l == "ar" else "logo-wordmark.svg")).read_text(encoding="utf-8"))
                                           for l in ("en", "ar") if (ASSETS / ("logo-wordmark-ar.svg" if l == "ar" else "logo-wordmark.svg")).exists()]:
        html, h = wordmark_png_html(svg, fonts, 1600)
        jobs.append((f"logo-wordmark{'-ar' if lang == 'ar' else ''}.png", html, 1600, h))
    for name, html, w, h in jobs:
        ok = render_png(binary, html, ASSETS / name, w, h)
        print(f"{'ok  ' if ok else 'FAIL'} assets/{name}")
        if not ok:
            skipped.append(name)
    if (ASSETS / "logo-512.png").exists():
        w, h, rgba = png_read(ASSETS / "logo-512.png")
        for size in (32, 16):
            png_write(ASSETS / f"favicon-{size}.png", *png_shrink(w, h, rgba, 512 // size))
        print("ok   assets/favicon-32.png, assets/favicon-16.png (from the 512 one)")
        write_ico([(16, (ASSETS / "favicon-16.png").read_bytes()), (32, (ASSETS / "favicon-32.png").read_bytes())], ROOT / "favicon.ico")
        print("ok   favicon.ico")
    if skipped:
        print("Skipped: " + ", ".join(skipped))
    return 0


if __name__ == "__main__":
    sys.exit(main())
