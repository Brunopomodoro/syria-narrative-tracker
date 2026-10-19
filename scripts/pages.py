#!/usr/bin/env python3
"""
Static pages for the Syria Narrative Tracker, written by the pipeline after every run:

  stories/en/<key>.html, stories/ar/<key>.html   a permanent page per story, with its full latest analysis and its history
  stories/en/index.html, stories/ar/index.html   the recent stories, by day
  weekly/en/<week>.html, weekly/ar/<week>.html   the weekly digests (text from scripts/weekly.py)
  feed.xml, feed-ar.xml                          RSS feeds of the weekly digests
  sitemap.xml, robots.txt                        for search engines
  index.html                                     the crawlable block between <!--prerender--> and <!--/prerender-->

Everything here is plain HTML built from the data files; nothing calls the network or Claude.
"""
from __future__ import annotations

import datetime as dt
import html
import json
import pathlib
import re
from collections import defaultdict

import archive
import brand  # noqa: E402
import hashtags  # noqa: E402

ROOT = archive.ROOT
DATA = archive.DATA
STORIES = ROOT / "stories"
WEEKLY = ROOT / "weekly"
MONTHLY = ROOT / "monthly"
STORY_INDEX = STORIES / "index.json"
UTC = dt.timezone.utc
LANGS = ("en", "ar")
MONTHS_AR = ["كانون الثاني", "شباط", "آذار", "نيسان", "أيار", "حزيران", "تموز", "آب", "أيلول", "تشرين الأول", "تشرين الثاني", "كانون الأول"]
MONTHS_EN = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]

W = {   # the words on the static pages
    "en": {"tracker": "Tracker", "trends": "Trends", "data": "Data", "about": "About", "switch": "العربية",
           "people": "People", "outlets": "Outlets", "reacting": "How people are reacting", "framed": "How it's framed", "watch": "Watch for:",
           "sigTitle": "Signs of coordination:", "sigLevels": {"none": "none", "low": "weak", "medium": "moderate", "high": "strong"},
           "sigNote": "Measured signals, not proof: real breaking news, popular slogans and a few devoted commenters produce them too. The About page explains each one.",
           "where": "Sources", "overtime": "Over time", "update": "Update", "share": "Share of discussion", "firstSeen": "First seen", "lastSeen": "Last seen",
           "updates": "updates", "update1": "update", "story": "Story", "theme": "Theme", "emotions": "Emotions", "listing": "Stories", "listingSub": "Every story the tracker has followed in the last 30 days, by the day it was last seen. Older stories are in the downloads on the Data page.",
           "allStories": "All recent stories", "digest": "Weekly digest", "digests": "Weekly digests", "week": "Week", "highlights": "The week's stories", "watchNext": "What to watch",
           "themeTable": "Themes this week", "dailyTone": "Tone by day", "stories": "Stories", "posts": "Posts analysed", "vsLast": "vs last week",
           "postsNote": "Each update analyses a sample of up to {n} posts from the previous {h} hours, so one post can be counted in several updates. Compare days with each other rather than reading the figures as numbers of posts.",
           "note": "Written automatically by an AI model from the week's public posts. It describes what was said, not what is true.",
           "storyNote": "Analysis generated automatically by an AI model from public posts. It describes what is being said, not what is true. Individuals are never named, quoted or linked.",
           "tone": ["Strongly negative", "Leaning negative", "Mostly neutral", "Leaning positive", "Strongly positive", "No reactions yet"],
           "footer": "Summaries are written automatically by an AI model from public posts. They describe what is being said, not what is true.",
           "feedTitle": "Syria Narrative Tracker: weekly digest", "feedDesc": "A weekly written summary of what is being said about Syria online.",
           "review": "Monthly report", "reviews": "Monthly reports", "month": "Month", "monthHighlights": "The stories that mattered", "watchMonth": "What to watch next month",
           "weeksBrief": "The weeks in brief", "flaggedTitle": "Stories that carried signs of coordination", "themeTableMonth": "Themes this month", "vsLastMonth": "vs last month",
           "weeklyTone": "Tone by week", "weekCol": "Week", "daysCol": "Days", "readOnline": "Read online", "subscribe": "Subscribe by email", "level": "Level",
           "monthNote": "Written automatically by an AI model from the month's public posts and the tracker's weekly digests. It describes what was said, not what is true.",
           "daily": "Daily brief", "dailies": "Daily briefs", "dailySub": "One page per day: the last update's summary, the day's tone and numbers, and every story of the day with its analysis. Built from the archive; no model call.",
           "dailyMood": "The day in a word", "dayNumbers": "The day in numbers", "storiesOfDay": "The day's stories", "asOf": "as of the last update,",
           "reportsTab": "Reports", "expertsTab": "Expert view", "reportLabel": "Monthly report", "keyFindings": "Key findings", "inNumbers": "The month in numbers", "analysis": "Analysis",
           "aboutReport": "About this report", "privacy": "Privacy", "support": "Support", "related": "Related stories", "contact": "Contact", "shareIt": "Share", "pdf": "Download PDF", "cite": "Cite as",
           "peopleTone": "People's tone", "outletTone": "Outlets' tone", "vsPrev": "vs previous month", "postIdx": "post analyses", "updatesN": "updates", "storiesN": "stories followed", "daysN": "days covered",
           "chartThemes": "Share of discussion by theme", "chartTone": "Tone by week: people and outlets (−1 to +1)",
           "fromWhere": "Where the posts came from", "langsLbl": "Languages", "methodLink": "Method, sources and limitations", "licence": "Data: CC BY 4.0", "generatedOn": "Generated",
           "methodText": "This report was generated automatically by the Syria Narrative Tracker from {posts} post analyses over {days} days, drawn from {sources} public sources (Telegram channels, news sites, YouTube comments, Reddit, X and Bluesky) and grouped into stories by an AI model ({model}). Tone runs from −1 (anger, fear, grief) to +1 (hope, pride). It describes what was said online, not what is true, and it is not a representative survey of Syrians: online discussion over-represents people with good connectivity, diaspora communities and media outlets.",
           "citeText": "{site} ({year}). Monthly report, {month}. {url}",
           "platformNames": {"telegram": "Telegram channels", "telegram_comments": "Telegram comments", "telegram_groups": "Telegram groups", "news": "News sites", "youtube": "YouTube comments", "reddit": "Reddit", "x": "X", "bluesky": "Bluesky", "threads": "Threads", "instagram": "Instagram"},
           "langNames": {"ar": "Arabic", "ku": "Kurdish", "en": "English", "other": "other"},
           "feedTitleMonthly": "Syria Narrative Tracker: monthly review", "feedDescMonthly": "A monthly written review of what is being said about Syria online: what moved, who said what, and the stories that mattered.",
           "prerender": "What people are talking about", "moreStories": "More stories", "readMore": "Read the analysis", "seenIn": "seen in",
           "home": "Home", "stories": "Stories", "expertsTitle": "Expert view", "sourcesTitle": "Sources", "expertsLatest": "In the Expert view",
           "xDay": "What international and Arab experts said that day", "xWeek": "This week in the Expert view: our analysis of international and Arab reports",
           "xArea": "The expert view on {area} this week", "areas": {"security": "security", "economy": "the economy", "governance": "governance"}},
    "ar": {"tracker": "المتتبّع", "trends": "الاتجاهات", "data": "البيانات", "about": "حول الموقع", "switch": "English",
           "people": "الناس", "outlets": "وسائل الإعلام", "reacting": "كيف يتفاعل الناس", "framed": "كيف تُقدَّم القصة", "watch": "انتبه إلى:",
           "sigTitle": "مؤشرات التنسيق:", "sigLevels": {"none": "لا شيء", "low": "ضعيفة", "medium": "متوسطة", "high": "قوية"},
           "sigNote": "مؤشرات مقيسة لا أدلة: الأخبار العاجلة الحقيقية والشعارات الشائعة وقلة من المعلّقين المتحمسين تنتجها أيضاً. تشرح صفحة «حول» كل مؤشر.",
           "where": "المصادر", "overtime": "مع الوقت", "update": "التحديث", "share": "الحصة من النقاش", "firstSeen": "أول ظهور", "lastSeen": "آخر ظهور",
           "updates": "تحديثاً", "update1": "تحديث واحد", "story": "قصة", "theme": "الموضوع", "emotions": "المشاعر", "listing": "القصص", "listingSub": "كل قصة تابعها المتتبّع خلال آخر ٣٠ يوماً، حسب يوم آخر ظهور لها. القصص الأقدم في ملفات التنزيل على صفحة البيانات.",
           "allStories": "كل القصص الحديثة", "digest": "الملخص الأسبوعي", "digests": "الملخصات الأسبوعية", "week": "الأسبوع", "highlights": "قصص الأسبوع", "watchNext": "ما يجب متابعته",
           "themeTable": "مواضيع هذا الأسبوع", "dailyTone": "النبرة حسب اليوم", "stories": "القصص", "posts": "المنشورات المحلَّلة", "vsLast": "مقارنة بالأسبوع الماضي",
           "postsNote": "يحلّل كل تحديث عيّنة تصل إلى {n} منشور من الساعات الـ{h} السابقة، لذا قد يُحتسب المنشور الواحد في أكثر من تحديث. قارن الأيام ببعضها بدلاً من قراءة الأرقام كأعداد منشورات.",
           "note": "كُتب تلقائياً بواسطة نموذج ذكاء اصطناعي من منشورات الأسبوع العامة، ويصف ما قيل لا ما هو صحيح.",
           "storyNote": "تحليل مولَّد تلقائياً بواسطة نموذج ذكاء اصطناعي من منشورات عامة، يصف ما يُقال لا ما هو صحيح. لا يُذكر الأفراد ولا يُقتبس كلامهم ولا تُربط منشوراتهم.",
           "tone": ["سلبي جداً", "يميل إلى السلبية", "محايد غالباً", "يميل إلى الإيجابية", "إيجابي جداً", "لا تفاعل بعد"],
           "footer": "تُكتب الملخصات تلقائياً بواسطة نموذج ذكاء اصطناعي انطلاقاً من منشورات عامة، وهي تصف ما يُقال، لا ما هو صحيح.",
           "feedTitle": "متتبّع السرديات السورية: الملخص الأسبوعي", "feedDesc": "ملخص مكتوب أسبوعياً لما يُقال عن سوريا على الإنترنت.",
           "review": "التقرير الشهري", "reviews": "التقارير الشهرية", "month": "الشهر", "monthHighlights": "القصص التي كانت الأهم", "watchMonth": "ما يجب متابعته الشهر المقبل",
           "weeksBrief": "الأسابيع باختصار", "flaggedTitle": "قصص حملت مؤشرات تنسيق", "themeTableMonth": "مواضيع هذا الشهر", "vsLastMonth": "مقارنة بالشهر الماضي",
           "weeklyTone": "النبرة حسب الأسبوع", "weekCol": "الأسبوع", "daysCol": "الأيام", "readOnline": "اقرأ على الموقع", "subscribe": "اشترك بالبريد الإلكتروني", "level": "المستوى",
           "monthNote": "كُتبت تلقائياً بواسطة نموذج ذكاء اصطناعي من منشورات الشهر العامة ومن الملخصات الأسبوعية للمتتبّع، وتصف ما قيل لا ما هو صحيح.",
           "daily": "الموجز اليومي", "dailies": "الموجزات اليومية", "dailySub": "صفحة واحدة لكل يوم: ملخص آخر تحديث، ونبرة اليوم وأرقامه، وكل قصص اليوم مع تحليلها. تُبنى من الأرشيف من دون استدعاء النموذج.",
           "dailyMood": "اليوم في كلمة", "dayNumbers": "اليوم بالأرقام", "storiesOfDay": "قصص اليوم", "asOf": "حتى آخر تحديث،",
           "reportsTab": "التقارير", "expertsTab": "قراءات الخبراء", "reportLabel": "تقرير شهري", "keyFindings": "أبرز النتائج", "inNumbers": "الشهر بالأرقام", "analysis": "التحليل",
           "aboutReport": "عن هذا التقرير", "privacy": "الخصوصية", "support": "ادعمنا", "related": "قصص ذات صلة", "contact": "اتصل بنا", "shareIt": "مشاركة", "pdf": "تنزيل PDF", "cite": "للاستشهاد",
           "peopleTone": "نبرة الناس", "outletTone": "نبرة وسائل الإعلام", "vsPrev": "مقارنة بالشهر السابق", "postIdx": "تحليلات منشورات", "updatesN": "تحديثاً", "storiesN": "قصة متابَعة", "daysN": "يوماً مغطّى",
           "chartThemes": "الحصة من النقاش حسب الموضوع", "chartTone": "النبرة حسب الأسبوع: الناس ووسائل الإعلام (من −١ إلى +١)",
           "fromWhere": "من أين جاءت المنشورات", "langsLbl": "اللغات", "methodLink": "المنهجية والمصادر وحدود المنهج", "licence": "البيانات: CC BY 4.0", "generatedOn": "أُنشئ في",
           "methodText": "أُنشئ هذا التقرير تلقائياً بواسطة متتبّع السرديات السورية من {posts} تحليل منشور على مدى {days} يوماً، من {sources} مصدراً عاماً (قنوات تيليغرام ومواقع إخبارية وتعليقات يوتيوب وريديت وX وبلوسكاي)، جمعها نموذج ذكاء اصطناعي ({model}) في قصص. تمتد النبرة من −١ (غضب وخوف وحزن) إلى +١ (أمل وفخر). يصف التقرير ما قيل على الإنترنت لا ما هو صحيح، وليس مسحاً تمثيلياً للسوريين: النقاش على الإنترنت يُفرط في تمثيل أصحاب الاتصال الجيد والجاليات ووسائل الإعلام.",
           "citeText": "{site} ({year}). تقرير شهري، {month}. {url}",
           "platformNames": {"telegram": "قنوات تيليغرام", "telegram_comments": "تعليقات تيليغرام", "telegram_groups": "مجموعات تيليغرام", "news": "مواقع إخبارية", "youtube": "تعليقات يوتيوب", "reddit": "ريديت", "x": "X", "bluesky": "بلوسكاي", "threads": "ثريدز", "instagram": "إنستغرام"},
           "langNames": {"ar": "العربية", "ku": "الكردية", "en": "الإنجليزية", "other": "أخرى"},
           "feedTitleMonthly": "متتبّع السرديات السورية: المراجعة الشهرية", "feedDescMonthly": "مراجعة مكتوبة شهرياً لما يُقال عن سوريا على الإنترنت: ما الذي تغيّر، ومن قال ماذا، والقصص التي كانت الأهم.",
           "prerender": "ما الذي يتحدث عنه الناس", "moreStories": "المزيد من القصص", "readMore": "اقرأ التحليل", "seenIn": "ظهرت في",
           "home": "الرئيسية", "stories": "القصص", "expertsTitle": "قراءات الخبراء", "sourcesTitle": "المصادر", "expertsLatest": "في قراءات الخبراء",
           "xDay": "ما قاله الخبراء الدوليون والعرب في ذلك اليوم", "xWeek": "هذا الأسبوع في قراءات الخبراء: تحليلنا للتقارير الدولية والعربية",
           "xArea": "قراءة الخبراء في {area} هذا الأسبوع", "areas": {"security": "الأمن", "economy": "الاقتصاد", "governance": "الحوكمة"}},
}

CSS = """
:root{--paper:#F7F1E3;--ink:#1A1814;--muted:#45413A;--faint:#6B6559;--rule:#E2D9C5;--wash:#EEE6D3;--neg:#A3303C;--neu:#A7ABA3;--pos:#256454;--brass:#8A6420;
--sans:"IBM Plex Sans","IBM Plex Sans Arabic",system-ui,sans-serif;--display:"IBM Plex Serif","Noto Naskh Arabic",Georgia,serif}
:root{color-scheme:light}
html[lang=ar]{--sans:"IBM Plex Sans Arabic","IBM Plex Sans",system-ui,sans-serif;--display:"Noto Naskh Arabic","IBM Plex Sans Arabic",serif}
*{box-sizing:border-box}body{margin:0;background:var(--paper);color:var(--ink);font:17px/1.6 var(--sans)}html[lang=ar] body{font-size:18px;line-height:1.8}
a{color:inherit;text-decoration-color:var(--brass);text-underline-offset:3px}a:hover{color:var(--brass)}
.wrap{max-width:760px;margin:0 auto;padding:0 20px 40px}
.top{display:flex;justify-content:space-between;align-items:center;gap:16px;flex-wrap:wrap;padding:22px 0 18px;border-bottom:1px solid var(--rule);margin-bottom:34px}
.top .brand{display:flex;align-items:center;gap:9px;font-weight:600;font-size:1rem;text-decoration:none;color:var(--ink)}.top .brand .mark{width:26px;height:26px;flex:none}.purl{display:none}.top nav{display:flex;gap:18px;color:var(--muted);font-size:.88rem;flex-wrap:wrap}.top nav a{text-decoration:none}
.top .lang{border:1px solid var(--rule);border-radius:999px;padding:2px 12px;color:var(--ink)}
.eyebrow{color:var(--muted);font-size:.9rem;margin:0 0 10px}h1{font-family:var(--display);font-weight:600;font-size:1.9rem;line-height:1.25;margin:0 0 14px}
h2{font-family:var(--display);font-weight:600;font-size:1.25rem;margin:34px 0 10px}p{margin:0 0 14px;max-width:68ch}.sub{color:var(--muted);font-size:.9rem}
.tone{display:flex;gap:18px 28px;flex-wrap:wrap;margin:0 0 22px;color:var(--muted);font-size:.92rem}.tone i{display:inline-block;width:10px;height:10px;border-radius:50%;margin-inline-end:7px;vertical-align:middle}
.tone i.o{background:transparent;border:1.5px solid var(--ink)}.tone b{color:var(--ink);font-weight:500}
.reaction{border-inline-start:3px solid var(--neu);padding:6px 16px;margin:0 0 18px}.reaction p{margin:0}
ul{padding-inline-start:20px}li{margin-bottom:6px}.flag{color:var(--brass);font-size:.95rem}
.signals{margin:14px 0 18px;padding:10px 14px;border-inline-start:3px solid var(--faint);background:var(--wash);border-radius:0 6px 6px 0;font-size:.92rem}html[dir="rtl"] .signals{border-radius:6px 0 0 6px}.signals.medium{border-color:var(--brass)}.signals.high{border-color:var(--neg)}.signals p{margin:0}.signals ul{margin:6px 0 0}.signals .sub{margin-top:8px;font-size:.82rem}
.tw{overflow-x:auto;max-width:100%;margin:6px 0 18px}table{width:100%;border-collapse:collapse;font-size:.9rem}th,td{text-align:start;padding:7px 12px 7px 0;border-bottom:1px solid var(--rule);vertical-align:top}th{color:var(--muted);font-weight:500}
td.n{font-variant-numeric:tabular-nums;white-space:nowrap}.bar{position:relative;height:10px;background:var(--wash);border-radius:3px;min-width:80px}.bar i{position:absolute;inset-inline-start:0;top:0;height:100%;background:var(--brass);border-radius:3px;opacity:.85}
.day{margin:22px 0 6px;font-weight:500;color:var(--muted);font-size:.9rem}.list{list-style:none;padding:0}.list li{padding:8px 0;border-top:1px solid var(--rule);margin:0}.list .meta{display:block;color:var(--muted);font-size:.85rem}
.chip{display:inline-block;border:1px solid var(--rule);border-radius:999px;padding:1px 10px;font-size:.82rem;color:var(--muted);margin-inline-end:8px}
.xlink{margin:22px 0 8px;font-weight:500}
footer{margin-top:44px;padding-top:16px;border-top:1px solid var(--rule);color:var(--muted);font-size:.85rem}
.report .rmeta{margin-top:-6px}.cform{display:grid;gap:14px;max-width:560px;margin:18px 0}.cform label{display:grid;gap:5px;font-weight:600;font-size:.92rem}.cform input,.cform select,.cform textarea{font:inherit;font-weight:400;color:var(--ink);background:#fff;border:1px solid var(--rule);border-radius:8px;padding:9px 12px}.cform textarea{min-height:160px;resize:vertical}.cform input:focus,.cform select:focus,.cform textarea:focus{outline:2px solid var(--brass);outline-offset:1px}.cform button{justify-self:start;font:inherit;font-weight:600;background:var(--brass);color:#fff;border:0;border-radius:999px;padding:9px 22px;cursor:pointer}.cform .opt{font-weight:400;color:var(--muted)}.hp{display:none}.give{display:flex;flex-wrap:wrap;gap:10px}.give .chip{font-size:1rem;padding:6px 16px;background:var(--brass);color:#fff;border-color:var(--brass);text-decoration:none}.share{display:flex;flex-wrap:wrap;align-items:center;gap:8px;margin:14px 0 6px}.share a{border:1px solid var(--rule);border-radius:999px;padding:3px 12px;font-size:.84rem;text-decoration:none;color:var(--ink)}.share a:hover{border-color:var(--brass)}.share a.pdf{background:var(--brass);color:#fff;border-color:var(--brass)}
.report h2{margin-top:30px}.findings ol{padding-inline-start:22px}.findings li{margin-bottom:8px}.report ol li{margin-bottom:8px}
.kpis{display:grid;grid-template-columns:repeat(2,1fr);gap:10px;margin:12px 0 18px}.kpi{border:1px solid var(--rule);border-radius:8px;padding:10px 14px}.kpi b{display:block;font-family:var(--display);font-size:1.35rem;font-weight:600;line-height:1.25}.kpi span{color:var(--muted);font-size:.82rem}.kpi .delta{display:block;font-size:.8rem}
.charts{display:grid;grid-template-columns:1fr;gap:16px}.charts figure{margin:0;border:1px solid var(--rule);border-radius:8px;padding:12px 14px}.charts figcaption{font-weight:500;font-size:.92rem;margin-bottom:8px}.charts svg{display:block;max-width:100%;height:auto}.charts figure:only-child{grid-column:1/-1;max-width:680px}
.legend{display:flex;gap:18px;font-size:.82rem;color:var(--muted);margin:6px 0 0}.legend i{display:inline-block;width:18px;height:3px;vertical-align:middle;margin-inline-end:6px;background:currentColor}.legend i.b{background:var(--brass)}
.about-report{border-top:1px solid var(--rule);margin-top:30px;padding-top:14px;font-size:.88rem;color:var(--muted)}.about-report h2{margin-top:0;font-size:1.05rem}.about-report p{max-width:none}
@media (min-width:640px){.kpis{grid-template-columns:repeat(3,1fr)}.charts{grid-template-columns:1fr 1fr}}
@page{size:A4;margin:10mm 12mm}
@media print{body{font-size:9.5pt;line-height:1.35;background:#fff;color:#000}.wrap{max-width:none;padding:0}.share,footer,.chip,.print-hide,.wk-text,.top nav{display:none!important}.top{padding:0 0 5pt;margin:0 0 10pt;border-bottom:1px solid #bbb}.top .brand{font-size:9.5pt;color:#000}.top .brand .mark{width:14pt;height:14pt}.purl{display:block;color:#555;font-size:8.5pt}.eyebrow{display:block;margin:0 0 4pt}h1{font-size:18pt;margin-bottom:4pt}h2{font-size:11.5pt;margin:10pt 0 4pt}.report h2{margin-top:10pt}p{margin:0 0 4pt}li{margin-bottom:2pt}.report .stories ol{column-count:2;column-gap:16pt}
.kpis{grid-template-columns:repeat(6,1fr);gap:6pt}.kpi{padding:5pt 8pt;border-color:#bbb}.kpi b{font-size:12pt}.kpi span,.kpi .delta{font-size:7.5pt}.charts{grid-template-columns:1fr 1fr;gap:8pt}.charts figure{padding:5pt 8pt;border-color:#bbb}.charts figcaption{font-size:9pt}
.analysis{column-count:2;column-gap:16pt}.analysis h2{column-span:all}.weeks ul{column-count:2;column-gap:16pt}section,figure,.kpi,table,li{break-inside:avoid}a{text-decoration:none;color:inherit}.tw{overflow:visible}table{font-size:8.5pt}th,td{padding:2pt 6pt 2pt 0}.bar{min-width:50px}.about-report{font-size:8pt;margin-top:12pt;padding-top:6pt}.sub{font-size:8.5pt}svg text{fill:#000}}
"""

FONTS = '<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin><link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Serif:wght@400;500;600&family=IBM+Plex+Sans+Arabic:wght@400;500;600&family=Noto+Naskh+Arabic:wght@500;600;700&display=swap" rel="stylesheet">'
CSP = '<meta http-equiv="Content-Security-Policy" content="default-src \'self\'; script-src \'none\'; style-src \'self\' \'unsafe-inline\' https://fonts.googleapis.com; font-src https://fonts.gstatic.com; img-src \'self\' data:; object-src \'none\'; base-uri \'none\'; form-action \'none\'">'


# ----------------------------------------------------------------- helpers

def esc(s) -> str:
    return html.escape(str(s if s is not None else ""), quote=True)


def site_url(cfg: dict) -> str:
    u = str(cfg.get("site_url") or "").strip()
    if not u:
        cname = ROOT / "CNAME"
        if cname.exists():
            u = "https://" + cname.read_text(encoding="utf-8").strip()
    return u.rstrip("/")


def site_title(cfg: dict, lang: str) -> str:
    return str(cfg.get("site_title_ar") if lang == "ar" else cfg.get("site_title")) or "Syria Narrative Tracker"


def ar_digits(s: str) -> str:
    return s.translate(str.maketrans("0123456789", "٠١٢٣٤٥٦٧٨٩"))


def fmt_date(iso: str, lang: str, time: bool = False) -> str:
    d = archive_parse(iso)
    if not d:
        return str(iso or "")
    if lang == "ar":
        out = f"{d.day} {MONTHS_AR[d.month - 1]} {d.year}"
        if time:
            out += f"، {d.strftime('%H:%M')} UTC"
        return ar_digits(out)
    out = f"{d.day} {MONTHS_EN[d.month - 1]} {d.year}"
    return out + (f", {d.strftime('%H:%M')} UTC" if time else "")


def archive_parse(iso: str):
    try:
        s = str(iso)
        if len(s) == 10:
            return dt.datetime.strptime(s, "%Y-%m-%d").replace(tzinfo=UTC)
        return dt.datetime.fromisoformat(s.replace("Z", "+00:00")).astimezone(UTC)
    except (TypeError, ValueError):
        return None


def num(v, lang: str) -> str:
    s = f"{v:,}" if isinstance(v, int) else str(v)
    return ar_digits(s.replace(",", "٬")) if lang == "ar" else s


def pct(v, lang: str) -> str:
    return (ar_digits(str(round((v or 0) * 100))) + "٪") if lang == "ar" else f"{round((v or 0) * 100)}%"


def signed(v, lang: str) -> str:
    s = f"{v:+.2f}"
    return ar_digits(s.replace(".", "٫")) if lang == "ar" else s


def pts(v, lang: str) -> str:
    """A change in share, in percentage points."""
    s = f"{round(v * 100):+d}"
    return ar_digits(s) + " نقطة" if lang == "ar" else s + " pts"


def tone_label(v, lang: str) -> str:
    w = W[lang]["tone"]
    if v is None:
        return w[5]
    return w[0] if v <= -0.5 else w[1] if v <= -0.15 else w[2] if v < 0.15 else w[3] if v < 0.5 else w[4]


def tone_color(v) -> str:
    """The same neutral-to-red / neutral-to-green mix as the website."""
    v = max(-1.0, min(1.0, float(v or 0)))
    neu, neg, pos = (167, 171, 163), (163, 48, 60), (44, 118, 99)
    tgt, t = (neg, -v) if v < 0 else (pos, v)
    return "rgb(%d,%d,%d)" % tuple(round(a + (b - a) * t) for a, b in zip(neu, tgt))


def theme_label(cfg: dict, theme: str, lang: str) -> str:
    for t in archive.theme_catalog(cfg):
        if t["id"] == theme:
            return t["label_ar"] if lang == "ar" and t.get("label_ar") else t["label"]
    return theme


def t(n: dict, field: str, lang: str):
    """A text field in the page's language, falling back to the other language."""
    v = n.get(field + "_ar") if lang == "ar" else n.get(field)
    if v in (None, "", []):
        v = n.get(field) if lang == "ar" else n.get(field + "_ar")
    return v


# ----------------------------------------------------------------- the page frame

def page(cfg: dict, lang: str, title: str, description: str, body: str, path: str, alt_path: str, root: str = "../../",
         updated: str | None = None, kind: str = "article", image: str | None = None, jsonld: dict | None = None,
         noindex: bool = False, csp: str | None = None) -> str:
    w, base = W[lang], site_url(cfg)
    image = image or ("assets/og-ar.png" if lang == "ar" else "assets/og.png")
    other = "en" if lang == "ar" else "ar"
    canonical = f"{base}/{path}" if base else path
    alt = f"{base}/{alt_path}" if base else root + alt_path
    og = f"""<meta property="og:type" content="{kind}"><meta property="og:title" content="{esc(title)}"><meta property="og:description" content="{esc(description)}">
<meta property="og:url" content="{esc(canonical)}"><meta property="og:locale" content="{'ar_SY' if lang == 'ar' else 'en_GB'}"><meta property="og:site_name" content="{esc(site_title(cfg, lang))}">
<meta property="og:image" content="{esc((base + '/' if base else root) + image)}"><meta property="og:image:width" content="1200"><meta property="og:image:height" content="630"><meta name="twitter:card" content="summary_large_image">"""
    return f"""<!doctype html>
<html lang="{lang}" dir="{'rtl' if lang == 'ar' else 'ltr'}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
{csp or CSP}
<meta name="referrer" content="no-referrer">
<title>{esc(title)} · {esc(site_title(cfg, lang))}</title>
<meta name="description" content="{esc(description)}">
<link rel="canonical" href="{esc(canonical)}">{'<meta name="robots" content="noindex, follow">' if noindex else ''}
<link rel="alternate" hreflang="{lang}" href="{esc(canonical)}"><link rel="alternate" hreflang="{other}" href="{esc(alt)}">
<link rel="icon" href="{root}assets/logo.svg" type="image/svg+xml"><link rel="icon" href="{root}favicon.ico" sizes="32x32"><link rel="apple-touch-icon" href="{root}assets/apple-touch-icon.png">
<link rel="manifest" href="{root}site.webmanifest"><meta name="theme-color" content="#F7F1E3"><meta name="color-scheme" content="only light">
<link rel="alternate" type="application/rss+xml" title="{esc(w['feedTitle'])}" href="{root}{'feed-ar.xml' if lang == 'ar' else 'feed.xml'}">
<link rel="alternate" type="application/rss+xml" title="{esc(w['feedTitleMonthly'])}" href="{root}{'feed-monthly-ar.xml' if lang == 'ar' else 'feed-monthly.xml'}">
<link rel="alternate" type="application/rss+xml" title="{esc(w['expertsTab'])} · {esc(site_title(cfg, lang))}" href="{root}{'feed-experts-ar.xml' if lang == 'ar' else 'feed-experts.xml'}">
{og}
{ld_script(jsonld)}
{FONTS}
<style>{CSS}</style>
</head>
<body>
<div class="wrap">
<header class="top"><a class="brand" href="{root}{'ar/' if lang == 'ar' else ''}">{brand.inline_mark()}<span>{esc(site_title(cfg, lang))}</span></a><span class="purl" dir="ltr">{esc(base.replace('https://', ''))}</span>
<nav><a href="{root}{'ar/' if lang == 'ar' else ''}">{w['tracker']}</a><a href="{root}{'ar/' if lang == 'ar' else ''}#trends">{w['trends']}</a><a href="{root}{'ar/' if lang == 'ar' else ''}#reports">{w['reportsTab']}</a><a href="{root}experts/{lang}/index.html">{w['expertsTab']}</a><a href="{root}{'ar/' if lang == 'ar' else ''}#data">{w['data']}</a><a href="{root}{'ar/' if lang == 'ar' else ''}#about">{w['about']}</a>{(f'<a href="{root}support/{lang}.html">{w["support"]}</a>') if support_on(cfg) else ''}<a href="{root}contact/{lang}.html">{w['contact']}</a><a class="lang" lang="{other}" href="{root}{alt_path}">{w['switch']}</a></nav></header>
<main>
{body}
</main>
<footer>{esc(w['footer'])}{(' · ' + esc(fmt_date(updated, lang, True))) if updated else ''} · <a href="{root}privacy/{lang}.html">{w['privacy']}</a>{(f' · <a href="{root}support/{lang}.html">{w["support"]}</a>') if support_on(cfg) else ''} · <a href="{root}contact/{lang}.html">{w['contact']}</a> · <a href="{root}sources/{lang}.html">{SOURCES_WORDS[lang]['title']}</a></footer>
</div>
</body>
</html>
"""


def write(path: pathlib.Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")



# ----------------------------------------------------------------- structured data (schema.org, for search engines)

def ld_script(data: dict | None) -> str:
    """A JSON-LD block. It is data, not code: browsers do not run it, so the pages' script policy is unaffected."""
    if not data:
        return ""
    return '<script type="application/ld+json">' + json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/") + "</script>"


def ld_publisher(cfg: dict, lang: str) -> dict:
    base = site_url(cfg)
    return {"@type": "Organization", "name": site_title(cfg, lang), "url": f"{base}/",
            "logo": {"@type": "ImageObject", "url": f"{base}/assets/logo-512.png", "width": 512, "height": 512}}


def ld_article(cfg: dict, lang: str, kind: str, headline: str, description: str, path: str, published: str, modified: str,
               about: str = "", image: str | None = None) -> dict:
    """Article (stories, daily briefs) or Report (weekly digests, monthly reports)."""
    base = site_url(cfg)
    out = {"@context": "https://schema.org", "@type": kind, "headline": str(headline)[:110], "description": str(description)[:300],
           "inLanguage": lang, "url": f"{base}/{path}", "mainEntityOfPage": f"{base}/{path}",
           "datePublished": published or modified, "dateModified": modified or published,
           "image": f"{base}/{image or ('assets/og-ar.png' if lang == 'ar' else 'assets/og.png')}",
           "author": ld_publisher(cfg, lang), "publisher": ld_publisher(cfg, lang), "isAccessibleForFree": True,
           "license": "https://creativecommons.org/licenses/by/4.0/", "spatialCoverage": {"@type": "Place", "name": "Syria"}}
    if about:
        out["about"] = about
    return out


def ld_breadcrumbs(cfg: dict, lang: str, crumbs: list) -> dict:
    """BreadcrumbList: the site's home in the page's language, then (name, path) pairs; the last is the page itself."""
    base = site_url(cfg)
    items = [(W[lang]["home"], "ar/" if lang == "ar" else "")] + list(crumbs)
    return {"@context": "https://schema.org", "@type": "BreadcrumbList",
            "itemListElement": [{"@type": "ListItem", "position": i + 1, "name": str(n)[:110], "item": f"{base}/{path}"} for i, (n, path) in enumerate(items)]}


# The tracker's themes per Expert view area (scripts/experts.py AREA_THEMES), for linking story pages to the analysis.
THEME_AREA = {"security": "security", "israel-south": "security", "coast-alawite": "security", "suwayda-druze": "security",
              "economy": "economy", "refugees": "economy", "society": "economy",
              "governance": "governance", "justice": "governance", "northeast-kurdish": "governance", "international": "governance"}


def expert_link(lang: str, name: str, label: str) -> str:
    """A "see also" line to an Expert view page, only when that page exists."""
    if not (ROOT / "experts" / lang / name).exists():
        return ""
    return f'<p class="xlink">→ <a href="../../experts/{lang}/{esc(name)}">{esc(label)}</a></p>'


def week_of_date(date: str) -> str:
    y, w, _ = dt.date.fromisoformat(date[:10]).isocalendar()
    return f"{y}-W{w:02d}"


def index_min_runs(cfg: dict) -> int:
    """Stories seen in fewer updates than this are left out of search results (still on the site)."""
    return int((cfg.get("seo") or {}).get("index_min_runs", 2))


def story_indexable(cfg: dict, key: str, index: dict | None = None) -> bool:
    e = (index if index is not None else load_story_index()).get(key) or {}
    return int(e.get("runs") or 0) >= index_min_runs(cfg)


def related_stories(cfg: dict, key: str, theme: str, lang: str, limit: int = 5) -> str:
    """Links to other stories of the same theme that search engines may index, most recent first."""
    index = load_story_index()
    rows = sorted((e | {"key": k} for k, e in index.items() if k != key and e.get("theme") == theme and theme != "other"
                   and int(e.get("runs") or 0) >= index_min_runs(cfg)), key=lambda e: e.get("last_seen", ""), reverse=True)[:limit]
    if not rows:
        return ""
    items = "".join(f'<li><a href="{esc(e["key"])}.html">{esc(t(e, "title", lang))}</a> <span class="sub">{esc(fmt_date(e.get("last_seen", ""), lang))}</span></li>' for e in rows)
    return f"<h2>{W[lang]['related']}</h2><ul>{items}</ul>"


# ----------------------------------------------------------------- stories

def load_story_index() -> dict:
    return archive._load(STORY_INDEX, {})


def update_story_index(latest: dict) -> dict:
    """One entry per story ever shown: titles, theme, first and last seen, how many updates it appeared in, last tones."""
    index = load_story_index()
    when = latest.get("generated_at", "")
    for n in latest.get("narratives") or []:
        key = n.get("key") or archive.story_key(n)
        e = index.setdefault(key, {"first_seen": n.get("first_seen", when), "runs": 0, "last_run": ""})
        e.update({"id": n["id"], "title": n.get("title", ""), "title_ar": n.get("title_ar", ""), "theme": n.get("theme", "other"),
                  "last_seen": when, "public_sentiment": n.get("public_sentiment"), "sentiment": n.get("sentiment"),
                  "share": n.get("share", 0)})
        if e.get("last_run") != when:
            e["runs"] = int(e.get("runs") or 0) + 1
            e["last_run"] = when
    archive._save(STORY_INDEX, index)
    return index


def story_runs(key: str, first_day: str, last_day: str, cache: dict) -> list:
    """Every run in which the story appeared, from the archive: [(time, share, public_sentiment, sentiment, volume)]."""
    out = []
    for date in archive.all_days():
        if date < first_day or date > last_day:
            continue
        day = cache.get(date) or cache.setdefault(date, archive.load_day(date))
        for r in day.get("runs") or []:
            for n in r.get("narratives") or []:
                if (n.get("key") or archive.story_key(n)) == key:
                    out.append((r.get("generated_at"), n.get("share", 0), n.get("public_sentiment"), n.get("sentiment"), n.get("volume", 0)))
    return out


def signal_value(i: dict, lang: str) -> str:
    """One signal's value in words (the same phrasing as the website)."""
    v, n = i.get("value"), i.get("n")
    if isinstance(v, float) and v.is_integer():
        v = int(v)
    if lang == "ar":
        return {"copies": f"{pct(v, lang)} من {num(n, lang)} منشوراً للناس تكرار حرفي",
                "near_copies": f"{pct(v, lang)} من {num(n, lang)} نصاً مميزاً شبه متطابقة",
                "burst": f"احتوت الساعة الأكثر نشاطاً على {num(v, lang)} أضعاف المتوسط الساعي ({num(n, lang)} منشوراً)",
                "burst_no_news": "لم تغطِّ أي وسيلة إعلام على القائمة القصة في تلك الساعة",
                "synchrony": f"ظهر {num(v, lang)} نصوص على منصات عدة خلال ساعة",
                "concentration": f"كتب أعلى ٥٪ من المعلّقين {pct(v, lang)} من {num(n, lang)} تعليقاً",
                "regularity": f"تتفاوت الفواصل بين التعليقات بنسبة {pct(v, lang)} فقط ({num(n, lang)} تعليقاً)"}.get(i.get("id"), str(v))
    return {"copies": f"{pct(v, lang)} of {num(n, lang)} public posts are exact repeats",
            "near_copies": f"{pct(v, lang)} of {num(n, lang)} distinct texts are near-identical",
            "burst": f"the busiest hour held {v}× the hourly average ({num(n, lang)} posts)",
            "burst_no_news": "no outlet on the list covered the story in that hour",
            "synchrony": f"{num(v, lang)} texts appeared on several platforms within an hour",
            "concentration": f"the top 5% of commenters wrote {pct(v, lang)} of {num(n, lang)} comments",
            "regularity": f"comment intervals vary by only {pct(v, lang)} ({num(n, lang)} comments)"}.get(i.get("id"), str(v))


def story_body(cfg: dict, n: dict, runs: list, lang: str, when: str) -> str:
    w = W[lang]
    key = n.get("key") or archive.story_key(n)
    theme = n.get("theme", "other")
    pub, out = n.get("public_sentiment"), n.get("sentiment")
    first = n.get("first_seen") or (runs[0][0] if runs else when)
    tone = f"""<div class="tone"><span><i style="background:{tone_color(pub) if pub is not None else 'var(--faint)'}"></i>{w['people']}: <b>{esc(tone_label(pub, lang))}</b>{(' (' + signed(pub, lang) + ')') if pub is not None else ''}</span>
<span><i class="o"></i>{w['outlets']}: <b>{esc(tone_label(out, lang))}</b> ({signed(out or 0, lang)})</span></div>"""
    n_runs = len(runs) or 1
    parts = [f"""<p class="eyebrow"><a href="index.html">{w['listing']}</a> · <a href="../../{'ar/' if lang == 'ar' else ''}#trends">{esc(theme_label(cfg, theme, lang))}</a> · {w['firstSeen']} {esc(fmt_date(first, lang))} · {w['seenIn']} {num(n_runs, lang)} {w['update1'] if n_runs == 1 else w['updates']}</p>""",
             f"<h1>{esc(t(n, 'title', lang))}</h1>", tone, share_bar(cfg, lang, f"stories/{lang}/{key}.html", str(t(n, "title", lang)), tags=hashtags.select(cfg, lang, [theme], [t(n, "title", lang)])),
             f"<p>{esc(t(n, 'summary', lang))}</p>"]
    reaction = t(n, "public_reaction", lang)
    if reaction:
        parts.append(f"""<h2>{w['reacting']}</h2><div class="reaction" style="border-color:{tone_color(pub) if pub is not None else 'var(--neu)'}"><p>{esc(reaction)}</p></div>""")
    emotions = t(n, "emotions", lang) or []
    if emotions:
        parts.append(f"<p class=\"sub\">{w['emotions']}: {esc(('، ' if lang == 'ar' else ', ').join(emotions))}</p>")
    framings = t(n, "framings", lang) or []
    if framings:
        parts.append(f"<h2>{w['framed']}</h2><ul>" + "".join(f"<li>{esc(f)}</li>" for f in framings) + "</ul>")
    flags = t(n, "flags", lang) or []
    if flags:
        parts.append(f"<p class=\"flag\">{w['watch']} {esc(('؛ ' if lang == 'ar' else '; ').join(flags))}</p>")
    sig = n.get("signals") or {}
    if sig.get("items"):
        import signals as SIG
        cat = {c["id"]: c for c in SIG.CATALOG}
        rows = "".join(f"<li><b>{esc(cat[i['id']]['label_ar' if lang == 'ar' else 'label'] if i['id'] in cat else i['id'])}</b> {esc(signal_value(i, lang))}</li>" for i in sig["items"])
        parts.append(f"<div class=\"signals {esc(sig.get('level', ''))}\"><p><b>{w['sigTitle']} {w['sigLevels'].get(sig.get('level'), '')}</b></p><ul>{rows}</ul><p class=\"sub\">{esc(w['sigNote'])}</p></div>")
    names = n.get("sources") or []
    links = [e for e in (n.get("examples") or []) if str(e.get("url", "")).startswith("https://")]
    if names or links:
        src = ", ".join(f'<a href="{esc(e["url"])}" rel="noopener nofollow">{esc(e["source"])}</a>' for e in links)
        rest = [s for s in names if s not in {e["source"] for e in links}]
        parts.append(f"<h2>{w['where']}</h2><p>{src}{(', ' if src and rest else '') + esc(', '.join(rest))}</p>")
    if runs:
        rows = "".join(f"<tr><td class=\"n\">{esc(fmt_date(r[0], lang, True))}</td><td class=\"n\">{pct(r[1], lang)}</td>"
                       f"<td class=\"n\">{signed(r[2], lang) if r[2] is not None else '–'}</td><td class=\"n\">{signed(r[3] or 0, lang)}</td></tr>"
                       for r in reversed(runs[-40:]))
        parts.append(f"<h2>{w['overtime']}</h2><div class=\"tw\"><table><thead><tr><th>{w['update']}</th><th>{w['share']}</th><th>{w['people']}</th><th>{w['outlets']}</th></tr></thead><tbody>{rows}</tbody></table></div>")
    parts.append(related_stories(cfg, key, theme, lang))
    area = THEME_AREA.get(theme)
    if area:
        week = week_of_date(when or key[:10])
        parts.append(expert_link(lang, f"{week}-{area}.html", w["xArea"].format(area=w["areas"][area])))
    parts.append(f"<p class=\"sub\">{esc(w['storyNote'])}</p>")
    return "\n".join(parts)


def write_story_pages(cfg: dict, latest: dict, narratives: list | None = None, cache: dict | None = None) -> int:
    """Pages for the given stories (default: every story in latest). Returns how many were written."""
    cache = cache if cache is not None else {}
    when = latest.get("generated_at", "")
    today = when[:10]
    count = 0
    for n in narratives if narratives is not None else (latest.get("narratives") or []):
        key = n.get("key") or archive.story_key(n)
        if not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}-[a-z0-9-]+", key):
            continue
        runs = story_runs(key, key[:10], today, cache)
        thin = not story_indexable(cfg, key)
        for lang in LANGS:
            other = "ar" if lang == "en" else "en"
            body = story_body(cfg, n, runs, lang, when)
            desc = str(t(n, "summary", lang) or "")[:200]
            write(STORIES / lang / f"{key}.html",
                  page(cfg, lang, str(t(n, "title", lang) or key), desc, body, f"stories/{lang}/{key}.html", f"stories/{other}/{key}.html", updated=when,
                       noindex=thin, jsonld=[ld_article(cfg, lang, "Article", t(n, "title", lang) or key, desc, f"stories/{lang}/{key}.html",
                                                        str(n.get("first_seen") or (runs[0][0] if runs else when)), when, theme_label(cfg, n.get("theme", "other"), lang)),
                                             ld_breadcrumbs(cfg, lang, [(W[lang]["stories"], f"stories/{lang}/index.html"), (t(n, "title", lang) or key, f"stories/{lang}/{key}.html")])]))
        count += 1
    return count


def write_story_listing(cfg: dict, days: int = 30) -> None:
    index = load_story_index()
    cutoff = (dt.datetime.now(UTC) - dt.timedelta(days=days)).strftime("%Y-%m-%d")
    recent = sorted((e for e in index.values() if str(e.get("last_seen", ""))[:10] >= cutoff), key=lambda e: (e.get("last_seen", ""), e.get("share", 0)), reverse=True)
    for lang in LANGS:
        w, other = W[lang], "ar" if lang == "en" else "en"
        by_day = defaultdict(list)
        for e in recent:
            by_day[str(e["last_seen"])[:10]].append(e)
        parts = [f"<h1>{w['listing']}</h1><p class=\"sub\">{esc(w['listingSub'])}</p>"]
        for day in sorted(by_day, reverse=True):
            items = "".join(
                f"""<li><a href="{esc(k)}.html">{esc(e['title_ar'] if lang == 'ar' and e.get('title_ar') else e['title'])}</a>
<span class="meta">{esc(theme_label(cfg, e.get('theme', 'other'), lang))} · {w['people']}: {esc(tone_label(e.get('public_sentiment'), lang))} · {w['outlets']}: {esc(tone_label(e.get('sentiment'), lang))} · {w['seenIn']} {num(int(e.get('runs') or 1), lang)} {w['updates']}</span></li>"""
                for k, e in ((archive_key(e), e) for e in by_day[day]))
            parts.append(f"<p class=\"day\">{esc(fmt_date(day, lang))}</p><ul class=\"list\">{items}</ul>")
        write(STORIES / lang / "index.html", page(cfg, lang, w["listing"], w["listingSub"], "\n".join(parts), f"stories/{lang}/index.html", f"stories/{other}/index.html", kind="website"))


def archive_key(e: dict) -> str:
    return f"{str(e.get('first_seen', ''))[:10]}-{e['id']}"


# ----------------------------------------------------------------- weekly digest pages and feeds

def weekly_body(cfg: dict, d: dict, lang: str) -> str:
    w, s = W[lang], d.get("stats") or {}
    paras = d.get("paragraphs_ar" if lang == "ar" else "paragraphs") or d.get("paragraphs") or []
    parts = ['<article class="report">',
             f"<p class=\"eyebrow\"><a href=\"index.html\">{w['digests']}</a> · {w['week']} {esc(d['week'])} · {esc(fmt_date(d['from'], lang))} – {esc(fmt_date(d['to'], lang))}</p>",
             f"<h1>{esc(t(d, 'title', lang))}</h1>",
             f"<p class=\"sub rmeta\">{esc(site_title(cfg, lang))} · {esc(fmt_date(d['from'], lang))} – {esc(fmt_date(d['to'], lang))} · <span dir=\"ltr\">{esc(site_url(cfg).replace('https://', ''))}</span></p>",
             share_bar(cfg, lang, f"weekly/{lang}/{d['week']}.html", f"{t(d, 'title', lang)}, {w['week']} {d['week']}",
                       pdf=f"{d['week']}.pdf", feed="feed-ar.xml" if lang == "ar" else "feed.xml",
                       tags=hashtags.select(cfg, lang, [x["theme"] for x in sorted(s.get("themes") or [], key=lambda x: -x.get("share", 0))],
                                            [t(d, "title", lang)] + [t(h, "title", lang) for h in d.get("highlights") or []])),
             '<section class="analysis">' + "".join(f"<p>{esc(p)}</p>" for p in paras) + "</section>"]
    hl = d.get("highlights") or []
    if hl:
        items = []
        for h in hl:
            key = h.get("key") or ""
            title = esc(t(h, "title", lang))
            link = f'<a href="../../stories/{lang}/{esc(key)}.html">{title}</a>' if key else title
            items.append(f"<li><b>{link}</b>{(' — ' if lang == 'en' else ' ـ ')}{esc(t(h, 'why', lang))}</li>")
        parts.append(f"<h2>{w['highlights']}</h2><ul>{''.join(items)}</ul>")
    watch = d.get("watch_ar" if lang == "ar" else "watch") or []
    if watch:
        parts.append(f"<h2>{w['watchNext']}</h2><ul>" + "".join(f"<li>{esc(x)}</li>" for x in watch) + "</ul>")
    themes = s.get("themes") or []
    if themes:
        mx = max([x.get("share", 0) for x in themes] + [0.05])
        rows = "".join(f"""<tr><td>{esc(theme_label(cfg, x['theme'], lang))}</td><td><div class="bar"><i style="width:{round(x.get('share', 0) / mx * 100)}%"></i></div></td>
<td class="n">{pct(x.get('share', 0), lang)}{(' <span class="sub">(' + pts(x['change'], lang) + ')</span>') if x.get('change') is not None else ''}</td>
<td class="n">{signed(x['public_sentiment'], lang) if x.get('public_sentiment') is not None else '–'}</td><td class="n">{signed(x['outlet_sentiment'], lang) if x.get('outlet_sentiment') is not None else '–'}</td><td class="n">{num(int(x.get('stories') or 0), lang)}</td></tr>"""
                       for x in themes)
        parts.append(f"<h2>{w['themeTable']}</h2><div class=\"tw\"><table><thead><tr><th>{w['theme']}</th><th></th><th>{w['share']}</th><th>{w['people']}</th><th>{w['outlets']}</th><th>{w['stories']}</th></tr></thead><tbody>{rows}</tbody></table></div>")
    days = s.get("days") or []
    if days:
        rows = "".join(f"<tr><td class=\"n\">{esc(fmt_date(x['date'], lang))}</td><td class=\"n\">{signed(x['public_sentiment'], lang) if x.get('public_sentiment') is not None else '–'}</td>"
                       f"<td class=\"n\">{signed(x['outlet_sentiment'], lang) if x.get('outlet_sentiment') is not None else '–'}</td><td class=\"n\">{num(int(x.get('posts') or 0), lang)}</td></tr>" for x in days)
        parts.append(f"<h2>{w['dailyTone']}</h2><div class=\"tw\"><table><thead><tr><th></th><th>{w['people']}</th><th>{w['outlets']}</th><th>{w['posts']}</th></tr></thead><tbody>{rows}</tbody></table></div>")
        parts.append(f"<p class=\"sub\">{esc(w['postsNote'].format(n=num(int(cfg.get('max_posts') or 300), lang), h=num(int(cfg.get('window_hours') or 24), lang)))}</p>")
    parts.append(expert_link(lang, f"{d['week']}.html", w["xWeek"]))
    parts.append(f"<p class=\"sub\">{esc(w['note'])}</p></article>")
    return "\n".join(parts)


def write_weekly_pages(cfg: dict, digest: dict) -> None:
    for lang in LANGS:
        other = "ar" if lang == "en" else "en"
        desc = (digest.get("paragraphs_ar" if lang == "ar" else "paragraphs") or [""])[0][:200]
        write(WEEKLY / lang / f"{digest['week']}.html",
              page(cfg, lang, str(t(digest, "title", lang)), desc, weekly_body(cfg, digest, lang),
                   f"weekly/{lang}/{digest['week']}.html", f"weekly/{other}/{digest['week']}.html", updated=digest.get("generated_at"),
                   jsonld=[ld_article(cfg, lang, "Report", t(digest, "title", lang), desc, f"weekly/{lang}/{digest['week']}.html", digest.get("generated_at", ""), digest.get("generated_at", "")),
                           ld_breadcrumbs(cfg, lang, [(W[lang]["digests"], f"weekly/{lang}/index.html"), (t(digest, "title", lang), f"weekly/{lang}/{digest['week']}.html")])]))


def write_weekly_listing(cfg: dict, digests: list) -> None:
    for lang in LANGS:
        w, other = W[lang], "ar" if lang == "en" else "en"
        items = "".join(f"""<li><a href="{esc(d['week'])}.html">{esc(d['title_ar'] if lang == 'ar' and d.get('title_ar') else d['title'])}</a>
<span class="meta">{esc(fmt_date(d['from'], lang))} – {esc(fmt_date(d['to'], lang))} · <a href="{esc(d['week'])}.pdf">{w['pdf']}</a></span></li>""" for d in sorted(digests, key=lambda d: d["week"], reverse=True))
        write(WEEKLY / lang / "index.html", page(cfg, lang, w["digests"], w["feedDesc"], f"<h1>{w['digests']}</h1><ul class=\"list\">{items}</ul>",
                                                 f"weekly/{lang}/index.html", f"weekly/{other}/index.html", kind="website"))


def write_feeds(cfg: dict, digests: list) -> None:
    base = site_url(cfg)
    for lang in LANGS:
        w = W[lang]
        items = []
        for d in sorted(digests, key=lambda d: d["week"], reverse=True)[:52]:
            link = f"{base}/weekly/{lang}/{d['week']}.html"
            paras = d.get("paragraphs_ar" if lang == "ar" else "paragraphs") or []
            pub = archive_parse(d.get("generated_at") or d["to"]) or dt.datetime.now(UTC)
            items.append(f"""<item><title>{esc(d['title_ar'] if lang == 'ar' and d.get('title_ar') else d['title'])}</title><link>{esc(link)}</link><guid isPermaLink="true">{esc(link)}</guid>
<pubDate>{pub.strftime('%a, %d %b %Y %H:%M:%S +0000')}</pubDate><description>{esc(' '.join(paras)[:1500])}</description></item>""")
        xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom"><channel><title>{esc(w['feedTitle'])}</title><link>{esc(base + '/')}</link><image><url>{esc(base + '/assets/logo-144.png')}</url><title>{esc(w['feedTitle'])}</title><link>{esc(base + '/')}</link></image>
<description>{esc(w['feedDesc'])}</description><language>{lang}</language><atom:link href="{esc(base + '/' + ('feed-ar.xml' if lang == 'ar' else 'feed.xml'))}" rel="self" type="application/rss+xml"/>
{''.join(items)}</channel></rss>
"""
        write(ROOT / ("feed-ar.xml" if lang == "ar" else "feed.xml"), xml)


# ----------------------------------------------------------------- monthly review pages and feeds

def fmt_month(month: str, lang: str) -> str:
    y, m = int(month[:4]), int(month[5:7])
    return ar_digits(f"{MONTHS_AR[m - 1]} {y}") if lang == "ar" else f"{MONTHS_EN[m - 1]} {y}"


def subscribe_link(cfg: dict, lang: str) -> str:
    url = str(cfg.get("newsletter_url") or "").strip()
    return f'<p><a class="chip" href="{esc(url)}" rel="noopener">{W[lang]["subscribe"]}</a></p>' if url.startswith("https://") else ""


def monthly_sections(cfg: dict, d: dict, lang: str, base: str = "../../", absolute: str = "") -> list:
    """The report's text sections as HTML; absolute links when a site address is given (for the feeds)."""
    w, s = W[lang], d.get("stats") or {}
    root = absolute + "/" if absolute else base
    parts = []
    findings = d.get("key_findings_ar" if lang == "ar" else "key_findings") or d.get("key_findings") or []
    if findings:
        parts.append(f"<section class=\"findings\"><h2>{w['keyFindings']}</h2><ol>" + "".join(f"<li>{esc(x)}</li>" for x in findings) + "</ol></section>")
    paras = d.get("paragraphs_ar" if lang == "ar" else "paragraphs") or d.get("paragraphs") or []
    parts.append(f"<section class=\"analysis\"><h2>{w['analysis']}</h2>" + "".join(f"<p>{esc(p)}</p>" for p in paras) + "</section>")
    hl = d.get("highlights") or []
    if hl:
        items = []
        for h in hl:
            key = h.get("key") or ""
            title = esc(t(h, "title", lang))
            link = f'<a href="{root}stories/{lang}/{esc(key)}.html">{title}</a>' if key else title
            items.append(f"<li><b>{link}</b>{(' — ' if lang == 'en' else ' ـ ')}{esc(t(h, 'why', lang))}</li>")
        parts.append(f"<section class=\"stories\"><h2>{w['monthHighlights']}</h2><ol>{''.join(items)}</ol></section>")
    watch = d.get("watch_ar" if lang == "ar" else "watch") or []
    if watch:
        parts.append(f"<section><h2>{w['watchMonth']}</h2><ul>" + "".join(f"<li>{esc(x)}</li>" for x in watch) + "</ul></section>")
    flagged = d.get("flagged") or []
    if flagged:
        import signals as SIG
        cat = {c["id"]: c for c in SIG.CATALOG}
        items = []
        for e in flagged:
            sig = e.get("signals") or {}
            names = ", ".join(cat[i["id"]]["label_ar" if lang == "ar" else "label"] if i["id"] in cat else i["id"] for i in sig.get("items") or [])
            items.append(f'<li><b><a href="{root}stories/{lang}/{esc(e["key"])}.html">{esc(t(e, "title", lang))}</a></b> '
                         f'<span class="sub">{w["level"]}: {w["sigLevels"].get(sig.get("level"), "")}; {esc(names)}</span></li>')
        parts.append(f"<section><h2>{w['flaggedTitle']}</h2><ul>{''.join(items)}</ul><p class=\"sub\">{esc(w['sigNote'])}</p></section>")
    digests = d.get("digests") or []
    if digests:
        items = []
        for x in digests:
            first = (x.get("paragraphs_ar" if lang == "ar" else "paragraphs") or x.get("paragraphs") or [""])[0]
            text = ('<span class="wk-text"><br>' + esc(first) + "</span>") if first else ""
            items.append(f'<li><b><a href="{root}weekly/{lang}/{esc(x["week"])}.html">{esc(t(x, "title", lang))}</a></b> '
                         f'<span class="sub">{esc(fmt_date(x.get("from", ""), lang))} – {esc(fmt_date(x.get("to", ""), lang))}</span>{text}</li>')
        parts.append(f"<section class=\"weeks\"><h2>{w['weeksBrief']}</h2><ul>{''.join(items)}</ul></section>")
    themes = s.get("themes") or []
    if themes:
        mx = max([x.get("share", 0) for x in themes] + [0.05])
        rows = "".join(f"""<tr><td>{esc(theme_label(cfg, x['theme'], lang))}</td><td><div class="bar"><i style="width:{round(x.get('share', 0) / mx * 100)}%"></i></div></td>
<td class="n">{pct(x.get('share', 0), lang)}{(' <span class="sub">(' + pts(x['change'], lang) + ')</span>') if x.get('change') is not None else ''}</td>
<td class="n">{signed(x['public_sentiment'], lang) if x.get('public_sentiment') is not None else '–'}</td><td class="n">{signed(x['outlet_sentiment'], lang) if x.get('outlet_sentiment') is not None else '–'}</td><td class="n">{num(int(x.get('stories') or 0), lang)}</td></tr>"""
                       for x in themes)
        change_note = f" <span class=\"sub\">({w['vsLastMonth']})</span>" if any(x.get("change") is not None for x in themes) else ""
        parts.append(f"<section><h2>{w['themeTableMonth']}</h2><div class=\"tw\"><table><thead><tr><th>{w['theme']}</th><th></th><th>{w['share']}{change_note}</th><th>{w['people']}</th><th>{w['outlets']}</th><th>{w['stories']}</th></tr></thead><tbody>{rows}</tbody></table></div></section>")
    weeks = s.get("weeks") or []
    if weeks:
        rows = "".join(f"<tr><td class=\"n\">{esc(x['week'])}</td><td class=\"n\">{esc(fmt_date(x['from'], lang))} – {esc(fmt_date(x['to'], lang))}</td>"
                       f"<td class=\"n\">{signed(x['public_sentiment'], lang) if x.get('public_sentiment') is not None else '–'}</td>"
                       f"<td class=\"n\">{signed(x['outlet_sentiment'], lang) if x.get('outlet_sentiment') is not None else '–'}</td><td class=\"n\">{num(int(x.get('posts') or 0), lang)}</td></tr>" for x in weeks)
        parts.append(f"<section class=\"print-hide\"><h2>{w['weeklyTone']}</h2><div class=\"tw\"><table><thead><tr><th>{w['weekCol']}</th><th>{w['daysCol']}</th><th>{w['people']}</th><th>{w['outlets']}</th><th>{w['posts']}</th></tr></thead><tbody>{rows}</tbody></table></div>"
                     f"<p class=\"sub\">{esc(w['postsNote'].format(n=num(int(cfg.get('max_posts') or 300), lang), h=num(int(cfg.get('window_hours') or 24), lang)))}</p></section>")
    return parts


def svg_theme_bars(cfg: dict, themes: list, lang: str) -> str:
    """Share of discussion by theme as a horizontal bar chart (inline SVG: prints and scales)."""
    rows = [x for x in themes if x.get("share", 0) > 0][:10]
    if not rows:
        return ""
    width, lab, bar_h, gap, top = 640, 268, 16, 10, 4
    mx = max(x["share"] for x in rows) or 0.05
    height = top + len(rows) * (bar_h + gap)
    rtl = lang == "ar"   # mirrored for Arabic: labels on the right, bars growing leftwards; the SVG itself stays LTR so anchors behave
    out = [f'<svg viewBox="0 0 {width} {height}" width="100%" role="img" aria-label="{esc(W[lang]["chartThemes"])}" style="direction:ltr">']
    for i, x in enumerate(rows):
        y = top + i * (bar_h + gap)
        wbar = max(2.0, x["share"] / mx * (width - lab - 100))
        change = f" ({pts(x['change'], lang)})" if x.get("change") is not None else ""
        label, value = esc(theme_label(cfg, x["theme"], lang)), f"{pct(x['share'], lang)}{esc(change)}"
        if rtl:
            out.append(f'<text x="{width - lab + 10}" y="{y + bar_h - 3}" text-anchor="start" font-size="12" fill="currentColor">{label}</text>'
                       f'<rect x="{width - lab - wbar:.1f}" y="{y}" width="{wbar:.1f}" height="{bar_h}" rx="3" style="fill:var(--brass);opacity:.85"/>'
                       f'<text x="{width - lab - wbar - 8:.1f}" y="{y + bar_h - 3}" text-anchor="end" font-size="12" fill="currentColor" opacity=".8">{value}</text>')
        else:
            out.append(f'<text x="{lab - 10}" y="{y + bar_h - 3}" text-anchor="end" font-size="12" fill="currentColor">{label}</text>'
                       f'<rect x="{lab}" y="{y}" width="{wbar:.1f}" height="{bar_h}" rx="3" style="fill:var(--brass);opacity:.85"/>'
                       f'<text x="{lab + wbar + 8:.1f}" y="{y + bar_h - 3}" font-size="12" fill="currentColor" opacity=".8">{value}</text>')
    return "".join(out) + "</svg>"


def svg_tone_weeks(weeks: list, lang: str) -> str:
    """People's and outlets' tone by week as a two-line chart on the -1 to +1 scale (inline SVG)."""
    pts_ = [x for x in weeks if x.get("public_sentiment") is not None or x.get("outlet_sentiment") is not None]
    if len(pts_) < 2:
        return ""
    width, height, left, right, top, bottom = 640, 230, 46, 96, 12, 36
    w_ = W[lang]
    n = len(pts_)
    x_of = lambda i: left + i * (width - left - right) / (n - 1)
    y_of = lambda v: top + (1 - (max(-1.0, min(1.0, v)) + 1) / 2) * (height - top - bottom)
    out = [f'<svg viewBox="0 0 {width} {height}" width="100%" role="img" aria-label="{esc(w_["chartTone"])}" style="direction:ltr">']
    for v in (-1, -0.5, 0, 0.5, 1):
        y = y_of(v)
        out.append(f'<line x1="{left}" x2="{width - right}" y1="{y:.1f}" y2="{y:.1f}" stroke="currentColor" stroke-opacity="{0.35 if v == 0 else 0.12}" stroke-width="1"/>'
                   f'<text x="{left - 8}" y="{y + 4:.1f}" text-anchor="end" font-size="11" fill="currentColor" opacity=".7">{signed(v, lang) if v else "0"}</text>')
    for i, x in enumerate(pts_):
        out.append(f'<text x="{x_of(i):.1f}" y="{height - 12}" text-anchor="middle" font-size="11" fill="currentColor" opacity=".8">{esc(x["week"][5:] if lang != "ar" else ar_digits(x["week"][6:]))}</text>')
    for key, style, label in (("public_sentiment", "stroke:currentColor", w_["people"]), ("outlet_sentiment", "stroke:var(--brass)", w_["outlets"])):
        pts_xy = [(x_of(i), y_of(x[key])) for i, x in enumerate(pts_) if x.get(key) is not None]
        if not pts_xy:
            continue
        out.append(f'<polyline points="{" ".join(f"{px:.1f},{py:.1f}" for px, py in pts_xy)}" fill="none" style="{style};stroke-width:2.5" stroke-linejoin="round"/>')
        out += [f'<circle cx="{px:.1f}" cy="{py:.1f}" r="4" style="fill:{"currentColor" if "currentColor" in style else "var(--brass)"}"/>' for px, py in pts_xy]
        px, py = pts_xy[-1]
        out.append(f'<text x="{px + 9:.1f}" y="{py + 4:.1f}" font-size="12" fill="currentColor">{esc(label)}</text>')
    return "".join(out) + "</svg>"


def kpi_tiles(cfg: dict, d: dict, lang: str) -> str:
    w, s = W[lang], d.get("stats") or {}
    def delta(cur, prev):
        if cur is None or prev is None:
            return ""
        return f'<span class="delta">{signed(cur - prev, lang)} {w["vsPrev"]}</span>'
    def label(v):
        return esc(tone_label(v, lang)) if v is not None else "–"
    tiles = [(label(s.get("public_sentiment")), f"{w['peopleTone']} ({signed(s['public_sentiment'], lang)})" if s.get("public_sentiment") is not None else w["peopleTone"], delta(s.get("public_sentiment"), s.get("prev_public_sentiment"))),
             (label(s.get("outlet_sentiment")), f"{w['outletTone']} ({signed(s['outlet_sentiment'], lang)})" if s.get("outlet_sentiment") is not None else w["outletTone"], delta(s.get("outlet_sentiment"), s.get("prev_outlet_sentiment"))),
             (num(int(s.get("stories_total") or 0), lang), w["storiesN"], ""), (num(int(s.get("posts") or 0), lang), w["postIdx"], ""),
             (num(int(s.get("runs") or 0), lang), w["updatesN"], ""), (num(int(s.get("days") or 0), lang), w["daysN"], "")]
    return '<div class="kpis">' + "".join(f"<div class=\"kpi\"><b>{v}</b><span>{lbl}</span>{dl}</div>" for v, lbl, dl in tiles) + "</div>"


def share_bar(cfg: dict, lang: str, path: str, title: str, pdf: str | None = None, feed: str | None = None, tags: list | None = None) -> str:
    """Share links for a page: PDF (when one exists), X, Facebook, Telegram, WhatsApp, the newsletter and a feed.
    tags: hashtags without '#', most relevant first, for X (as many as fit the post), Facebook (the first) and Telegram."""
    import urllib.parse as up
    w, base = W[lang], site_url(cfg)
    url = f"{base}/{path}"
    text = f"{title} — {site_title(cfg, lang)}"
    q = up.quote
    tags = hashtags.fit(tags or [], text)
    x = f"https://twitter.com/intent/tweet?text={q(text)}&amp;url={q(url)}" + (f"&amp;hashtags={q(','.join(tags))}" if tags else "")
    fb = f"https://www.facebook.com/sharer/sharer.php?u={q(url)}" + (f"&amp;hashtag={q('#' + tags[0])}" if tags else "")
    tg = text + ("\n" + " ".join("#" + tag for tag in tags) if tags else "")
    links = ([f'<a class="pdf" href="{esc(pdf)}" download>{w["pdf"]}</a>'] if pdf else []) + [
        f'<a href="{x}" rel="noopener">X</a>',
        f'<a href="{fb}" rel="noopener">Facebook</a>',
        f'<a href="https://t.me/share/url?url={q(url)}&amp;text={q(tg)}" rel="noopener">Telegram</a>',
        f'<a href="https://wa.me/?text={q(text + " " + url)}" rel="noopener">WhatsApp</a>']
    nl = str(cfg.get("newsletter_url") or "").strip()
    if nl.startswith("https://"):
        links.append(f'<a href="{esc(nl)}" rel="noopener">{w["subscribe"]}</a>')
    if feed:
        links.append(f'<a href="../../{esc(feed)}">RSS</a>')
    return f'<div class="share" aria-label="{w["shareIt"]}"><span class="sub">{w["shareIt"]}:</span>{"".join(links)}</div>'


def about_report(cfg: dict, d: dict, lang: str) -> str:
    w, s, base = W[lang], d.get("stats") or {}, site_url(cfg)
    n_sources = len(archive.source_catalog(cfg))
    where = ", ".join(f"{W[lang]['platformNames'].get(k, k)} {pct(v, lang)}" for k, v in list((s.get("platforms") or {}).items())[:6])
    langs = ", ".join(f"{W[lang]['langNames'].get(k, k)} {pct(v, lang)}" for k, v in (s.get("languages") or {}).items() if v >= 0.005)
    method = w["methodText"].format(posts=num(int(s.get("posts") or 0), lang), days=num(int(s.get("days") or 0), lang), sources=num(n_sources, lang), model=esc(d.get("model") or cfg.get("model") or ""))
    url = f"{base}/monthly/{lang}/{d['month']}.html"
    cite = w["citeText"].format(site=esc(site_title(cfg, lang)), year=d["month"][:4], month=esc(fmt_month(d["month"], lang)), url=esc(url))
    return (f'<section class="about-report"><h2>{w["aboutReport"]}</h2><p>{method}</p>'
            f'<p>{w["fromWhere"]}: {esc(where) or "–"}. {w["langsLbl"]}: {esc(langs) or "–"}.</p>'
            f'<p><a href="{esc(base)}/{"ar/" if lang == "ar" else ""}#about">{w["methodLink"]}</a> · {w["licence"]} · {w["generatedOn"]} {esc(fmt_date(d.get("generated_at", ""), lang, True))}</p>'
            f'<p>{w["cite"]}: {cite}</p></section>')


def monthly_body(cfg: dict, d: dict, lang: str) -> str:
    w, s = W[lang], d.get("stats") or {}
    base = site_url(cfg)
    head = [f"<p class=\"eyebrow\"><a href=\"index.html\">{w['reviews']}</a> · {w['reportLabel']} · {esc(fmt_month(d['month'], lang))}</p>",
            f"<h1>{esc(t(d, 'title', lang))}</h1>",
            f"<p class=\"sub rmeta\">{esc(site_title(cfg, lang))} · {esc(fmt_date(d['from'], lang))} – {esc(fmt_date(d['to'], lang))} · <span dir=\"ltr\">{esc(base.replace('https://', ''))}</span></p>",
            share_bar(cfg, lang, f"monthly/{lang}/{d['month']}.html", f"{t(d, 'title', lang)}, {fmt_month(d['month'], lang)}",
                      pdf=f"{d['month']}.pdf", feed="feed-monthly-ar.xml" if lang == "ar" else "feed-monthly.xml",
                      tags=hashtags.select(cfg, lang, [x["theme"] for x in sorted(s.get("themes") or [], key=lambda x: -x.get("share", 0))],
                                           [t(d, "title", lang)] + [t(h, "title", lang) for h in d.get("highlights") or []]))]
    charts = []
    bars = svg_theme_bars(cfg, s.get("themes") or [], lang)
    if bars:
        charts.append(f'<figure><figcaption>{w["chartThemes"]}</figcaption>{bars}</figure>')
    lines = svg_tone_weeks(s.get("weeks") or [], lang)
    if lines:
        charts.append(f'<figure><figcaption>{w["chartTone"]}</figcaption>{lines}<p class="legend"><span><i></i>{w["people"]}</span><span><i class="b"></i>{w["outlets"]}</span></p></figure>')
    sections = monthly_sections(cfg, d, lang)
    numbers = f'<section class="numbers"><h2>{w["inNumbers"]}</h2>{kpi_tiles(cfg, d, lang)}' + (f'<div class="charts">{"".join(charts)}</div>' if charts else "") + "</section>"
    body = sections[:1] + [numbers] + sections[1:] if sections and 'class="findings"' in sections[0] else [numbers] + sections
    return "\n".join(['<article class="report">'] + head + body + [about_report(cfg, d, lang), "</article>"])


def monthly_email_html(cfg: dict, d: dict, lang: str) -> str:
    """The whole review as self-contained HTML with absolute links, for the feed item (newsletter services send it as is)."""
    base, w = site_url(cfg), W[lang]
    link = f"{base}/monthly/{lang}/{d['month']}.html"
    body = "\n".join(monthly_sections(cfg, d, lang, absolute=base))
    body = body.replace('<div class="tw">', "").replace("</table></div>", "</table>")   # no scroll wrappers in email
    body = re.sub(r'<td><div class="bar">.*?</div></td>', "", body).replace("<th></th>", "")   # the bar column needs CSS; email clients have none
    body = body.replace("<table>", '<table cellpadding="6" style="border-collapse:collapse;font-size:14px">').replace("<th>", '<th align="left">')
    return (f'<div dir="{"rtl" if lang == "ar" else "ltr"}" lang="{lang}" style="font-family:system-ui,sans-serif;line-height:1.6">'
            f'<p style="color:#45413A;font-size:14px"><img src="{esc(base + "/assets/logo-144.png")}" width="24" height="24" alt="" style="vertical-align:middle;border-radius:5px;margin-{"left" if lang == "ar" else "right"}:8px">{esc(site_title(cfg, lang))} · {esc(fmt_month(d["month"], lang))} · <a href="{esc(link)}">{w["readOnline"]}</a></p>'
            f'<h1 style="font-size:24px;line-height:1.3">{esc(t(d, "title", lang))}</h1>{body}'
            f'<p style="color:#45413A;font-size:13px"><a href="{esc(base)}/">{esc(site_title(cfg, lang))}</a> · {esc(w["footer"])}</p></div>')


def write_monthly_pages(cfg: dict, review: dict) -> None:
    for lang in LANGS:
        other = "ar" if lang == "en" else "en"
        desc = (review.get("paragraphs_ar" if lang == "ar" else "paragraphs") or [""])[0][:200]
        write(MONTHLY / lang / f"{review['month']}.html",
              page(cfg, lang, str(t(review, "title", lang)), desc, monthly_body(cfg, review, lang),
                   f"monthly/{lang}/{review['month']}.html", f"monthly/{other}/{review['month']}.html", updated=review.get("generated_at"),
                   jsonld=[ld_article(cfg, lang, "Report", t(review, "title", lang), desc, f"monthly/{lang}/{review['month']}.html", review.get("generated_at", ""), review.get("generated_at", "")),
                           ld_breadcrumbs(cfg, lang, [(W[lang]["reviews"], f"monthly/{lang}/index.html"), (t(review, "title", lang), f"monthly/{lang}/{review['month']}.html")])]))


def write_monthly_listing(cfg: dict, reviews: list) -> None:
    for lang in LANGS:
        w, other = W[lang], "ar" if lang == "en" else "en"
        items = "".join(f"""<li><a href="{esc(d['month'])}.html">{esc(d['title_ar'] if lang == 'ar' and d.get('title_ar') else d['title'])}</a>
<span class="meta">{esc(fmt_month(d['month'], lang))} · <a href="{esc(d['month'])}.pdf">{w['pdf']}</a></span></li>""" for d in sorted(reviews, key=lambda d: d["month"], reverse=True))
        feed = f'<p class="sub"><a href="../../{"feed-monthly-ar.xml" if lang == "ar" else "feed-monthly.xml"}">RSS</a></p>'
        write(MONTHLY / lang / "index.html", page(cfg, lang, w["reviews"], w["feedDescMonthly"],
                                                  f"<h1>{w['reviews']}</h1><p class=\"sub\">{esc(w['feedDescMonthly'])}</p>{subscribe_link(cfg, lang)}<ul class=\"list\">{items}</ul>{feed}",
                                                  f"monthly/{lang}/index.html", f"monthly/{other}/index.html", kind="website"))


def write_monthly_feeds(cfg: dict, reviews: list) -> None:
    """RSS with the full review in each item (content:encoded), so an RSS-to-email service can send it as a newsletter."""
    base = site_url(cfg)
    for lang in LANGS:
        w = W[lang]
        items = []
        for x in sorted(reviews, key=lambda d: d["month"], reverse=True)[:24]:
            d = archive._load(MONTHLY_DATA_DIR / f"{x['month']}.json", None) or x
            link = f"{base}/monthly/{lang}/{x['month']}.html"
            paras = d.get("paragraphs_ar" if lang == "ar" else "paragraphs") or []
            pub = archive_parse(x.get("generated_at") or x["to"]) or dt.datetime.now(UTC)
            full = monthly_email_html(cfg, d, lang) if d.get("stats") else " ".join(f"<p>{esc(p)}</p>" for p in paras)
            items.append(f"""<item><title>{esc(x['title_ar'] if lang == 'ar' and x.get('title_ar') else x['title'])}</title><link>{esc(link)}</link><guid isPermaLink="true">{esc(link)}</guid>
<pubDate>{pub.strftime('%a, %d %b %Y %H:%M:%S +0000')}</pubDate><description>{esc(' '.join(paras[:2])[:1500])}</description>
<content:encoded><![CDATA[{full.replace(']]>', ']]&gt;')}]]></content:encoded></item>""")
        name = "feed-monthly-ar.xml" if lang == "ar" else "feed-monthly.xml"
        xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom" xmlns:content="http://purl.org/rss/1.0/modules/content/"><channel><title>{esc(w['feedTitleMonthly'])}</title><link>{esc(base + '/')}</link><image><url>{esc(base + '/assets/logo-144.png')}</url><title>{esc(w['feedTitleMonthly'])}</title><link>{esc(base + '/')}</link></image>
<description>{esc(w['feedDescMonthly'])}</description><language>{lang}</language><atom:link href="{esc(base + '/' + name)}" rel="self" type="application/rss+xml"/>
{''.join(items)}</channel></rss>
"""
        write(ROOT / name, xml)


MONTHLY_DATA_DIR = DATA / "monthly"


def load_reviews() -> list:
    return archive._load(MONTHLY_DATA_DIR / "index.json", [])


# ----------------------------------------------------------------- daily briefs

DAILY = ROOT / "daily"


def daily_summary(cfg: dict, day: dict) -> dict | None:
    """What a day's page needs, from the archived runs of that day: the last update's brief, the day's stories
    (each with its last analysis), tone, volume and theme shares."""
    runs = [r for r in day.get("runs") or [] if r.get("narratives")]
    if not runs:
        return None
    last = runs[-1]
    stories: dict = {}
    for r in runs:
        for n in r.get("narratives") or []:
            key = n.get("key") or archive.story_key(n)
            e = stories.setdefault(key, {"key": key, "runs": 0, "max_share": 0.0})
            e.update(n); e["key"] = key
            e["runs"] += 1
            e["max_share"] = max(e["max_share"], float(n.get("share") or 0))
    pub = archive._mean([((r.get("overall") or {}).get("public_sentiment"), (r.get("stats") or {}).get("public_posts") or 1) for r in runs])
    out = archive._mean([((r.get("overall") or {}).get("sentiment"), (r.get("stats") or {}).get("outlet_posts") or 1) for r in runs])
    themes: dict = {}
    for r in runs:
        for n in r.get("narratives") or []:
            themes[n.get("theme") or "other"] = themes.get(n.get("theme") or "other", 0) + float(n.get("share") or 0) / len(runs)
    theme_rows = sorted([{"theme": k, "share": round(v, 3)} for k, v in themes.items() if v > 0], key=lambda x: x["share"], reverse=True)
    return {"date": day["date"], "last": last, "overall": last.get("overall") or {}, "runs": len(runs),
            "posts": sum(int((r.get("stats") or {}).get("posts_analyzed") or 0) for r in runs),
            "public_sentiment": pub, "outlet_sentiment": out, "themes": theme_rows,
            "stories": sorted(stories.values(), key=lambda e: (e["max_share"], e["runs"]), reverse=True)}


def daily_body(cfg: dict, s: dict, lang: str) -> str:
    w, ov = W[lang], s["overall"]
    date = s["date"]
    title = f"{w['daily']} · {fmt_date(date, lang)}"
    mood = ov.get("public_mood_ar" if lang == "ar" else "public_mood") or ov.get("mood_ar" if lang == "ar" else "mood") or ""
    tiles = [(esc(tone_label(s["public_sentiment"], lang)), f"{w['peopleTone']}" + (f" ({signed(s['public_sentiment'], lang)})" if s["public_sentiment"] is not None else "")),
             (esc(tone_label(s["outlet_sentiment"], lang)), f"{w['outletTone']}" + (f" ({signed(s['outlet_sentiment'], lang)})" if s["outlet_sentiment"] is not None else "")),
             (num(len(s["stories"]), lang), w["storiesN"]), (num(int(s["posts"]), lang), w["postIdx"]), (num(int(s["runs"]), lang), w["updatesN"])]
    kpis = '<div class="kpis">' + "".join(f"<div class=\"kpi\"><b>{v}</b><span>{lbl}</span></div>" for v, lbl in tiles) + "</div>"
    bars = svg_theme_bars(cfg, s["themes"], lang)
    items = []
    for e in s["stories"]:
        p = e.get("public_sentiment")
        tone_txt = f"{w['people']} {signed(p, lang)} · " if p is not None else ""
        items.append(f'<li><b><a href="../../stories/{lang}/{esc(e["key"])}.html">{esc(t(e, "title", lang))}</a></b> '
                     f'<span class="sub">{esc(theme_label(cfg, e.get("theme", "other"), lang))} · {tone_txt}{w["outlets"]} {signed(e.get("sentiment") or 0, lang)} · {pct(e["max_share"], lang)}</span>'
                     f'<br>{esc(t(e, "summary", lang))}</li>')
    parts = ['<article class="report">',
             f"<p class=\"eyebrow\"><a href=\"index.html\">{w['dailies']}</a> · {esc(fmt_date(date, lang))}</p>",
             f"<h1>{esc(title)}</h1>",
             f"<p class=\"sub rmeta\">{esc(site_title(cfg, lang))} · {w['asOf']} {esc(fmt_date(s['last'].get('generated_at', ''), lang, True))}</p>",
             share_bar(cfg, lang, f"daily/{lang}/{date}.html", title,
                       tags=hashtags.select(cfg, lang, [x["theme"] for x in s["themes"]], [t(e, "title", lang) for e in s["stories"]])),
             f"<section class=\"findings\"><h2>{w['dailyMood']}</h2><p><strong>{esc(mood)}</strong> {esc(t(ov, 'brief', lang))}</p></section>",
             f"<section class=\"numbers\"><h2>{w['dayNumbers']}</h2>{kpis}" + (f'<div class="charts"><figure><figcaption>{w["chartThemes"]}</figcaption>{bars}</figure></div>' if bars else "") + "</section>",
             f"<section class=\"stories\"><h2>{w['storiesOfDay']}</h2><ol>{''.join(items)}</ol></section>",
             expert_link(lang, f"{date}.html", w["xDay"]),
             f"<p class=\"sub\">{esc(w['storyNote'])}</p></article>"]
    return "\n".join(parts)


def write_daily_pages(cfg: dict, dates: list) -> int:
    n = 0
    for date in dates:
        s = daily_summary(cfg, archive.load_day(date))
        if not s:
            continue
        for lang in LANGS:
            other = "ar" if lang == "en" else "en"
            desc = str(t(s["overall"], "brief", lang) or "")[:200]
            write(DAILY / lang / f"{date}.html", page(cfg, lang, f"{W[lang]['daily']} · {fmt_date(date, lang)}", desc, daily_body(cfg, s, lang),
                                                    f"daily/{lang}/{date}.html", f"daily/{other}/{date}.html", updated=s["last"].get("generated_at"),
                                                    jsonld=[ld_article(cfg, lang, "Article", f"{W[lang]['daily']} · {fmt_date(date, lang)}", desc, f"daily/{lang}/{date}.html",
                                                                       f"{date}T00:00:00Z", s["last"].get("generated_at", "")),
                                                            ld_breadcrumbs(cfg, lang, [(W[lang]["dailies"], f"daily/{lang}/index.html"), (fmt_date(date, lang), f"daily/{lang}/{date}.html")])]))
        n += 1
    return n


def write_daily_listing(cfg: dict) -> None:
    index = archive._load(archive.ARCHIVE / "index.json", {})
    days = [d for d in index.get("days") or [] if d.get("runs")]
    for lang in LANGS:
        w, other = W[lang], "ar" if lang == "en" else "en"
        items = []
        for d in sorted(days, key=lambda d: d["date"], reverse=True)[:90]:
            tone = f"{w['people']} {signed(d['public_sentiment'], lang)}" if d.get("public_sentiment") is not None else ""
            tone += (" · " if tone else "") + (f"{w['outlets']} {signed(d['outlet_sentiment'], lang)}" if d.get("outlet_sentiment") is not None else "")
            items.append(f"""<li><a href="{esc(d['date'])}.html">{esc(fmt_date(d['date'], lang))}</a><span class="meta">{tone} · {num(int(d.get('stories') or 0), lang)} {w['stories'].lower() if lang == 'en' else w['stories']}</span></li>""")
        write(DAILY / lang / "index.html", page(cfg, lang, w["dailies"], w["dailySub"],
                                                f"<h1>{w['dailies']}</h1><p class=\"sub\">{esc(w['dailySub'])}</p><ul class=\"list\">{''.join(items)}</ul>",
                                                f"daily/{lang}/index.html", f"daily/{other}/index.html", kind="website"))


# ----------------------------------------------------------------- sitemap, robots, prerender

def write_sitemap(cfg: dict, digests: list, reviews: list | None = None) -> None:
    base = site_url(cfg)
    if not base:
        return
    today = dt.datetime.now(UTC).strftime("%Y-%m-%d")
    urls = [(f"{base}/", today, "hourly", "1.0"), (f"{base}/ar/", today, "hourly", "1.0"),
            (f"{base}/stories/en/index.html", today, "daily", "0.7"), (f"{base}/stories/ar/index.html", today, "daily", "0.7"),
            (f"{base}/weekly/en/index.html", today, "weekly", "0.6"), (f"{base}/weekly/ar/index.html", today, "weekly", "0.6"),
            (f"{base}/monthly/en/index.html", today, "monthly", "0.6"), (f"{base}/monthly/ar/index.html", today, "monthly", "0.6")]
    story_index = load_story_index()
    for key, e in story_index.items():
        if not story_indexable(cfg, key, story_index):
            continue                                # seen in a single update: on the site, not offered to search engines
        for lang in LANGS:
            urls.append((f"{base}/stories/{lang}/{key}.html", str(e.get("last_seen", today))[:10], "daily", "0.6"))
    for d in digests:
        for lang in LANGS:
            urls.append((f"{base}/weekly/{lang}/{d['week']}.html", str(d.get("generated_at", today))[:10], "monthly", "0.6"))
    for d in reviews if reviews is not None else load_reviews():
        for lang in LANGS:
            urls.append((f"{base}/monthly/{lang}/{d['month']}.html", str(d.get("generated_at", today))[:10], "yearly", "0.7"))
    for lang in LANGS:
        urls.append((f"{base}/daily/{lang}/index.html", today, "daily", "0.5"))
    for date in archive.all_days():
        for lang in LANGS:
            if (DAILY / lang / f"{date}.html").exists():
                urls.append((f"{base}/daily/{lang}/{date}.html", date, "yearly", "0.4"))
    for lang in LANGS:
        urls.append((f"{base}/sources/{lang}.html", today, "monthly", "0.5"))
    import experts                                   # imported here: experts imports this module
    urls += experts.sitemap_urls(base)
    body = "".join(f"<url><loc>{esc(u)}</loc><lastmod>{m}</lastmod><changefreq>{c}</changefreq><priority>{p}</priority></url>\n" for u, m, c, p in urls[:49000])
    write(ROOT / "sitemap.xml", f'<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n{body}</urlset>\n')
    write(ROOT / "robots.txt", f"User-agent: *\nAllow: /\nSitemap: {base}/sitemap.xml\n")


def expert_prerender(lang: str) -> str:
    """The newest Expert view pages (daily brief, week, month) as plain links for the crawlable home block."""
    index = archive._load(archive.DATA / "experts" / "analyses" / "index.json", [])
    rows = []
    for kind in ("day", "week", "month"):
        x = max((y for y in index if y.get("kind") == kind), key=lambda y: y["from"], default=None)
        if not x:
            continue
        title = x.get("overall_title_ar" if lang == "ar" else "overall_title") or x.get("overall_title") or ""
        lede = x.get("overall_lede_ar" if lang == "ar" else "overall_lede") or ""
        rows.append(f'<li><a href="experts/{lang}/{esc(x["id"])}.html">{esc(title)}</a> {esc(lede)}</li>')
    return f"<h3>{W[lang]['expertsLatest']}</h3><ul>{''.join(rows)}</ul>" if rows else ""


def prerender_index(cfg: dict, latest: dict) -> bool:
    """Write the current analysis into index.html as plain HTML, for crawlers and link previews; the site's
    script replaces it on load. Returns whether index.html changed."""
    path = ROOT / "index.html"
    html_text = path.read_text(encoding="utf-8")
    start, end = "<!--prerender-->", "<!--/prerender-->"
    if start not in html_text or end not in html_text:
        return False
    ov = latest.get("overall") or {}
    sections = []
    for lang in LANGS:
        w = W[lang]
        items = []
        for n in latest.get("narratives") or []:
            key = n.get("key") or archive.story_key(n)
            items.append(f"<li><a href=\"stories/{lang}/{esc(key)}.html\">{esc(t(n, 'title', lang))}</a> {esc(t(n, 'summary', lang))}</li>")
        mood = ov.get("public_mood_ar" if lang == "ar" else "public_mood") or ov.get("mood_ar" if lang == "ar" else "mood") or ""
        xp = expert_prerender(lang)
        sections.append(f"""<section class="pre" lang="{lang}" dir="{'rtl' if lang == 'ar' else 'ltr'}"><h2>{w['prerender']} · {esc(fmt_date(latest.get('generated_at', ''), lang, True))}</h2>
<p><strong>{esc(mood)}</strong> {esc(t(ov, 'brief', lang))}</p><ul>{''.join(items)}</ul>{xp}<p><a href="stories/{lang}/index.html">{w['moreStories']}</a> · <a href="daily/{lang}/index.html">{w['dailies']}</a> · <a href="weekly/{lang}/index.html">{w['digests']}</a> · <a href="monthly/{lang}/index.html">{w['reviews']}</a> · <a href="experts/{lang}/index.html">{w['expertsTitle']}</a> · <a href="sources/{lang}.html">{w['sourcesTitle']}</a></p></section>""")
    block = start + "\n" + "\n".join(sections) + "\n" + end
    new = html_text[:html_text.index(start)] + block + html_text[html_text.index(end) + len(end):]
    j0, j1 = "<!--jsonld-->", "<!--/jsonld-->"
    if j0 in new and j1 in new:
        new = new[:new.index(j0)] + j0 + home_jsonld(cfg, "en") + j1 + new[new.index(j1) + len(j1):]
    changed = new != html_text
    if changed:
        path.write_text(new, encoding="utf-8")
    write_arabic_home(cfg, new)
    return changed


HOME_TEXT = {
    "en": {"title": "Syria Narrative Tracker – what Syrians are saying online, updated through the day",
           "desc": "What is being said about Syria online today: public posts in Arabic, Kurdish and English grouped into stories, "
                   "with how people and outlets are reacting. Daily briefs, weekly and monthly reports, open data."},
    "ar": {"title": "متتبّع السرديات السورية – ماذا يقول السوريون على الإنترنت اليوم، يتجدّد على مدار اليوم",
           "desc": "ما يُقال عن سوريا على الإنترنت اليوم: منشورات عامة بالعربية والكردية والإنجليزية مجمّعة في قصص، مع كيفية تفاعل "
                   "الناس ووسائل الإعلام معها. موجز يومي وتقارير أسبوعية وشهرية وبيانات مفتوحة."},
}


def home_jsonld(cfg: dict, lang: str) -> str:
    """WebSite, Organization and Dataset descriptions for the home page (the Dataset is what Google Dataset Search lists)."""
    base = site_url(cfg)
    idx = archive._load(DATA / "archive" / "index.json", {}) or {}
    first, last = idx.get("first_day", ""), idx.get("last_day", "")
    home = f"{base}/ar/" if lang == "ar" else f"{base}/"
    data = [
        {"@context": "https://schema.org", "@type": "WebSite", "name": site_title(cfg, lang), "url": home, "inLanguage": lang,
         "description": HOME_TEXT[lang]["desc"], "publisher": ld_publisher(cfg, lang)},
        {"@context": "https://schema.org", **ld_publisher(cfg, lang), "sameAs": [u for u in [str(cfg.get("doi") or "").strip()] if u.startswith("https://")]},
        {"@context": "https://schema.org", "@type": "Dataset", "name": "Syria Narrative Tracker: stories, themes and tone of online discussion about Syria",
         "alternateName": "متتبّع السرديات السورية",
         "description": "Stories found in public online discussion about Syria (Telegram, news sites, YouTube, Reddit, Bluesky, X), in Arabic, "
                        "Kurdish and English, with each story's theme, share of the discussion and the tone of people's and outlets' reactions, "
                        "updated several times a day since September 2026. Aggregates only: posts by individuals are never stored.",
         "url": f"{base}/#data", "keywords": ["Syria", "سوريا", "public opinion", "narratives", "social media", "sentiment", "disinformation", "Kurdish", "Arabic"],
         "license": "https://creativecommons.org/licenses/by/4.0/", "isAccessibleForFree": True, "creator": ld_publisher(cfg, "en"),
         "spatialCoverage": {"@type": "Place", "name": "Syria"}, "temporalCoverage": f"{first}/{last}" if first and last else None,
         "distribution": [{"@type": "DataDownload", "encodingFormat": "application/json", "contentUrl": f"{base}/data/archive/index.json"},
                          {"@type": "DataDownload", "encodingFormat": "application/json", "contentUrl": f"{base}/data/exports/index.json"}]},
    ]
    data[2] = {k: v for k, v in data[2].items() if v is not None}
    return "".join(ld_script(d) for d in data)


def write_arabic_home(cfg: dict, html_text: str) -> None:
    """ar/index.html: the same page with Arabic as its language, titles and description, and every relative link one
    level up. The site's script sees the /ar/ path, opens in Arabic and adjusts the links it writes."""
    base = site_url(cfg)
    a = html_text.replace('<html lang="en" dir="ltr">', '<html lang="ar" dir="rtl">', 1)
    a = re.sub(r'((?:href|src|content)=")(?!#|[a-z]+:|/|\.\./|data:)((?:assets|feed|site\.webmanifest|favicon\.ico|stories|daily|weekly|monthly|support|privacy|contact|experts|sources)[^"]*)"',
               lambda m: f'{m.group(1)}../{m.group(2)}"', a)
    en, ar = HOME_TEXT["en"], HOME_TEXT["ar"]
    a = a.replace(f"<title>{en['title']}</title>", f"<title>{ar['title']}</title>", 1)
    a = a.replace(f'<meta name="description" content="{esc(en["desc"])}">', f'<meta name="description" content="{esc(ar["desc"])}">', 1)
    a = a.replace(f'<link rel="canonical" href="{base}/">', f'<link rel="canonical" href="{base}/ar/">', 1)
    a = a.replace(f'<meta property="og:url" content="{base}/">', f'<meta property="og:url" content="{base}/ar/">', 1)
    a = a.replace(f'<meta property="og:title" content="{esc(en["title"])}">', f'<meta property="og:title" content="{esc(ar["title"])}">', 1)
    a = a.replace(f'<meta property="og:description" content="{esc(en["desc"])}">', f'<meta property="og:description" content="{esc(ar["desc"])}">', 1)
    a = a.replace(f'content="{base}/assets/og.png"', f'content="{base}/assets/og-ar.png"', 1)
    a = a.replace('<meta property="og:site_name" content="Syria Narrative Tracker">', f'<meta property="og:site_name" content="{esc(site_title(cfg, "ar"))}">', 1)
    j0, j1 = "<!--jsonld-->", "<!--/jsonld-->"
    if j0 in a and j1 in a:
        a = a[:a.index(j0)] + j0 + home_jsonld(cfg, "ar") + j1 + a[a.index(j1) + len(j1):]
    path = ROOT / "ar" / "index.html"
    if not path.exists() or path.read_text(encoding="utf-8") != a:
        write(path, a)


def load_digests() -> list:
    return archive._load(DATA / "weekly" / "index.json", [])


PRIVACY_UPDATED = "2026-10-15"


def privacy_body(cfg: dict, lang: str) -> str:
    contact = str(cfg.get("contact_url") or "").strip()
    c = f'<a href="{esc(contact)}" rel="noopener">{esc(contact.replace("https://", ""))}</a>' if contact.startswith("https://") else ""
    if contact_key(cfg):   # the contact form is set up: send people there rather than to a public page
        c = f'<a href="../contact/{lang}.html">{"صفحة «اتصل بنا»" if lang == "ar" else "the Contact page"}</a>'
    gh, cf = "https://docs.github.com/site-policy/privacy-policies/github-general-privacy-statement", "https://www.cloudflare.com/privacypolicy/"
    if lang == "ar":
        sections = [
            ("هذا الموقع", f"لا يستخدم الموقع ملفات تعريف الارتباط (الكوكيز)، ولا أدوات تحليل أو تتبّع، ولا حسابات، ولا يجمع أي معلومات عن زوّاره. إذا راسلتنا عبر صفحة «اتصل بنا»، تُرسَل رسالتك واسمك وبريدك إلى فريق المتتبّع بالبريد الإلكتروني عبر خدمة Web3Forms؛ لا تُحفظ على الموقع ولا تُنشر، ونستخدمها للرد عليك فقط، ويمكنك أن تطلب حذفها في أي وقت. الموقع مستضاف على GitHub Pages ويُقدَّم عبر Cloudflare، ومثل أي خدمة استضافة تعالج هاتان الشركتان عناوين IP للزوار لعرض الصفحات والحماية من الهجمات، وفق سياسات الخصوصية الخاصة بهما (<a href=\"{gh}\" rel=\"noopener\">GitHub</a>، <a href=\"{cf}\" rel=\"noopener\">Cloudflare</a>)."),
            ("المنشورات العامة", "يقرأ المتتبّع منشورات عامة عن سوريا وينشر نتائج إجمالية فقط. لا تُخزَّن منشورات الأفراد ولا تُقتبس ولا يُربط إليها، ولا يُرسم ملف لأي شخص. لكشف التنسيق، تُحوَّل أسماء المعلّقين إلى بصمات أحادية الاتجاه لا توجد إلا في الذاكرة أثناء التحديث ولا تُحفظ أبداً."),
            ("حسابات التواصل الاجتماعي", "تنشر صفحة المتتبّع على فيسبوك تقارير الموقع نفسه تلقائياً عبر تطبيق فيسبوك. يستخدم التطبيق مديرو المتتبّع فقط للنشر على صفحة المتتبّع، ولا يسجّل دخول أحد، ولا يقرأ أو يجمع أو يخزّن أي بيانات عن مستخدمي فيسبوك، ولا يشارك شيئاً مع أي جهة."),
            ("حذف البيانات", "لا يحتفظ المتتبّع ولا تطبيقه على فيسبوك بأي بيانات شخصية عنك، فلا يوجد ما يُحذف. إذا سبق أن ربطت التطبيق بحسابك على فيسبوك، يمكنك إزالته من إعدادات فيسبوك ← التطبيقات والمواقع الإلكترونية ← إزالة." + (f" لأي سؤال أو طلب، تواصل معنا عبر {c}." if c else "")),
        ]
        head = f"<h1>الخصوصية</h1><p class=\"sub\">آخر تحديث: {esc(fmt_date(PRIVACY_UPDATED, lang))}</p>"
    else:
        sections = [
            ("This website", f"The site uses no cookies, no analytics or tracking and no accounts, and collects nothing about its visitors. If you write to us through the Contact page, your message, name and email are sent to the tracker's team by email through the Web3Forms service; they are not stored on the site or published, we use them only to reply, and you can ask us to delete them at any time. It is hosted on GitHub Pages and served through Cloudflare; like any web host, they process visitors' IP addresses to deliver the pages and protect them from attacks, under their own privacy policies (<a href=\"{gh}\" rel=\"noopener\">GitHub</a>, <a href=\"{cf}\" rel=\"noopener\">Cloudflare</a>)."),
            ("Public posts", "The tracker reads public posts about Syria and publishes aggregate results only. Posts by individuals are never stored, quoted or linked, and no one is profiled. To detect coordination, commenters' names are turned into one-way fingerprints that exist only in memory during an update and are never saved."),
            ("Social media accounts", "The tracker's Facebook Page publishes the site's own reports automatically through a Facebook app. The app is used only by the tracker's administrators to post to the tracker's own Page. It logs no one in, does not read, collect or store data about Facebook users, and shares nothing with anyone."),
            ("Data deletion", "Neither the tracker nor its Facebook app holds personal data about you, so there is nothing to delete. If you have ever connected the app to your Facebook account, you can remove it under Facebook Settings → Apps and websites → Remove." + (f" For any question or request, write to us through {c}." if c else "")),
        ]
        head = f"<h1>Privacy</h1><p class=\"sub\">Last updated: {esc(fmt_date(PRIVACY_UPDATED, lang))}</p>"
    return head + "".join(f'<h2 id="{"deletion" if i == 3 else "s" + str(i)}">{esc(h)}</h2><p>{body}</p>' for i, (h, body) in enumerate(sections))


SUPPORT_PLATFORMS = [("open_collective", "Open Collective"), ("github_sponsors", "GitHub Sponsors"), ("kofi", "Ko-fi"), ("paypal", "PayPal"), ("other", None)]


def support_links(cfg: dict) -> list:
    """[(label, url)] of the ways to give set under `support:` in config.yaml; https links only."""
    sup, out = cfg.get("support") or {}, []
    for key, label in SUPPORT_PLATFORMS:
        url = str(sup.get(key) or "").strip()
        if url.startswith("https://"):
            out.append((label or str(sup.get("other_label") or "Donate"), url))
    return out


def support_on(cfg: dict) -> bool:
    return bool(support_links(cfg))


def measured_costs(days: int = 30) -> tuple:
    """(dollars, days with data, updates) of the analysis over the last `days` days, from the archive index."""
    idx = archive._load(DATA / "archive" / "index.json", {}) or {}
    rows = [d for d in (idx.get("days") or []) if d.get("runs")][-days:]
    return round(sum(float(d.get("cost_usd") or 0) for d in rows), 2), len(rows), sum(int(d.get("runs") or 0) for d in rows)


def support_body(cfg: dict, lang: str) -> str:
    sup, links = cfg.get("support") or {}, support_links(cfg)
    dollars, ndays, runs = measured_costs()
    note = str(sup.get("recipient_note_ar" if lang == "ar" else "recipient_note") or "").strip()
    funders = [f for f in sup.get("funders") or [] if f.get("name")]
    oc = bool(str(sup.get("open_collective") or "").startswith("https://"))
    money = f"${dollars:,.2f}"
    if lang == "ar":
        money = ar_digits(money)
        head = "<h1>ادعم المتتبّع</h1><p>متتبّع السرديات السورية مجاني ومستقل ومفتوح: يمكن لأي شخص قراءته وتنزيل بياناته وإعادة استخدامها. يعمل بتكاليف صغيرة لكنها مستمرة، ويساعد دعمك على استمراره وتوسيعه.</p>"
        cost = (f"<h2>كم يكلّف</h2><div class=\"tw\"><table><tbody>"
                f"<tr><td>تحليل المنشورات بنموذج Claude، آخر {ar_digits(str(ndays))} يوماً ({ar_digits(str(runs))} تحديثاً)</td><td class=\"n\"><b>{money}</b></td></tr>"
                f"<tr><td>استضافة الموقع (GitHub Pages)</td><td class=\"n\">مجاناً</td></tr>"
                f"<tr><td>اسم النطاق syrianpulse.org</td><td class=\"n\">رسم سنوي</td></tr></tbody></table></div>"
                f"<p class=\"sub\">رقم التحليل مُقاس من سجلّ التحديثات نفسه، ويتحدّث تلقائياً.</p>")
        uses = ("<h2>ما الذي يموّله دعمك</h2><ul><li>استمرار التحديثات اليومية والتقارير الأسبوعية والشهرية.</li>"
                "<li>قراءة مزيد من المنشورات في كل تحديث، لتقديرات أدقّ للنبرة وقصص أصغر لا تضيع.</li>"
                "<li>مصادر جديدة، خصوصاً من المناطق التي لا يغطيها المتتبّع جيداً بعد.</li>"
                "<li>مراجعة بشرية لعيّنات من التحليل بالعربية والكردية، ونسخة كردية من الموقع.</li></ul>")
        give = "<h2>كيف تدعم</h2>" + (f'<p class="give">' + "".join(f'<a class="chip" href="{esc(u)}" rel="noopener">{esc(l)}</a>' for l, u in links) + "</p>" if links else "<p class=\"sub\">ستظهر طرق الدعم هنا قريباً.</p>")
        where = note or ("تذهب المدفوعات إلى صندوق المشروع على Open Collective، حيث تظهر كل دفعة وكل نفقة للعموم." if oc else
                         "تذهب المدفوعات إلى حساب مؤسس المشروع، ولا تُنفق إلا على المشروع. تكاليف كل شهر معروضة في هذه الصفحة.")
        rules = ("<h2>قواعدنا</h2><ul><li>لا يؤثر أي داعم أو ممول على ما ينشره المتتبّع أو كيف يحلّله.</li>"
                 "<li>يُذكر كل ممول مؤسسي في هذه الصفحة.</li><li>لا تُباع ولا تُشارك أي بيانات عن الأفراد، أبداً.</li>"
                 "<li>تبقى البيانات والتقارير مجانية ومفتوحة للجميع بترخيص CC BY 4.0.</li></ul>")
        fund = "<h2>الممولون</h2>" + ("<ul>" + "".join(f"<li>{esc(f.get('name_ar') or f['name'])}</li>" for f in funders) + "</ul>" if funders else "<p>لا ممولين مؤسسيين حتى الآن؛ المشروع ممول ذاتياً.</p>")
        return head + cost + uses + give + f"<h2>أين يذهب المال</h2><p>{esc(where)}</p>" + rules + fund
    head = "<h1>Support the tracker</h1><p>The Syria Narrative Tracker is free, independent and open: anyone can read it, download its data and reuse it. It runs on small but steady costs, and your support keeps it going and helps it grow.</p>"
    cost = (f"<h2>What it costs</h2><div class=\"tw\"><table><tbody>"
            f"<tr><td>Analysis of the posts by Claude, last {ndays} days ({runs} updates)</td><td class=\"n\"><b>{money}</b></td></tr>"
            f"<tr><td>Website hosting (GitHub Pages)</td><td class=\"n\">free</td></tr>"
            f"<tr><td>Domain name syrianpulse.org</td><td class=\"n\">yearly fee</td></tr></tbody></table></div>"
            f"<p class=\"sub\">The analysis figure is measured from the tracker's own record of updates and refreshes by itself.</p>")
    uses = ("<h2>What your support pays for</h2><ul><li>Keeping the daily updates and the weekly and monthly reports running.</li>"
            "<li>Reading more posts per update, for steadier tone estimates and fewer small stories missed.</li>"
            "<li>New sources, especially from areas the tracker does not yet cover well.</li>"
            "<li>Human review of samples of the analysis in Arabic and Kurdish, and a Kurdish version of the site.</li></ul>")
    give = "<h2>How to give</h2>" + (f'<p class="give">' + "".join(f'<a class="chip" href="{esc(u)}" rel="noopener">{esc(l)}</a>' for l, u in links) + "</p>" if links else "<p class=\"sub\">Ways to give will appear here soon.</p>")
    where = note or ("Payments go to the project's Open Collective, where every payment and every expense is public." if oc else
                     "Payments go to the account of the project's founder and are spent only on the project. Each month's costs are shown on this page.")
    rules = ("<h2>Our rules</h2><ul><li>No supporter or funder has any say in what the tracker publishes or how it analyses it.</li>"
             "<li>Every institutional funder is named on this page.</li><li>No data about individuals is ever sold or shared.</li>"
             "<li>The data and reports stay free and open to everyone under CC BY 4.0.</li></ul>")
    fund = "<h2>Funders</h2>" + ("<ul>" + "".join(f"<li>{esc(f['name'])}</li>" for f in funders) + "</ul>" if funders else "<p>No institutional funders yet; the project is self-funded.</p>")
    return head + cost + uses + give + f"<h2>Where the money goes</h2><p>{esc(where)}</p>" + rules + fund


FORM_ENDPOINT = "https://api.web3forms.com/submit"
CONTACT_TOPICS = {"en": ["General question or feedback", "Correction to a story or report", "Media enquiry", "Partnership or funding", "Technical problem with the site"],
                  "ar": ["سؤال عام أو ملاحظة", "تصحيح لقصة أو تقرير", "استفسار إعلامي", "شراكة أو تمويل", "مشكلة تقنية في الموقع"]}


def contact_key(cfg: dict) -> str:
    return str((cfg.get("contact") or {}).get("web3forms_access_key") or "").strip()


def contact_body(cfg: dict, lang: str) -> str:
    key, base = contact_key(cfg), site_url(cfg)
    fallback = str(cfg.get("contact_url") or "").strip()
    topics = "".join(f"<option>{esc(x)}</option>" for x in CONTACT_TOPICS[lang])
    ar = lang == "ar"
    head = ("<h1>اتصل بنا</h1><p>لسؤال أو تصحيح أو استفسار إعلامي أو شراكة، اكتب لنا هنا. نقرأ كل رسالة ونرد عادة خلال أيام قليلة.</p>" if ar else
            "<h1>Contact us</h1><p>For a question, a correction, a media enquiry or a partnership, write to us here. We read every message and usually reply within a few days.</p>")
    if not key:
        link = f'<a href="{esc(fallback)}" rel="noopener">{esc(fallback.replace("https://", ""))}</a>' if fallback.startswith("https://") else ""
        return head + (f"<p>نموذج التواصل قيد الإعداد. إلى ذلك الحين يمكنك الكتابة لنا عبر {link}.</p>" if ar else f"<p>The contact form is being set up. Until then you can reach us at {link}.</p>")
    labels = (("الاسم", "اختياري"), "بريدك الإلكتروني", "الموضوع", "رسالتك", "إرسال") if ar else (("Your name", "optional"), "Your email", "Topic", "Your message", "Send")
    note = ("تُرسَل رسالتك إلى فريق المتتبّع بالبريد الإلكتروني عبر خدمة Web3Forms، ولا تُحفظ على هذا الموقع ولا تُنشر. نستخدم بريدك للرد عليك فقط. "
            f'التفاصيل في <a href="../privacy/{lang}.html">صفحة الخصوصية</a>.' if ar else
            "Your message goes to the tracker's team by email through the Web3Forms service; it is not stored on this site or published. "
            f'We use your email only to reply. Details on the <a href="../privacy/{lang}.html">privacy page</a>.')
    return head + f"""<form class="cform" action="{FORM_ENDPOINT}" method="POST" accept-charset="UTF-8">
<input type="hidden" name="access_key" value="{esc(key)}">
<input type="hidden" name="subject" value="{esc('رسالة جديدة من syrianpulse.org (عربي)' if ar else 'New message from syrianpulse.org (English)')}">
<input type="hidden" name="from_name" value="{esc(site_title(cfg, 'en'))}">
<input type="hidden" name="redirect" value="{esc(base)}/contact/{lang}-sent.html">
<input type="checkbox" name="botcheck" class="hp" tabindex="-1" autocomplete="off" aria-hidden="true">
<label><span>{labels[0][0]} <span class="opt">({labels[0][1]})</span></span><input type="text" name="name" maxlength="120" autocomplete="name"></label>
<label>{labels[1]}<input type="email" name="email" required maxlength="200" autocomplete="email" dir="ltr"></label>
<label>{labels[2]}<select name="topic">{topics}</select></label>
<label>{labels[3]}<textarea name="message" required maxlength="5000"></textarea></label>
<button type="submit">{labels[4]}</button>
</form><p class="sub">{note}</p>"""


def write_contact_pages(cfg: dict) -> None:
    csp = CSP.replace("form-action 'none'", f"form-action {FORM_ENDPOINT} 'self'") if contact_key(cfg) else CSP
    for lang in LANGS:
        other = "ar" if lang == "en" else "en"
        w = W[lang]
        write(ROOT / "contact" / f"{lang}.html", page(cfg, lang, w["contact"], w["contact"], contact_body(cfg, lang),
                                                   f"contact/{lang}.html", f"contact/{other}.html", root="../", kind="website", csp=csp))
        sent = ('<h1>شكراً لك</h1><p>وصلت رسالتك. سنقرؤها ونرد عليك قريباً.</p><p><a href="../ar/">العودة إلى المتتبّع</a></p>' if lang == "ar" else
                '<h1>Thank you</h1><p>Your message has been sent. We will read it and reply soon.</p><p><a href="../">Back to the tracker</a></p>')
        write(ROOT / "contact" / f"{lang}-sent.html", page(cfg, lang, w["contact"], w["contact"], sent, f"contact/{lang}-sent.html",
                                                        f"contact/{other}-sent.html", root="../", kind="website", noindex=True))


def write_support_pages(cfg: dict) -> None:
    for lang in LANGS:
        other = "ar" if lang == "en" else "en"
        write(ROOT / "support" / f"{lang}.html", page(cfg, lang, W[lang]["support"], W[lang]["support"], support_body(cfg, lang),
                                                   f"support/{lang}.html", f"support/{other}.html", root="../", kind="website"))


def write_privacy_pages(cfg: dict) -> None:
    for lang in LANGS:
        other = "ar" if lang == "en" else "en"
        write(ROOT / "privacy" / f"{lang}.html", page(cfg, lang, W[lang]["privacy"], W[lang]["privacy"], privacy_body(cfg, lang),
                                                   f"privacy/{lang}.html", f"privacy/{other}.html", root="../", kind="website"))


# ----------------------------------------------------------------- the index of every source the site uses

SOURCES_WORDS = {
    "en": {"title": "Sources", "sub": "Every source the site reads: the channels, sites and platforms the tracker follows for what Syrians and Syrian outlets say, and the organisations and outlets behind the Expert view.",
           "tracker": "The tracker: what Syrians and Syrian outlets say", "experts": "The Expert view: international and Arab media, think tanks and organisations",
           "telegram": "Telegram channels", "news": "News sites", "youtube": "YouTube", "reddit": "Reddit", "bluesky": "Bluesky", "x": "X",
           "ytSearch": "Comments under the videos found by these searches", "ytChannels": "and under the newest videos of these channels",
           "search": "Posts found by keyword searches", "comments": "Telegram comments and reactions on the channels above, through a Telegram account",
           "kinds": {"intl": "International organisations", "thinktank": "Think tanks and research centres", "media": "Media"},
           "via": "read through Google News searches limited to its site",
           "note": "Posts by individuals are read only in aggregate: they are never stored, quoted or linked. The list changes as sources are added or stop working; every change to the tracker's sources is recorded in the method changelog on the About page."},
    "ar": {"title": "المصادر", "sub": "كل المصادر التي يقرؤها الموقع: القنوات والمواقع والمنصات التي يتابعها المتتبّع لمعرفة ما يقوله السوريون ووسائل الإعلام السورية، والجهات ووسائل الإعلام التي تستند إليها قراءات الخبراء.",
           "tracker": "المتتبّع: ما يقوله السوريون ووسائل الإعلام السورية", "experts": "قراءات الخبراء: وسائل إعلام ومراكز أبحاث ومنظمات دولية وعربية",
           "telegram": "قنوات تيليغرام", "news": "مواقع إخبارية", "youtube": "يوتيوب", "reddit": "ريديت", "bluesky": "بلوسكاي", "x": "إكس",
           "ytSearch": "التعليقات على الفيديوهات التي تُظهرها عمليات البحث هذه", "ytChannels": "وعلى أحدث فيديوهات هذه القنوات",
           "search": "منشورات تُظهرها عمليات بحث بالكلمات المفتاحية", "comments": "تعليقات تيليغرام وتفاعلاته على القنوات أعلاه، عبر حساب تيليغرام",
           "kinds": {"intl": "منظمات دولية", "thinktank": "مراكز أبحاث ودراسات", "media": "وسائل إعلام"},
           "via": "تُقرأ عبر بحث غوغل نيوز المحصور في موقعها",
           "note": "تُقرأ منشورات الأفراد إجمالاً فقط: لا تُخزَّن ولا تُقتبس ولا يُربط إليها. تتغير القائمة مع إضافة مصادر أو توقف أخرى، وكل تغيير في مصادر المتتبّع مسجَّل في سجل تغييرات المنهجية في صفحة «حول الموقع»."},
}


def source_domains(url: str) -> list:
    """The publisher sites behind a feed address: the site: terms of a Google News search, else the feed's host."""
    import urllib.parse as up
    sites = re.findall(r"site%3A([a-z0-9.-]+)", url, re.I) or re.findall(r"site:([a-z0-9.-]+)", url, re.I)
    if sites:
        return sites
    host = up.urlparse(url).netloc.lower()
    return [re.sub(r"^(www|feeds|news)\.(?=.+\..+)", "", host)] if host else []


def sources_body(cfg: dict, lang: str) -> str:
    w = SOURCES_WORDS[lang]
    kinds = {k["id"]: (k["label_ar"] if lang == "ar" else k["label"]) for k in archive.KINDS}
    lab = lambda x: (x.get("label_ar") if lang == "ar" and x.get("label_ar") else x.get("label")) or x.get("name") or ""
    link = lambda d: f'<a href="https://{esc(d)}" rel="noopener nofollow" dir="ltr">{esc(d)}</a>'
    parts = [f"<h1>{w['title']}</h1><p>{esc(w['sub'])}</p>", f"<h2>{w['tracker']}</h2>"]
    tg = cfg.get("telegram_channels") or []
    if tg:
        rows = "".join(f'<tr><td>{esc(lab(c))}</td><td>{esc(kinds.get(c.get("kind"), ""))}</td><td><a href="https://t.me/{esc(c["name"])}" rel="noopener nofollow" dir="ltr">t.me/{esc(c["name"])}</a></td></tr>' for c in tg)
        parts.append(f"<h3>{w['telegram']} ({num(len(tg), lang)})</h3><div class=\"tw\"><table><tbody>{rows}</tbody></table></div>")
    if (cfg.get("telegram_api") or {}).get("enabled"):
        parts.append(f"<p class=\"sub\">{esc(w['comments'])}</p>")
    feeds = cfg.get("rss_feeds") or []
    if feeds:
        rows = "".join(f'<tr><td>{esc(lab(f))}</td><td>{esc(kinds.get(f.get("kind"), ""))}</td><td>{" ".join(link(d) for d in source_domains(f["url"]))}</td></tr>' for f in feeds)
        parts.append(f"<h3>{w['news']} ({num(len(feeds), lang)})</h3><div class=\"tw\"><table><tbody>{rows}</tbody></table></div>")
    yt = cfg.get("youtube") or {}
    if yt.get("enabled"):
        chans = ", ".join(f'<a href="https://www.youtube.com/{esc(c["handle"])}" rel="noopener nofollow">{esc(lab(c))}</a>' for c in yt.get("channels") or [])
        parts.append(f"<h3>{w['youtube']}</h3><p>{esc(w['ytSearch'])}: <span dir=\"auto\">{esc(' · '.join(yt.get('search_terms') or []))}</span>" + (f"; {esc(w['ytChannels'])}: {chans}" if chans else "") + ".</p>")
    rd = cfg.get("reddit") or {}
    if rd.get("enabled"):
        subs = ", ".join(f'<a href="https://www.reddit.com/r/{esc(str(f["subreddit"]).removeprefix("r/"))}" rel="noopener nofollow" dir="ltr">r/{esc(str(f["subreddit"]).removeprefix("r/"))}</a>' for f in rd.get("feeds") or [])
        parts.append(f"<h3>{w['reddit']}</h3><p>{subs}</p>")
    bs = cfg.get("bluesky") or {}
    if bs.get("enabled"):
        parts.append(f"<h3>{w['bluesky']}</h3><p>{esc(w['search'])}: <span dir=\"auto\">{esc(' · '.join(bs.get('search_terms') or []))}</span></p>")
    if (cfg.get("x_twitter") or {}).get("enabled"):
        parts.append(f"<h3>{w['x']}</h3><p>{esc(w['search'])}.</p>")
    ex = (cfg.get("experts") or {})
    if ex.get("enabled") and ex.get("sources"):
        parts.append(f"<h2>{w['experts']}</h2>")
        for kind in ("intl", "thinktank", "media"):
            seen: dict = {}
            for x in (y for y in ex["sources"] if y.get("kind", "media") == kind and y.get("enabled") is not False):
                name = re.sub(r"\s*\(via Google News\)", "", x["name"])
                google = "news.google.com" in x["url"]
                e = seen.setdefault(name, {"domains": [], "via": False})
                for d in (source_domains(x["url"]) if not google or "site%3A" in x["url"] else ["news.google.com"]):
                    if d not in e["domains"]:
                        e["domains"].append(d)
                e["via"] = e["via"] or (google and "site%3A" in x["url"])
            rows = [f'<tr><td>{esc(n)}</td><td>{" ".join(link(d) for d in e["domains"])}</td><td class="sub">{esc(w["via"]) if e["via"] else ""}</td></tr>'
                    for n, e in seen.items()]
            if rows:
                parts.append(f"<h3>{w['kinds'][kind]}</h3><div class=\"tw\"><table><tbody>{''.join(rows)}</tbody></table></div>")
    parts.append(f"<p class=\"sub\">{esc(w['note'])}</p>")
    return "\n".join(parts)


def write_sources_pages(cfg: dict) -> None:
    for lang in LANGS:
        w, other = SOURCES_WORDS[lang], "ar" if lang == "en" else "en"
        write(ROOT / "sources" / f"{lang}.html", page(cfg, lang, w["title"], w["sub"], sources_body(cfg, lang),
                                                      f"sources/{lang}.html", f"sources/{other}.html", kind="website",
                                                      jsonld=ld_breadcrumbs(cfg, lang, [(w["title"], f"sources/{lang}.html")])))


def publish(cfg: dict, latest: dict, narratives: list | None = None) -> None:
    """Everything the pipeline does after a run: story pages for the run's stories, listings, feeds, sitemap, prerender."""
    update_story_index(latest)
    write_story_pages(cfg, latest, narratives)
    write_story_listing(cfg)
    digests = load_digests()
    write_weekly_listing(cfg, digests)
    write_feeds(cfg, digests)
    reviews = load_reviews()
    write_monthly_listing(cfg, reviews)
    write_monthly_feeds(cfg, reviews)
    today = str(latest.get("generated_at") or "")[:10]
    if today:
        write_daily_pages(cfg, [today])   # the day's brief, refreshed on every update
    write_daily_listing(cfg)
    write_sitemap(cfg, digests, reviews)
    write_privacy_pages(cfg)
    write_support_pages(cfg)
    write_contact_pages(cfg)
    write_sources_pages(cfg)
    prerender_index(cfg, latest)
