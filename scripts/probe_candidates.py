"""Temporary: tests candidate sources from GitHub Actions (which has internet access)."""
import datetime as dt, re, concurrent.futures as cf, requests, feedparser
from bs4 import BeautifulSoup
H = {"User-Agent": "Mozilla/5.0 (compatible; SyriaNarrativeTracker/1.0)"}
NOW = dt.datetime.now(dt.timezone.utc)
KW = re.compile(r"سوري|دمشق|حلب|حمص|إدلب|ادلب|درعا|السويداء|اللاذقية|الحسكة|القامشلي|الرقة|دير الزور|Syria|Damascus|Aleppo|Sûriye|Suriye|Rojava|Qamişlo|Kobanê|Efrîn|Hesek|Şam|Heleb|سووریا|ڕۆژاوا", re.I)

TG = """ronahi_tv Ronahitv_official rudawkurmanci RudawKurmanci kurdistan24kurmanci anhakurdi hawarnewskurdi ANHA_Kurdi rojavanews RojavaNews rojava_news xeber24 Xeber24 welatnews ANFKurmanci anfkurmanci sterktv SterkTV medyanews k24kurdi npa_kurdi npakurdi NPA_Kurdi RonahiNews anha_kurdi anhakurmanci ciratv jinnews rudawkurdish RudawSorani rudawsorani k24sorani RojavaIC rojava_ic aanes_ar AANES_official smart_news_ar SMARTNewsAgency smartnews SuwaydaNews suwayda_news alsuwayda24 sweida_24 ssnnews Suwayda24_ suwayda24_news SuwaydaAlaan Lattakia_24 lattakianow tartousnow SyrianCoast HomsNow Daraa24_ horan_free deir_ezzor24 furatpost FuratPost syriatv_net syria_tv_net SyriaTVChannel orientnews_net OrientNewsNet sohr_news damascusnow DamascusNow damascus_now AleppoNow SyrianCivilDefence SyriaCivilDefence syria_moi SyrianMOI moi_syria SyrianMoFA syrianmofa sanaarabic SANA_Syria sana_sy syriahr_ar sohr_ar2 rudawnews rudaw_kurdi sdf_press Syrian_Kurds kurdistan_24 rudawkurdi rojnews1 anf_kurdi ANHA_Kurmanci hawarnews_kurdi hawarnews_en""".split()

RSS = """https://www.reddit.com/r/syria/comments/.rss
https://www.reddit.com/r/syria/new/.rss
https://www.reddit.com/r/Kurdistan/comments/.rss
https://www.reddit.com/r/kurdistan/new/.rss
https://www.reddit.com/r/Rojava/new/.rss
https://www.reddit.com/r/arabs/comments/.rss
https://news.google.com/rss/search?q=Rojava&hl=ku&gl=IQ&ceid=IQ:ku
https://news.google.com/rss/search?q=%D9%82%D8%B3%D8%AF+OR+%D8%A7%D9%84%D8%A3%D9%83%D8%B1%D8%A7%D8%AF+%D8%B3%D9%88%D8%B1%D9%8A%D8%A7&hl=ar&gl=SY&ceid=SY:ar
https://news.google.com/rss/search?q=Suriye&hl=tr&gl=TR&ceid=TR:tr
https://www.rudaw.net/arabic/rss.xml
https://www.kurdistan24.net/ar/rss.xml
https://anha.net/rss
https://www.anha.net/ku/rss
https://npasyria.com/rss""".split()

def tg(name):
    try:
        r = requests.get(f"https://t.me/s/{name}", headers=H, timeout=25)
        s = BeautifulSoup(r.text, "html.parser")
        title = (s.select_one(".tgme_channel_info_header_title") or s.select_one("meta[property='og:title']"))
        title = title.get_text(strip=True) if hasattr(title, "get_text") and title.get_text(strip=True) else (title.get("content") if title else "")
        subs = s.select_one(".tgme_channel_info_counter .counter_value")
        msgs = s.select("div.tgme_widget_message[data-post]")
        texts = [m.select_one(".tgme_widget_message_text") for m in msgs]
        texts = [t.get_text(" ", strip=True) for t in texts if t]
        times = [dt.datetime.fromisoformat(t["datetime"]) for t in s.select(".tgme_widget_message_date time[datetime]")]
        newest = round((NOW - max(times)).total_seconds() / 3600, 1) if times else None
        day = sum(1 for t in times if (NOW - t).total_seconds() < 86400)
        joined = " ".join(texts)
        ar = len(re.findall(r"[؀-ۿ]", joined)); la = len(re.findall(r"[A-Za-z]", joined))
        ku = len(re.findall(r"[êîûçşÊÎÛÇŞ]|ڕ|ۆ|ێ|ڵ", joined))
        kw = sum(1 for t in texts if KW.search(t))
        return f"TG {name:22} ok={bool(msgs)} title={title[:40]!r} subs={subs.get_text() if subs else '-'} msgs={len(texts)} last24h={day} newest_h={newest} ar={ar} latin={la} kurdishchars={ku} syria_kw={kw}/{len(texts)}"
    except Exception as e:
        return f"TG {name:22} ERR {e}"

def rss(u):
    try:
        r = requests.get(u, headers=H, timeout=25)
        p = feedparser.parse(r.content)
        es = p.entries
        ts = [dt.datetime(*(e.get("published_parsed") or e.get("updated_parsed"))[:6], tzinfo=dt.timezone.utc) for e in es if (e.get("published_parsed") or e.get("updated_parsed"))]
        day = sum(1 for t in ts if (NOW - t).total_seconds() < 86400)
        kw = sum(1 for e in es if KW.search(e.get("title", "") + " " + e.get("summary", "")))
        return f"RSS {r.status_code} n={len(es)} last24h={day} syria_kw={kw} title={p.feed.get('title','')[:40]!r} {u}"
    except Exception as e:
        return f"RSS ERR {e} {u}"

def extra():
    out = []
    for u in ["https://www.reddit.com/r/syria/new.json?limit=5", "https://old.reddit.com/r/syria/new.json?limit=5",
              "https://www.reddit.com/r/syria/new/.rss", "https://www.reddit.com/r/Kurdistan/new/.rss"]:
        try:
            r = requests.get(u, headers=H, timeout=25); out.append(f"REDDIT {r.status_code} len={len(r.text)} {u}")
        except Exception as e: out.append(f"REDDIT ERR {e} {u}")
    for q in ["سوريا", "Syria", "Rojava", "Sûriyê", "Kurd", "Kobanê", "قسد", "السوريين"]:
        for base in ["https://api.bsky.app"]:
            try:
                r = requests.get(base + "/xrpc/app.bsky.feed.searchPosts", params={"q": q, "limit": 25, "sort": "latest"}, headers=H, timeout=25)
                ps = r.json().get("posts", []) if r.ok else []
                n = len(ps)
                ages = [round((NOW - dt.datetime.fromisoformat(x["record"]["createdAt"].replace("Z","+00:00"))).total_seconds()/3600,1) for x in ps if x.get("record",{}).get("createdAt")]
                langs = [",".join(x["record"].get("langs") or ["?"]) for x in ps]
                n = f"{n} ages_h={ages[:3]}..{ages[-1:] } langs={sorted(set(langs))} sample={[x['record'].get('text','')[:60] for x in ps[:2]]}"
                out.append(f"BSKY {r.status_code} {base} q={q} posts={n} {r.text[:120] if not r.ok else ''}")
            except Exception as e: out.append(f"BSKY ERR {e}")
    return out

with cf.ThreadPoolExecutor(4) as ex:
    for line in ex.map(tg, TG): print(line, flush=True)
for u in RSS:
    import time; time.sleep(3); print(rss(u), flush=True)
for line in extra(): print(line)
