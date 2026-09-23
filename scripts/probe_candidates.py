"""Temporary: tests candidate sources from GitHub Actions (which has internet access)."""
import datetime as dt, re, concurrent.futures as cf, requests, feedparser
from bs4 import BeautifulSoup
H = {"User-Agent": "Mozilla/5.0 (compatible; SyriaNarrativeTracker/1.0)"}
NOW = dt.datetime.now(dt.timezone.utc)
KW = re.compile(r"سوري|دمشق|حلب|حمص|إدلب|ادلب|درعا|السويداء|اللاذقية|الحسكة|القامشلي|الرقة|دير الزور|Syria|Damascus|Aleppo|Sûriye|Suriye|Rojava|Qamişlo|Kobanê|Efrîn|Hesek|Şam|Heleb|سووریا|ڕۆژاوا", re.I)

TG = """SANANewsEnglish Enabbaladi_en SANAArabic sana_syria SanaNews Sana_Ar sana_ar SyrianArabNewsAgency SyrianPresidency SyPresidency
alekhbariahsy AlikhbariaSY alikhbariah syr_television syriatv SyriaTvNews tvsyria syria_tv SyriaTV_net
EnabBaladiAR enabbaladi_ar enab_baladi EnabBaladi syriahr SOHR_ar SyrianObservatory HalabToday halabtodaytv HalabTodayTV
orient_news OrientNews orienttv Step_news stepagency stepnewsagency step_agency baladinews Baladi_News zamanalwsl Zaman_alwasl
Suwayda24 suwayda_24 suwayda24news sweida24 ShaamNews shaamnetwork Sham_Network jesrpress Jesr_press levant24_ Levant24 SyriaDirect
ANHAArabic anha_ar ANHA_Arabic hawarnews hawarnews_ar ANHA_English ANHAKurdi hawar_news anhaenglish
npasyria npa_arabic NPA_Syria npasyria_ar npa_english NorthPress_ar NorthPressAgency npaenglish
ronahitv RonahiTV Ronahi_TV SDFpress sdf_press SDF_Syria sdfmediacenter
rudaw Rudaw_net RudawKurdish RudawArabic rudaw_arabic rudawarabic rudawenglish
Kurdistan24 k24arabic kurdistan24_ar kurdistan24english kurdistan24kurdi
rojnews RojNews ANFNews anfarabic anf_arabic anfkurdi anfenglish
LatakiaNews latakia_now Lattakia_now homs_now daraa24 Daraa_24 HouranFree horanfree DeirEzzor24 deirezzor24 eyeofeuphrates
AJABreaking ajanews AlJazeera aljazeeranews alarabiya AlArabiya_Brk AlArabiya SkyNewsArabia skynewsarabia asharqnews aawsat_news
AlMayadeenNews almayadeen rtarabic RTarabic bbcarabic BBCArabic France24_ar dw_arabic AnadoluAr aa_arabic trtarabi TRTArabi
alaraby_tv AlarabyTV MiddleEastEye TheNewArab syrianobserver""".split()

RSS = """https://news.google.com/rss/search?q=%D8%B3%D9%88%D8%B1%D9%8A%D8%A7&hl=ar&gl=SY&ceid=SY:ar
https://news.google.com/rss/search?q=Syria&hl=en-US&gl=US&ceid=US:en
https://news.google.com/rss/search?q=S%C3%BBriye+OR+Rojava&hl=tr&gl=TR&ceid=TR:tr
https://news.google.com/rss/search?q=Rojava+OR+S%C3%BBriye+OR+Qami%C5%9Flo+OR+Kob%C3%AAn%C3%AA&hl=en-US&gl=US&ceid=US:en
https://www.enabbaladi.net/feed
https://english.enabbaladi.net/feed
https://www.syriahr.com/feed
https://www.syriahr.com/en/feed
https://npasyria.com/feed
https://npasyria.com/en/feed
https://npasyria.com/ku/feed
https://www.hawarnews.com/ar/rss
https://www.hawarnews.com/kr/rss
https://www.hawarnews.com/en/rss
https://hawarnews.com/ar/feed
https://www.rudaw.net/arabic/rss
https://www.rudaw.net/rss/arabic
https://www.rudaw.net/kurmanci/rss
https://www.rudaw.net/english/rss
https://www.kurdistan24.net/ar/rss
https://www.kurdistan24.net/en/rss
https://www.kurdistan24.net/ku/rss
https://www.kurdistan24.net/kmr/rss
https://www.syria.tv/rss.xml
https://www.syria.tv/feed
https://sana.sy/feed
https://sana.sy/en/feed
https://www.sana.sy/feed
https://www.aljazeera.com/xml/rss/all.xml
https://www.aljazeera.net/aljazeerarss/a7c186be-1baa-4bd4-9d80-a84db769f779/73d0e1b4-532f-45ef-b135-bfdff8b8cab9
https://syriadirect.org/feed/
https://www.levant24.com/feed
https://suwayda24.com/feed
https://www.zamanalwsl.net/rss
https://orient-news.net/rss
https://www.france24.com/ar/rss
https://rss.dw.com/xml/rss-ar-all
https://feeds.bbci.co.uk/arabic/middleeast/rss.xml
https://feeds.bbci.co.uk/news/world/middle_east/rss.xml
https://anfarabic.com/feed.rss
https://anfkurdi.com/feed.rss
https://anfenglish.com/feed.rss
https://www.alaraby.co.uk/rss
https://www.aa.com.tr/ar/rss/default?cat=guncel
https://www.skynewsarabia.com/rss/middle-east.xml
https://www.aawsat.com/feed
https://www.independentarabia.com/rss
https://www.syria.news/feed
https://halabtodaytv.net/feed
https://www.middleeasteye.net/rss
https://www.newarab.com/rss
https://stepagency-sy.net/feed
https://www.alquds.co.uk/feed
https://www.ronahi.net/feed
https://www.xeber24.org/feed
https://www.basnews.com/ar/rss
https://ku.hawarnews.com/rss""".split()

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
    for q in ["سوريا", "Syria", "Rojava"]:
        for base in ["https://public.api.bsky.app", "https://api.bsky.app"]:
            try:
                r = requests.get(base + "/xrpc/app.bsky.feed.searchPosts", params={"q": q, "limit": 25, "sort": "latest"}, headers=H, timeout=25)
                n = len(r.json().get("posts", [])) if r.ok else 0
                out.append(f"BSKY {r.status_code} {base} q={q} posts={n} {r.text[:120] if not r.ok else ''}")
            except Exception as e: out.append(f"BSKY ERR {e}")
    return out

with cf.ThreadPoolExecutor(12) as ex:
    for line in ex.map(tg, TG): print(line, flush=True)
    for line in ex.map(rss, RSS): print(line, flush=True)
for line in extra(): print(line)
