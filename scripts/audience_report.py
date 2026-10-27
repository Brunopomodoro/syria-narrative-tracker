#!/usr/bin/env python3
"""The audience snapshot report (English): audience/en.html and an A4 PDF, audience/en.pdf, from data/audience.json
(scripts/audience.py). Written for media-development partners and funders: the findings in plain words, the tables
behind them, and the method and its limits. Not linked from the site's menus; share the link or the PDF.

Usage:  python scripts/audience_report.py   (or python scripts/audience.py --report)
"""
import json
import pathlib
import subprocess
import sys
import tempfile

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import pages  # noqa: E402

E = pages.esc
PLATFORMS = {"youtube": "YouTube comments (video)", "telegram": "Telegram channels", "bluesky": "Bluesky", "news": "News sites",
             "x": "X", "reddit": "Reddit", "facebook": "Facebook", "instagram": "Instagram", "threads": "Threads"}
LANGS = {"ar": "Arabic", "en": "English", "ku": "Kurdish"}
CSS = """<style>
.aud{max-width:860px;--bw:160px}.aud h2{margin-top:34px;border-bottom:2px solid var(--brass);padding-bottom:4px}.aud .lead{font-size:1.08rem}
.aud .finds{counter-reset:f;list-style:none;padding:0}.aud .finds li{counter-increment:f;position:relative;padding:10px 0 10px 40px;border-bottom:1px solid var(--rule)}
.aud .finds li::before{content:counter(f);position:absolute;left:0;top:10px;width:26px;height:26px;border-radius:50%;background:var(--brass);color:#fff;font-weight:600;text-align:center;line-height:26px;font-size:.85rem}
.aud table{width:100%;border-collapse:collapse;font-size:.92rem;margin:10px 0}.aud th,.aud td{text-align:left;padding:7px 8px;border-bottom:1px solid var(--rule);vertical-align:top}
.aud th{font-size:.8rem;text-transform:uppercase;letter-spacing:.03em;color:var(--muted)}.aud td.n{white-space:nowrap}
.aud .bar{display:flex;align-items:center;gap:8px}.aud .bar span.b{display:inline-block;height:10px;border-radius:5px;background:var(--brass)}
.aud .bar span.o{background:var(--neu)}.aud .pair{display:grid;gap:3px}.aud .legend{font-size:.85rem;color:var(--muted)}
.aud .legend i{display:inline-block;width:10px;height:10px;border-radius:5px;margin:0 4px 0 10px;vertical-align:0}
.aud .note{font-size:.88rem;color:var(--muted)}.aud .kpis{grid-template-columns:repeat(4,1fr)}
@media (max-width:600px){.aud{--bw:64px}.aud table{display:block;overflow-x:auto;font-size:.85rem}.aud th,.aud td{padding:6px 5px}}
@media print{.aud h2,.aud h2+p,.aud .legend{break-after:avoid}.aud tr,.aud .finds li{break-inside:avoid}.aud table{font-size:8.5pt}.aud .finds li{padding:5pt 0 5pt 24pt}.aud .finds li::before{width:15pt;height:15pt;line-height:15pt;font-size:7.5pt}}
</style>"""


def pct(v) -> str:
    return f"{round((v or 0) * 100)}%"


def tone(v) -> str:
    return pages.tone_label(v, "en") if v is not None else "–"


def theme(cfg, t) -> str:
    return pages.theme_label(cfg, t, "en")


def low(name: str) -> str:
    """A topic or outlet name inside a sentence: lower the first letter unless it starts with a proper noun."""
    return name if name.split(" ")[0] in PROPER else name[:1].lower() + name[1:]


PROPER = {"Israel", "Suwayda", "Kurdish", "Arab", "Arabic", "English"}


def tn(cfg, t, first=False) -> str:
    """A topic named in a finding, in italics so lists of topics with "and" in their names stay readable."""
    name = theme(cfg, t)
    return f"<em>{E(name if first else low(name))}</em>"


def gap_words(v: float) -> str:
    n = round(v * 100)
    return "same share" if n == 0 else f"{'+' if n > 0 else '−'}{abs(n)} point{'s' if abs(n) != 1 else ''}"


def bar(v, top, cls="b") -> str:
    f = max(0.0125, (v or 0) / (top or 1))
    return f'<span class="b {cls}" style="width:calc(var(--bw) * {f:.3f})"></span>'


def findings(cfg: dict, d: dict) -> list:
    out = []
    al = d["alignment"]
    if al:
        best = max(al.values(), key=lambda x: x["agree"])
        worst = min(al.values(), key=lambda x: x["agree"])
        out.append(f"<b>{E(best['label'])} are closest to the public mood.</b> On the stories they covered, people's mood went the same way as "
                   f"their tone (negative, neutral or positive) {pct(best['agree'])} of the time, against {pct(worst['agree'])} for "
                   f"{E(low(worst['label']))}. This is a proxy for whose framing audiences share, not a direct measure of trust.")
        angr = [x["angrier"] for x in al.values()]
        out.append(f"<b>People are angrier than every type of outlet.</b> Across all outlet types, people's reactions were clearly more negative "
                   f"than the coverage on {pct(min(angr))} to {pct(max(angr))} of the stories; outlets' tone was on average "
                   f"{tone(sum(x['outlets'] for x in al.values()) / len(al)).lower()}, people's {tone(sum(x['people'] for x in al.values()) / len(al)).lower()}.")
    db = d["doubt"]
    top = sorted(db["by_theme"].items(), key=lambda x: -x[1])[:3]
    out.append(f"<b>Doubt is widespread.</b> About {pct(db['share'])} of people's attention went to stories where they voiced doubt about "
               f"official accounts, promises or media reports, most of all on {', '.join(f'{tn(cfg, t)} ({pct(v)})' for t, v in top)}.")
    g = sorted(d["gaps"].items(), key=lambda x: -x[1]["gap"])
    more, less = [x for x in g if x[1]["gap"] > 0.02][:3], [x for x in g[::-1] if x[1]["gap"] < -0.02][:2]
    if more:
        out.append(f"<b>Coverage gaps.</b> People talk more than outlets cover about {', '.join(tn(cfg, t) for t, _ in more)}"
                   + (f", while outlets give more room than people's attention to {' and '.join(tn(cfg, t) for t, _ in less)}." if less else "."))
    tired_topics = [t for t, v in d["topic_trend"].items() if v["fatigue"]]
    weeks = [w for w in d["weeks"] if not w.get("partial")]
    if tired_topics or weeks:
        lo, hi = (min(w["tired"] for w in weeks), max(w["tired"] for w in weeks)) if weeks else (0, 0)
        out.append("<b>Signs of fatigue.</b> " + (f"{' and '.join(tn(cfg, t, i == 0) for i, t in enumerate(tired_topics))} lost a large part of people's attention "
                   "in the second half of the period while outlets kept covering them. " if tired_topics else "")
                   + f"Tiredness, resignation or numbness marked {pct(lo)} to {pct(hi)} of people's attention from week to week.")
    vid = d["platforms"].get("youtube", 0)
    vtop = sorted(d["video_share"].items(), key=lambda x: -x[1])[:2]
    out.append(f"<b>Video is where people react.</b> YouTube comments make up {pct(vid)} of the conversation analysed; reactions to "
               f"{' and '.join(tn(cfg, t) for t, _ in vtop)} happen mostly under videos ({' and '.join(pct(v) for _, v in vtop)}).")
    la = d["languages"]
    if "ar" in la and "en" in la:
        out.append(f"<b>Arabic and English audiences differ.</b> Arabic reactions are {tone(la['ar']['tone']).lower()} overall and centre on "
                   f"{tn(cfg, next(iter(la['ar']['topics'])))}; English reactions are {tone(la['en']['tone']).lower()} and centre on "
                   f"{tn(cfg, next(iter(la['en']['topics'])))}" + (", and Kurdish reactions almost entirely on the north-east." if "ku" in la else "."))
    emo = list(d["emotions"].items())[:4]
    em = d["emotions"]
    out.append(f"<b>{E(emo[0][0].capitalize())} leads.</b> The emotions most present in reactions are {', '.join(f'{E(k)} ({pct(v)})' for k, v in emo)}; "
               f"hope appears in {pct(em.get('hope', 0))} of them and pride in {pct(em.get('pride', 0))}.")
    return out


def body(cfg: dict, d: dict) -> str:
    base = pages.site_url(cfg)
    h = [CSS, '<article class="report aud">',
         '<p class="eyebrow">Syria Narrative Tracker · Audience snapshot</p>',
         '<h1>What Syrian online audiences talk about, how they react, and how far they are from the media</h1>',
         f'<p class="sub">{E(pages.fmt_date(d["from"], "en"))} – {E(pages.fmt_date(d["to"], "en"))} · {d["days"]} days · '
         f'{d["stories"]} stories · {d["public_posts"]:,} analyses of posts and comments by people and {d["outlet_posts"]:,} by outlets</p>',
         '<p class="lead">The Syria Narrative Tracker reads public posts and comments about Syria in Arabic, Kurdish and English several times a day '
         '(YouTube comments, Telegram channels, Bluesky, Reddit, X and news sites), groups them into stories and measures, story by story, '
         'the mood of ordinary people and the tone of each type of outlet. This snapshot draws audience indicators from that record. It describes what '
         'audiences say and do in public online; it does not represent all Syrians (see Method and limits).</p>',
         '<h2>Key findings</h2><ol class="finds">' + "".join(f"<li>{x}</li>" for x in findings(cfg, d)) + "</ol>"]

    al = d["alignment"]
    if al:
        rows = "".join(f"<tr><td>{E(v['label'])}</td><td class=\"n\">{v['stories']}</td><td>{E(tone(v['outlets']))}</td><td>{E(tone(v['people']))}</td>"
                       f"<td class=\"n\"><div class=\"bar\">{bar(v['agree'], 1)}{pct(v['agree'])}</div></td><td class=\"n\">{pct(v['angrier'])}</td></tr>"
                       for v in sorted(al.values(), key=lambda x: -x["agree"]))
        h.append('<h2>1. Outlets and the public mood</h2><p>For each type of outlet, on the stories it covered: its tone, people\'s mood on the same stories, '
                 'how often the two went the same way, and how often people were clearly more negative. Closeness suggests which outlets\' framing '
                 'audiences share; it is a proxy, and the survey\'s direct questions on trust are needed to explain why.</p>'
                 f'<table><thead><tr><th>Outlet type</th><th>Stories</th><th>Outlets\' tone</th><th>People\'s mood</th><th>Same direction</th><th>People more negative</th></tr></thead><tbody>{rows}</tbody></table>')

    db = d["doubt"]
    items = sorted(db["by_theme"].items(), key=lambda x: -x[1])
    h.append(f'<h2>2. Doubt about official accounts and media reports</h2><p>Share of people\'s attention, by topic, on stories where people voiced doubt, '
             f'suspicion or mockery about official accounts, promises or media reports (overall: {pct(db["share"])}).</p><table><tbody>'
             + "".join(f"<tr><td>{E(theme(cfg, t))}</td><td class=\"n\"><div class=\"bar\">{bar(v, 1)}{pct(v)}</div></td></tr>" for t, v in items) + "</tbody></table>")

    g = sorted(d["gaps"].items(), key=lambda x: -x[1]["gap"])
    topv = max(max(v["people"], v["outlets"]) for _, v in g)
    h.append('<h2>3. Gaps between coverage and attention</h2><p>Each topic\'s share of people\'s posts and comments against its share of outlets\' coverage '
             'over the period. Topics at the top get more attention from people than from outlets.</p><p class="legend"><i style="background:var(--brass)"></i>People '
             '<i style="background:var(--neu)"></i>Outlets</p><table><thead><tr><th>Topic</th><th>People / outlets</th><th>Difference</th></tr></thead><tbody>'
             + "".join(f"<tr><td>{E(theme(cfg, t))}</td><td><div class=\"pair\"><div class=\"bar\">{bar(v['people'], topv)}{pct(v['people'])}</div>"
                       f"<div class=\"bar\">{bar(v['outlets'], topv, 'o')}{pct(v['outlets'])}</div></div></td>"
                       f"<td class=\"n\">{gap_words(v['gap'])}</td></tr>" for t, v in g) + "</tbody></table>")

    tt = sorted(d["topic_trend"].items(), key=lambda x: x[1]["people_change"] if x[1]["people_change"] is not None else 0)
    weeks = d["weeks"]
    h.append(f'<h2>4. Fatigue</h2><p>How each topic\'s share of people\'s attention and of outlets\' coverage changed between the first and the second half of the period '
             f'(before and from {E(pages.fmt_date(d["half"], "en"))}). A topic that loses people\'s attention while outlets keep covering it shows signs of fatigue.</p>'
             '<table><thead><tr><th>Topic</th><th>People\'s attention</th><th>Outlets\' coverage</th><th></th></tr></thead><tbody>'
             + "".join(f"<tr><td>{E(theme(cfg, t))}</td><td class=\"n\">{pct(v['people_before'])} → {pct(v['people_after'])}</td>"
                       f"<td class=\"n\">{pct(v['outlets_before'])} → {pct(v['outlets_after'])}</td><td>{'<b>signs of fatigue</b>' if v['fatigue'] else ''}</td></tr>" for t, v in tt)
             + '</tbody></table><p>Week by week, the share of people\'s attention on stories whose reactions carried tiredness, resignation or numbness, and on stories with voiced doubt:</p>'
             '<table><thead><tr><th>Week</th><th>People\'s mood</th><th>Tiredness</th><th>Doubt</th></tr></thead><tbody>'
             + "".join(f"<tr><td class=\"n\">{E(w['week'])}{' (partial)' if w.get('partial') else ''}</td><td>{E(tone(w['people']))}</td>"
                       f"<td class=\"n\"><div class=\"bar\">{bar(w['tired'], 0.3)}{pct(w['tired'])}</div></td><td class=\"n\">{pct(w['doubt'])}</td></tr>" for w in weeks if w["people"] is not None)
             + "</tbody></table>")

    pl = d["platforms"]
    vs = sorted(d["video_share"].items(), key=lambda x: -x[1])
    eng = d["engagement"]
    emax = max(eng.values()) if eng else 1
    h.append('<h2>5. Where people react, and what engages them</h2><p>Share of the conversation analysed, by platform:</p><table><tbody>'
             + "".join(f"<tr><td>{E(PLATFORMS.get(k, k))}</td><td class=\"n\"><div class=\"bar\">{bar(v, max(pl.values()))}{pct(v)}</div></td></tr>" for k, v in pl.items())
             + '</tbody></table><p>By topic: the share of reactions under videos (YouTube), and engagement per post (likes, views and comments the posts drew, as an index: the topic with the most is 100).</p>'
             '<table><thead><tr><th>Topic</th><th>Under videos</th><th>Engagement</th></tr></thead><tbody>'
             + "".join(f"<tr><td>{E(theme(cfg, t))}</td><td class=\"n\">{pct(v)}</td><td class=\"n\"><div class=\"bar\">{bar(eng.get(t, 0), emax)}{round(100 * eng.get(t, 0) / emax)}</div></td></tr>" for t, v in vs)
             + "</tbody></table>")

    la = d["languages"]
    h.append('<h2>6. Languages</h2><table><thead><tr><th>Language</th><th>Posts and comments</th><th>Mood</th><th>Main topics (share of the language\'s reactions, mood)</th></tr></thead><tbody>'
             + "".join(f"<tr><td>{E(LANGS.get(k, k))}</td><td class=\"n\">{v['posts']:,}</td><td>{E(tone(v['tone']))}</td><td>"
                       + "; ".join(f"{E(theme(cfg, t))} {pct(x['share'])}, {E(tone(x['tone']).lower())}" for t, x in list(v["topics"].items())[:3]) + "</td></tr>" for k, v in la.items())
             + "</tbody></table>")
    emo = d["emotions"]
    h.append('<h2>7. Emotions in reactions</h2><table><tbody>' + "".join(
        f"<tr><td>{E(k.capitalize())}</td><td class=\"n\"><div class=\"bar\">{bar(v, max(emo.values()))}{pct(v)}</div></td></tr>" for k, v in emo.items()) + "</tbody></table>")

    h.append('<h2>Method and limits</h2>'
             '<p><b>Source.</b> Public posts and comments about Syria collected several times a day from YouTube comments, Telegram channels, Bluesky, Reddit, X and news sites, '
             'in Arabic, Kurdish and English. An AI model (Claude, by Anthropic) groups them into stories and rates the tone of people and of each outlet type, story by story; '
             'a validation tool compares its coding with human coding. Each story counts once a day (the day\'s last analysis).</p>'
             '<p><b>Outlet types.</b> State media (SANA, the Presidency, Al-Ikhbariya); independent and private Syrian outlets (Enab Baladi, Syria TV, Al-Watan and others); '
             'Arab and regional outlets (Al Jazeera, Al Arabiya, Asharq, TRT Arabi, Anadolu and others); Kurdish outlets (ANHA, North Press, Rudaw, Kurdistan24); '
             'international news through Google News.</p>'
             '<p><b>Indicators.</b> Doubt: reactions the model described as sceptical, suspicious, mocking or disbelieving of official accounts, promises or reports. '
             'Fatigue: a topic\'s share of people\'s attention falling by a quarter or more while outlets\' share holds; tiredness: reactions carrying tiredness, resignation, '
             'numbness, fatalism or helplessness. Engagement: likes, views and comments drawn by the posts analysed, per post.</p>'
             '<p><b>Limits.</b> People who post and comment in public are not a sample of all Syrians: the data says nothing about age, gender, education or income, about '
             'people who are offline or do not post, or about private messaging (WhatsApp) and Facebook, which the tracker does not collect. Silence, news avoidance '
             'and self-censorship are invisible to it. Alignment with an outlet\'s tone is not trust. These indicators are meant to sit beside a representative survey, '
             'focus groups and interviews, which answer who audiences are, what they can access and why they trust what they trust.</p>'
             f'<p class="note">Live site: <a href="{E(base)}/">{E(base.replace("https://", ""))}</a> · data as of {E(pages.fmt_date(d["generated_at"], "en", True))}. '
             'Individuals are never named, quoted or linked.</p></article>')
    return "\n".join(h)


def write(cfg: dict, d: dict) -> None:
    out = pages.ROOT / "audience"
    out.mkdir(exist_ok=True)
    html = pages.page(cfg, "en", "Audience snapshot", "Indicators of Syrian online audiences: alignment with outlets, doubt, coverage gaps, fatigue, platforms and languages.",
                      body(cfg, d), "audience/en.html", "audience/en.html", root="../", kind="article", noindex=True)
    page = out / "en.html"
    page.write_text(html, encoding="utf-8")
    import report_pdf
    binary = report_pdf.chrome()
    if not binary:
        print("No Chrome: audience/en.pdf not made.")
        return
    with tempfile.TemporaryDirectory() as tmp:          # A4 pages, for attaching to proposals
        src = out / ".en.print.html"
        src.write_text(html.replace("</head>", "<style>@page{size:A4;margin:14mm}</style></head>", 1), encoding="utf-8")
        try:
            subprocess.run([binary, "--headless=new", "--disable-gpu", "--no-sandbox", "--no-pdf-header-footer", "--virtual-time-budget=10000",
                            "--generate-pdf-document-outline", f"--print-to-pdf={out / 'en.pdf'}", src.resolve().as_uri()], capture_output=True, timeout=120, cwd=tmp)
        finally:
            src.unlink(missing_ok=True)
    print("audience/en.html and audience/en.pdf written.")


if __name__ == "__main__":
    import pipeline as P
    write(P.load_config(), json.loads((pages.DATA / "audience.json").read_text(encoding="utf-8")))
