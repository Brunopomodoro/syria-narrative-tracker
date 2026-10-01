/* Shayfak front end.
 *
 * Data flow
 *   data/officials.json      who the officials are (maintained by scripts/update_officials.py)
 *   Firebase /monthly        public vote aggregates per official per month (read only)
 *   Firebase /published      moderated community submissions (read only)
 *   Cloud Functions          castVote, getMyVotes, submitReport, moderate, listPending, deleteMyAccount
 *
 * The browser never writes to the database and never sends the Claude API key anywhere: all of that is server side.
 */
(function () {
"use strict";

const CFG = window.SHAYFAK || {};
const MIN_SAMPLE = Number(CFG.minSample || 30);
const DATA = CFG.dataPath || "data/";

// ── i18n ──────────────────────────────────────────────────────────────────────
const TR = {
en: {
  sn:"Shayfak", sub:"Syria Political Accountability",
  hero_s:"A public record of Syria's transitional government: who holds each office, what they have committed to, and how public confidence develops month by month.",
  p1:"Sourced", p1s:"Every entry links to where it came from.", p2:"Neutral", p2s:"We record what is public. We do not judge.", p3:"Open to response", p3s:"Officials and their offices can reply or correct any entry.",
  reply:"Send a response or correction", reply_s:"If you are the official or speak for their office, send a response. It is published next to the record.", record_note:"Documented questions and concerns, each with its source. Responses from the official are published alongside.", who_public:"Member of the public", who_office:"The official or their office", cResp:"Response",
  h_off:"Officials tracked", h_vt:"Votes this month", h_idx:"Confidence index", h_upd:"Roster updated",
  si:"Sign in", so:"Sign out", ltog:"العربية", fa:"All", fp:"President", fs:"Security", fg:"Government", fgov:"Governors", fpar:"Parliament", fformer:"Former",
  sb:"Sort:", sap:"Confidence", sr:"Rating", sn2:"Name", search:"Search officials...",
  tb:"Bio & career", tp:"Commitments", ta:"Public record", tc:"Community", ts:"Confidence",
  br:"Role", ba:"Affiliation", bsi:"In office since", bl:"Based in", bs:"Biography", bca:"Career", bi:"Issues", bten:"Positions held",
  pk:"Delivered", pp:"In progress", pb:"Not delivered", pn:"Pending", pt:"Commitments and pledges", ae:"No documented concerns on record.",
  pcs:"From the community (moderated)", acs:"From the community (moderated)", cn:"Submissions are classified by AI and checked by a moderator before they appear. Submitters are never shown.",
  ce:"No published submissions yet.",
  trust:"Confidence", distrust:"Not yet", votes:"votes", thismonth:"this month", notenough:"Not enough votes yet to show a percentage", needmore:"more needed",
  yourvote:"Your vote this month", novote:"You have not voted this month.", changeok:"You can change it until the month ends.",
  sl:"Sign in to vote", rate:"Rate 1 to 5 stars", history:"Confidence over time", hist_sub:"Share of confidence votes per month. Only months with enough votes are drawn.",
  all:"All voters", inside:"Inside Syria", verified:"Verified", table:"Table view", chart:"Chart view", month:"Month",
  movers_up:"Confidence rising", movers_dn:"Confidence declining", vs:"vs last month", nomovers:"Appears once two months of votes exist.",
  idx_title:"Public confidence index", idx_sub:"All confidence votes this month, pooled across officials", idx_none:"No votes yet this month",
  sb2:"Submit a report", stl:"Submit a report", si2:"Describe an incident, a promise or a statement, with a link to the source. AI summarises it; a moderator checks it before it is published. Your name is never attached.",
  src_ph:"Source URL (news article, official page, video)", txt_ph:"What happened? Quote the source where you can.", ab:"Analyze and submit", analyzing:"Analyzing...",
  rt:"Submitted for moderation", thanks:"Thank you. Here is how it was classified. It will appear once a moderator approves it.", fn:"See something missing?",
  lt:"Sign in to Shayfak", ls:"Sign-in is only used to stop double voting.", lg:"Continue with Google", lf:"Continue with Facebook", lx:"Continue with X",
  anon:"Your account is never stored with your vote. Votes are saved under a one-way code that cannot be turned back into your account, even by us. Nobody can see how you voted.",
  lc:"Cancel", li:"Signing in...", del:"Delete my account", delq:"Delete your account? Your sign-in and the link to your votes are destroyed. Published counts stay as they are.",
  mod:"Moderation", pending:"Pending submissions", publish:"Publish", reject:"Reject", none_pending:"Nothing waiting.",
  cAll:"Concern", cCor:"Integrity concern", cPro:"Promise", cAch:"Achievement", cSta:"Statement", cGen:"General",
  former:"Former", deceased:"Deceased", until:"until", present:"present", changelog:"Change log", data:"Open data", method:"How it works",
  share:"Share", copy:"Copy link", copied:"Link copied", back:"Back",
  footer:"An accountability record, not a verdict. The roster comes from official Syrian announcements and Wikidata and is checked daily. Votes are anonymous and open data (CC BY 4.0).",
  err_generic:"Something went wrong. Try again.", err_rate:"Too many requests. Try again later.", err_short:"Please write at least a sentence.",
  chg:{appointment:"Appointed", resignation:"Left office", dismissal:"Dismissed", death:"Died", reshuffle:"Moved", restructure:"Restructured"},
},
ar: {
  sn:"شايفك", sub:"منصة المساءلة السياسية السورية",
  hero_s:"سجل عام للحكومة الانتقالية السورية: من يشغل كل منصب، بماذا التزم، وكيف تتطور ثقة الناس شهراً بعد شهر.",
  p1:"موثَّق", p1s:"كل معلومة مرتبطة بمصدرها.", p2:"محايد", p2s:"نسجّل ما هو علني ولا نُصدر أحكاماً.", p3:"مفتوح للرد", p3s:"يمكن للمسؤولين ومكاتبهم الرد على أي معلومة أو تصحيحها.",
  reply:"أرسل رداً أو تصحيحاً", reply_s:"إن كنت المسؤول أو تتحدث باسم مكتبه، أرسل رداً يُنشر إلى جانب السجل.", record_note:"أسئلة وملاحظات موثقة، لكل منها مصدر. تُنشر ردود المسؤول إلى جانبها.", who_public:"من الجمهور", who_office:"المسؤول أو مكتبه", cResp:"رد",
  h_off:"مسؤول مُتابَع", h_vt:"صوت هذا الشهر", h_idx:"مؤشر الثقة", h_upd:"آخر تحديث للقائمة",
  si:"تسجيل الدخول", so:"تسجيل الخروج", ltog:"English", fa:"الكل", fp:"الرئاسة", fs:"الأمن", fg:"الحكومة", fgov:"المحافظون", fpar:"البرلمان", fformer:"السابقون",
  sb:"ترتيب:", sap:"الثقة", sr:"التقييم", sn2:"الاسم", search:"ابحث عن مسؤول...",
  tb:"السيرة الذاتية", tp:"الالتزامات", ta:"السجل العام", tc:"المجتمع", ts:"الثقة",
  br:"المنصب", ba:"الانتماء", bsi:"في المنصب منذ", bl:"مقر الإقامة", bs:"نبذة تعريفية", bca:"المسيرة المهنية", bi:"القضايا", bten:"المناصب",
  pk:"منجز", pp:"قيد التنفيذ", pb:"لم يُنجز", pn:"معلق", pt:"الالتزامات والتعهدات", ae:"لا توجد ملاحظات موثقة في السجل.",
  pcs:"من المجتمع (بعد المراجعة)", acs:"من المجتمع (بعد المراجعة)", cn:"تُصنَّف البلاغات بالذكاء الاصطناعي ويراجعها مشرف قبل نشرها. لا يظهر اسم المُبلِّغ أبداً.",
  ce:"لا توجد بلاغات منشورة بعد.",
  trust:"ثقة", distrust:"لا ثقة بعد", votes:"صوت", thismonth:"هذا الشهر", notenough:"لا توجد أصوات كافية بعد لعرض نسبة", needmore:"صوت إضافي مطلوب",
  yourvote:"صوتك هذا الشهر", novote:"لم تصوّت هذا الشهر.", changeok:"يمكنك تغييره حتى نهاية الشهر.",
  sl:"سجّل دخولك للتصويت", rate:"قيّم من 1 إلى 5 نجوم", history:"الثقة عبر الزمن", hist_sub:"نسبة أصوات الثقة في كل شهر. تُرسم الأشهر التي فيها أصوات كافية فقط.",
  all:"كل المصوّتين", inside:"داخل سوريا", verified:"موثَّق", table:"عرض جدول", chart:"عرض رسم", month:"الشهر",
  movers_up:"ثقة صاعدة", movers_dn:"ثقة هابطة", vs:"مقارنة بالشهر الماضي", nomovers:"يظهر هذا القسم بعد توفر شهرين من الأصوات.",
  idx_title:"مؤشر الثقة بالحكومة", idx_sub:"كل أصوات الثقة هذا الشهر مجمَّعة عبر المسؤولين", idx_none:"لا أصوات بعد هذا الشهر",
  sb2:"أرسل بلاغاً", stl:"إرسال بلاغ", si2:"صف حادثة أو وعداً أو تصريحاً مع رابط المصدر. يلخّصه الذكاء الاصطناعي ويراجعه مشرف قبل النشر. اسمك لا يُرفق أبداً.",
  src_ph:"رابط المصدر (مقال، صفحة رسمية، فيديو)", txt_ph:"ماذا حدث؟ اقتبس من المصدر إن أمكن.", ab:"تحليل وإرسال", analyzing:"جارٍ التحليل...",
  rt:"أُرسل للمراجعة", thanks:"شكراً. هكذا صُنِّف البلاغ، وسيظهر بعد موافقة المشرف.", fn:"هل لاحظت معلومة مفقودة؟",
  lt:"تسجيل الدخول لشايفك", ls:"تسجيل الدخول يُستخدم فقط لمنع التصويت المكرر.", lg:"المتابعة عبر جوجل", lf:"المتابعة عبر فيسبوك", lx:"المتابعة عبر إكس",
  anon:"حسابك لا يُخزَّن مع صوتك أبداً. تُحفظ الأصوات تحت رمز أحادي الاتجاه لا يمكن إعادته إلى حسابك، حتى من قِبلنا. لا أحد يستطيع معرفة كيف صوّت.",
  lc:"إلغاء", li:"جارٍ تسجيل الدخول...", del:"حذف حسابي", delq:"حذف حسابك؟ سيُمحى تسجيل دخولك والرابط بينه وبين أصواتك. تبقى الأعداد المنشورة كما هي.",
  mod:"الإشراف", pending:"بلاغات بانتظار المراجعة", publish:"نشر", reject:"رفض", none_pending:"لا شيء بانتظار المراجعة.",
  cAll:"ملاحظة", cCor:"شبهة فساد", cPro:"وعد", cAch:"إنجاز", cSta:"تصريح", cGen:"عام",
  former:"سابق", deceased:"متوفى", until:"حتى", present:"الآن", changelog:"سجل التغييرات", data:"بيانات مفتوحة", method:"كيف يعمل",
  share:"مشاركة", copy:"نسخ الرابط", copied:"تم نسخ الرابط", back:"رجوع",
  footer:"سجل للمساءلة لا حُكم. القائمة من الإعلانات السورية الرسمية وويكي بيانات وتُفحص يومياً. الأصوات مجهولة الهوية وبيانات مفتوحة (CC BY 4.0).",
  err_generic:"حدث خطأ ما. حاول مجدداً.", err_rate:"طلبات كثيرة. حاول لاحقاً.", err_short:"اكتب جملة واحدة على الأقل.",
  chg:{appointment:"تعيين", resignation:"ترك المنصب", dismissal:"إعفاء", death:"وفاة", reshuffle:"نقل", restructure:"إعادة هيكلة"},
}};
let lang = (function(){ try { return localStorage.getItem("sk_lang") || "ar"; } catch { return "ar"; } })();
const t = (k) => (TR[lang][k] ?? TR.en[k] ?? k);
const L = (o, k) => (lang === "ar" ? o[k + "Ar"] : o[k + "En"]) || o[k + "En"] || o[k + "Ar"] || "";
const N = (o) => { const ttl = lang === "ar" ? o.titleAr : o.titleEn; return (ttl ? ttl + " " : "") + L(o, "name"); };
const esc = (s) => s == null ? "" : String(s).replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;").replace(/'/g,"&#39;");
// Western digits in both languages: Arabic month names, but 1, 2, 3 rather than ١ ٢ ٣.
const LOC = () => (lang === "ar" ? "ar-SY-u-nu-latn" : "en-GB");
const num = (n) => Number(n || 0).toLocaleString("en-GB");

// ── state ─────────────────────────────────────────────────────────────────────
const A = {
  loaded:false, officials:[], meta:{}, changelog:[], trustIndex:{},
  monthly:{},            // id -> {month -> agg}
  published:{},          // id -> [sub]
  my:{}, myMonth:null,   // id -> {vote, stars}
  user:null, isMod:false,
  filter:"all", sort:"trust", search:"", viewGrid:false,
  sel:null, tab:"bio", chartTable:false, hStar:0,
  showAuth:false, authLoading:null, showSubmit:false, asOffice:false, stxt:"", surl:"", analyzing:false, result:null, err:null,
  showMod:false, pendingList:null, showLog:false,
};
let fb = { db:null, auth:null, fns:null, ready:false };
let _rPending = false;
function scheduleRender(){ if(_rPending) return; _rPending = true; requestAnimationFrame(()=>{ _rPending=false; render(); }); }
function setState(p){ Object.assign(A, p); if("sel" in p && !p.sel && location.hash) history.pushState(null,"",location.pathname+location.search); render(); }
window.setState = setState;

// ── helpers ───────────────────────────────────────────────────────────────────
const monthKey = (d = new Date()) => `${d.getUTCFullYear()}-${String(d.getUTCMonth()+1).padStart(2,"0")}`;
function prevMonthKey(m){ const [y,mo] = m.split("-").map(Number); const d = new Date(Date.UTC(y, mo-2, 1)); return monthKey(d); }
function fmtMonth(m){ const [y,mo] = m.split("-").map(Number); return new Date(Date.UTC(y,mo-1,1)).toLocaleDateString(LOC(),{month:"short",year:"numeric",timeZone:"UTC"}); }
function agg(id, m){ return (A.monthly[id] || {})[m || monthKey()] || null; }
function pctOf(a, part){ if(!a) return null; const s = part ? (a[part] || {}) : a; const up = s.up||0, dn = s.dn||0, n = up+dn; return n >= MIN_SAMPLE ? Math.round(100*up/n) : null; }
function totalOf(a){ return a ? (a.up||0)+(a.dn||0) : 0; }
function acol(p){ return p == null ? "#78716c" : p >= 60 ? "#15803d" : p >= 40 ? "#b45309" : "#b91c1c"; }
function avgStars(a){ const s = a && a.stars; return s && s.cnt ? (s.sum/s.cnt).toFixed(1) : null; }
function byId(id){ return A.officials.find(o => o.id === id); }
function active(o){ return o.status === "active"; }
function grpLbl(o){ return o.grp==="president"?t("fp"):o.grp==="security"?t("fs"):o.grp==="parliament"?t("fpar"):o.grp==="governor"?(lang==="ar"?"محافظ":"Governor"):t("fg"); }

function showToast(msg, type="info", ms=4000){
  let tc = document.getElementById("toast-container");
  if(!tc){ tc = document.createElement("div"); tc.id="toast-container"; document.body.appendChild(tc); }
  const el = document.createElement("div"); el.className = `toast toast-${type}`; el.textContent = msg; tc.appendChild(el);
  setTimeout(()=>{ el.style.opacity="0"; el.style.transition="opacity .3s"; setTimeout(()=>el.remove(), 320); }, ms);
}
function fnError(e){
  const code = (e && e.code) || "";
  if(code.includes("resource-exhausted")) return t("err_rate");
  if(code.includes("unauthenticated")) return t("sl");
  return (e && e.message) ? `${t("err_generic")} (${e.message})` : t("err_generic");
}

// ── data loading ──────────────────────────────────────────────────────────────
async function loadStatic(){
  // A build can inline the data (window.SHAYFAK_DATA) so the page also works when opened from disk.
  const inline = window.SHAYFAK_DATA;
  if(inline && inline.officials){
    A.officials = inline.officials.officials || []; A.meta = inline.officials.meta || {};
    A.changelog = Array.isArray(inline.changelog) ? inline.changelog : [];
    const j = inline.trust;
    if(j){ for(const [id, a] of Object.entries(j.officials||{})) (A.monthly[Number(id)] ||= {})[j.month] = a;
      if(j.previous_month) for(const [id, a] of Object.entries(j.previous||{})) (A.monthly[Number(id)] ||= {})[j.previous_month] = a; }
    return;
  }
  const r = await fetch(DATA + "officials.json", {cache:"no-cache"});
  const doc = await r.json();
  A.officials = doc.officials || []; A.meta = doc.meta || {};
  fetch(DATA + "changelog.json").then(r=>r.ok?r.json():[]).then(j=>{ A.changelog = Array.isArray(j)?j:[]; }).catch(()=>{});
  // the repository snapshot is the fallback when Firebase is unreachable
  fetch(DATA + "trust/latest.json").then(r=>r.ok?r.json():null).then(j=>{
    if(!j || Object.keys(A.monthly).length) return;
    for(const [id, a] of Object.entries(j.officials||{})) (A.monthly[Number(id)] ||= {})[j.month] = a;
    if(j.previous_month) for(const [id, a] of Object.entries(j.previous||{})) (A.monthly[Number(id)] ||= {})[j.previous_month] = a;
    scheduleRender();
  }).catch(()=>{});
}

function initFirebase(){
  if(typeof firebase === "undefined" || !CFG.firebase || !CFG.firebase.apiKey) return;
  try {
    firebase.initializeApp(CFG.firebase);
    if(CFG.appCheckSiteKey && firebase.appCheck){
      firebase.appCheck().activate(CFG.appCheckSiteKey, true);
    }
    fb.db = firebase.database(); fb.auth = firebase.auth(); fb.fns = firebase.app().functions(CFG.functionsRegion || "europe-west1"); fb.ready = true;
  } catch(e){ console.warn("Firebase init failed:", e.message); return; }

  fb.db.ref("monthly").on("value", snap => {
    const v = snap.val() || {}; const out = {};
    for(const [id, months] of Object.entries(v)) out[Number(id)] = months || {};
    A.monthly = out; scheduleRender();
  });
  fb.db.ref("published").on("value", snap => {
    const v = snap.val() || {}; const out = {};
    for(const [id, items] of Object.entries(v)) out[Number(id)] = Object.entries(items||{}).map(([k,s])=>({id:k,...s})).sort((a,b)=>(b.publishedAt||b.ts||0)-(a.publishedAt||a.ts||0));
    A.published = out; scheduleRender();
  });
  fb.auth.onAuthStateChanged(async user => {
    if(user){
      A.user = { uid:user.uid, name:user.displayName || "", via:(user.providerData[0]||{}).providerId || "" };
      try { const tok = await user.getIdTokenResult(); A.isMod = tok.claims.moderator === true || tok.claims.admin === true; } catch { A.isMod = false; }
      await refreshMyVotes();
    } else { A.user = null; A.isMod = false; A.my = {}; A.myMonth = null; }
    render();
  });
}
async function refreshMyVotes(){
  if(!fb.ready || !A.user) return;
  try { const res = await fb.fns.httpsCallable("getMyVotes")({}); A.my = {}; for(const [id,v] of Object.entries(res.data.votes||{})) A.my[Number(id)] = v; A.myMonth = res.data.month; }
  catch(e){ console.warn("getMyVotes:", e.message); }
}

// ── actions ───────────────────────────────────────────────────────────────────
async function doVote(id, dir){
  if(!A.user){ setState({showAuth:true}); return; }
  const cur = (A.my[id]||{}).vote || null;
  const vote = cur === dir ? null : dir;
  const prev = A.my[id]; A.my[id] = {...(A.my[id]||{}), vote}; render();
  try { const res = await fb.fns.httpsCallable("castVote")({officialId:id, vote}); A.my[id] = {vote:res.data.vote, stars:res.data.stars}; }
  catch(e){ A.my[id] = prev; showToast(fnError(e), "warn"); }
  render();
}
async function doRate(id, stars){
  if(!A.user){ setState({showAuth:true}); return; }
  const prev = A.my[id]; A.my[id] = {...(A.my[id]||{}), stars}; A.hStar = 0; render();
  try { const res = await fb.fns.httpsCallable("castVote")({officialId:id, stars}); A.my[id] = {vote:res.data.vote, stars:res.data.stars}; }
  catch(e){ A.my[id] = prev; showToast(fnError(e), "warn"); }
  render();
}
async function doLogin(provider){
  if(!fb.ready){ showToast("Firebase is not configured (config.js)", "warn"); return; }
  let p;
  if(provider==="google") p = new firebase.auth.GoogleAuthProvider();
  else if(provider==="facebook") p = new firebase.auth.FacebookAuthProvider();
  else if(provider==="x") p = new firebase.auth.TwitterAuthProvider();
  else return;
  try { setState({authLoading:provider}); await fb.auth.signInWithPopup(p); setState({showAuth:false, authLoading:null}); }
  catch(e){ setState({authLoading:null}); showToast((lang==="ar"?"فشل تسجيل الدخول: ":"Sign-in failed: ") + e.message, "warn", 6000); }
}
async function doLogout(){ if(fb.ready) await fb.auth.signOut(); A.user=null; A.my={}; render(); }
async function doDeleteAccount(){
  if(!A.user || !confirm(t("delq"))) return;
  try { await fb.fns.httpsCallable("deleteMyAccount")({}); A.user=null; A.my={}; showToast("✓", "ok"); }
  catch(e){ showToast(fnError(e), "warn"); }
  render();
}
async function doSubmit(){
  const o = byId(A.sel); if(!o) return;
  if(!A.user){ setState({showAuth:true}); return; }
  if(A.stxt.trim().length < 20){ setState({err:t("err_short")}); return; }
  setState({analyzing:true, err:null, result:null});
  try {
    const res = await fb.fns.httpsCallable("submitReport")({officialId:o.id, text:A.stxt.trim(), sourceUrl:A.surl.trim(), asOfficial:A.asOffice===true, lang, officialName:`${o.nameEn} / ${o.nameAr} (${o.roleEn})`});
    setState({analyzing:false, result:res.data.analysis, stxt:"", surl:""});
  } catch(e){ setState({analyzing:false, err:fnError(e)}); }
}
async function loadPending(){
  try { const res = await fb.fns.httpsCallable("listPending")({}); setState({pendingList:res.data.pending||[]}); }
  catch(e){ showToast(fnError(e), "warn"); }
}
async function doModerate(officialId, id, action){
  try { await fb.fns.httpsCallable("moderate")({officialId, id, action}); A.pendingList = (A.pendingList||[]).filter(p=>p.id!==id); render(); }
  catch(e){ showToast(fnError(e), "warn"); }
}
function toggleLang(){
  lang = lang==="ar"?"en":"ar"; try { localStorage.setItem("sk_lang", lang); } catch {}
  document.documentElement.lang = lang; document.documentElement.dir = lang==="ar"?"rtl":"ltr"; render();
}
Object.assign(window, {doVote, doRate, doLogin, doLogout, doDeleteAccount, doSubmit, loadPending, doModerate, toggleLang, shareOn, openOfficial});

// ── share + routing ───────────────────────────────────────────────────────────
function shareURL(o){
  const site = (CFG.siteUrl||"").replace(/\/$/,"");
  if(site && location.hostname !== "localhost" && location.protocol !== "file:") return `${site}/p/${o.slug}.html`;
  return `${location.href.split("#")[0]}#p${o.id}`;
}
function shareText(o){
  const a = agg(o.id); const p = pctOf(a); const n = totalOf(a);
  const name = N(o), role = L(o,"role");
  if(lang==="ar") return p==null ? `${name} (${role}) على شايفك. صوّت هذا الشهر: ${shareURL(o)} #شايفك #سوريا`
                                  : `${name} (${role}): ${p}٪ ثقة من ${n} صوت هذا الشهر على شايفك. صوّت أنت أيضاً: ${shareURL(o)} #شايفك #سوريا`;
  return p==null ? `${name} (${role}) on Shayfak. Vote this month: ${shareURL(o)} #Shayfak #Syria`
                 : `${name} (${role}): ${p}% trust from ${n} votes this month on Shayfak. Cast yours: ${shareURL(o)} #Shayfak #Syria`;
}
function shareOn(platform, id){
  const o = byId(id); if(!o) return;
  const url = encodeURIComponent(shareURL(o)), txt = encodeURIComponent(shareText(o));
  const links = { x:`https://x.com/intent/tweet?text=${txt}`, whatsapp:`https://wa.me/?text=${txt}`, telegram:`https://t.me/share/url?url=${url}&text=${txt}`, facebook:`https://www.facebook.com/sharer/sharer.php?u=${url}` };
  if(platform==="copy"){ navigator.clipboard.writeText(shareURL(o)).then(()=>showToast(t("copied"),"ok")).catch(()=>{}); return; }
  if(platform==="native" && navigator.share){ navigator.share({title:`${t("sn")} — ${N(o)}`, text:shareText(o), url:shareURL(o)}).catch(()=>{}); return; }
  window.open(links[platform], "_blank", "noopener,width=600,height=500");
}
function openOfficial(id){ setState({sel:id, tab:"bio", showSubmit:false, result:null, err:null}); }
function routeFromHash(){
  const h = location.hash.replace(/^#\/?/, "");
  if(!h) { if(A.sel) setState({sel:null}); return; }
  let o = null;
  if(/^p\d+$/.test(h)) o = byId(Number(h.slice(1))); else o = A.officials.find(x => x.slug === h);
  if(o && A.sel !== o.id) setState({sel:o.id, tab:"bio"});
}

// ── chart ─────────────────────────────────────────────────────────────────────
const SERIES = [["all","#2a78d6"],["inside","#eb6834"],["verified","#1baf7a"]];
function seriesPoints(id){
  const months = Object.keys(A.monthly[id]||{}).sort();
  return months.map(m => { const a = A.monthly[id][m]; return { m, all:pctOf(a), inside:pctOf(a,"inside"), verified:pctOf(a,"verified"), n:totalOf(a), nIn:totalOf(a.inside), nVer:totalOf(a.verified) }; });
}
function renderTrustChart(o){
  const pts = seriesPoints(o.id);
  const drawn = pts.filter(p => p.all != null || p.inside != null || p.verified != null);
  if(drawn.length < 2 && !A.chartTable) return `<div class="chart-wrap"><div class="chart-title">${t("history")}</div><div class="chart-sub">${t("hist_sub")}</div><div class="ns">${t("nomovers")}</div>${pts.length?tableView(pts):""}</div>`;
  const used = SERIES.filter(([k]) => pts.some(p => p[k] != null));
  const W = 640, H = 220, px = 36, py = 16, iw = W - px*2, ih = H - py*2 - 18;
  const xs = pts.map((_, i) => px + (pts.length === 1 ? iw/2 : i*iw/(pts.length-1)));
  const y = v => py + ih - v/100*ih;
  const grid = [0,25,50,75,100].map(v => `<line x1="${px}" x2="${W-px}" y1="${y(v)}" y2="${y(v)}" stroke="#e7e5e4" stroke-width="1"/><text x="${px-6}" y="${y(v)+4}" font-size="10" fill="#78716c" text-anchor="end">${v}%</text>`).join("");
  const labels = pts.map((p,i) => `<text x="${xs[i]}" y="${H-2}" font-size="10" fill="#78716c" text-anchor="middle">${esc(fmtMonth(p.m))}</text>`).join("");
  const lines = used.map(([k,col]) => {
    const d = pts.map((p,i) => p[k]==null ? null : `${xs[i].toFixed(1)},${y(p[k]).toFixed(1)}`);
    let path = "", pen = false;
    d.forEach(seg => { if(seg==null){ pen=false; return; } path += (pen?"L":"M") + seg + " "; pen = true; });
    const marks = pts.map((p,i) => p[k]==null ? "" : `<circle cx="${xs[i]}" cy="${y(p[k])}" r="4" fill="${col}" stroke="#fff" stroke-width="2"/>`).join("");
    const last = [...pts].reverse().find(p => p[k]!=null);
    const lastIdx = pts.indexOf(last);
    // only the first series carries an end label; the others are read from the legend, tooltip or table
    const lbl = last && k === used[0][0] ? `<text x="${xs[lastIdx]+6}" y="${y(last[k])+4}" font-size="11" font-weight="700" fill="#292524">${last[k]}%</text>` : "";
    return `<path d="${path.trim()}" fill="none" stroke="${col}" stroke-width="2" stroke-linejoin="round" stroke-linecap="round"/>${marks}${lbl}`;
  }).join("");
  const hits = pts.map((p,i) => `<rect data-i="${i}" x="${(i===0?px:(xs[i-1]+xs[i])/2).toFixed(1)}" y="${py}" width="${((i===pts.length-1?W-px:(xs[i]+xs[i+1])/2)-(i===0?px:(xs[i-1]+xs[i])/2)).toFixed(1)}" height="${ih}" fill="transparent"/>`).join("");
  const legend = used.map(([k,col]) => `<span><i style="background:${col}"></i>${t(k)}</span>`).join("");
  return `<div class="chart-wrap" id="trust-chart">
    <div style="display:flex;justify-content:space-between;align-items:baseline;gap:8px;flex-wrap:wrap"><div><div class="chart-title">${t("history")}</div><div class="chart-sub">${t("hist_sub")}</div></div>
    <button class="linkbtn" onclick="setState({chartTable:!A.chartTable})">${A.chartTable?t("chart"):t("table")}</button></div>
    ${A.chartTable ? tableView(pts) : `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="${esc(t("history"))}" style="direction:ltr">${grid}${lines}${labels}<g class="hits">${hits}</g></svg><div class="legend">${legend}</div><div class="chart-tip" id="chart-tip"></div>`}
  </div>`;
}
function tableView(pts){
  return `<table class="tbl"><thead><tr><th>${t("month")}</th><th>${t("all")}</th><th>${t("votes")}</th><th>${t("inside")}</th><th>${t("verified")}</th></tr></thead><tbody>
  ${[...pts].reverse().map(p => `<tr><td>${esc(fmtMonth(p.m))}</td><td>${p.all==null?"—":p.all+"%"}</td><td>${num(p.n)}</td><td>${p.inside==null?"—":p.inside+"%"} <span style="color:var(--g4)">(${num(p.nIn)})</span></td><td>${p.verified==null?"—":p.verified+"%"} <span style="color:var(--g4)">(${num(p.nVer)})</span></td></tr>`).join("")}
  </tbody></table>`;
}
function wireChart(o){
  const root = document.getElementById("trust-chart"); if(!root) return;
  const tip = document.getElementById("chart-tip"); const pts = seriesPoints(o.id);
  root.querySelectorAll(".hits rect").forEach(r => {
    r.addEventListener("mousemove", ev => {
      const p = pts[Number(r.dataset.i)]; if(!p) return;
      const rows = [[t("all"),p.all,p.n],[t("inside"),p.inside,p.nIn],[t("verified"),p.verified,p.nVer]].filter(x=>x[2]>0).map(x=>`${x[0]}: ${x[1]==null?"—":x[1]+"%"} (${x[2]})`).join("<br>");
      tip.innerHTML = `<strong>${esc(fmtMonth(p.m))}</strong><br>${rows}`; tip.style.display="block";
      const b = root.getBoundingClientRect(); tip.style.left = Math.min(ev.clientX-b.left+12, b.width-170)+"px"; tip.style.top = (ev.clientY-b.top-10)+"px";
    });
    r.addEventListener("mouseleave", ()=>{ tip.style.display="none"; });
  });
}

// ── render pieces ─────────────────────────────────────────────────────────────
function pEl(o, sz){
  const fs = sz>=72?20:15;
  const fb_ = `<div class="av-fb" style="background:${o.bg};color:${o.col};font-size:${fs}px;width:100%;height:100%;display:flex;align-items:center;justify-content:center;font-weight:600">${esc(o.ini)}</div>`;
  const inner = o.photo ? `<img src="${esc(o.photo)}" alt="" loading="lazy" referrerpolicy="no-referrer" style="width:100%;height:100%;object-fit:cover;display:block" onerror="this.remove()">${fb_}` : fb_;
  return `<div style="width:${sz}px;height:${sz}px;border-radius:50%;overflow:hidden;border:2px solid var(--g3);flex-shrink:0;position:relative">${inner}</div>`;
}
function statusBadge(o){ return o.status==="active" ? "" : `<span class="status-badge status-former">${o.status==="deceased"?t("deceased"):t("former")}</span>`; }
function renderStars(o){
  const mine = (A.my[o.id]||{}).stars || 0; const eff = A.hStar || mine;
  let h = `<div class="stars" title="${esc(t("rate"))}">`;
  for(let i=1;i<=5;i++) h += `<span class="star${i<=eff?" f":""}" onmouseenter="A.hStar=${i};window.render()" onmouseleave="A.hStar=0;window.render()" onclick="doRate(${o.id},${i})">★</span>`;
  return h + "</div>";
}
function trustBlock(o, compact){
  const a = agg(o.id); const p = pctOf(a); const n = totalOf(a); const my = A.my[o.id]||{};
  const canVote = active(o);
  const head = p==null
    ? `<div class="trust-hero"><span class="trust-n" style="color:var(--g4)">—</span><span class="idx-l">${num(n)} ${t("votes")} ${t("thismonth")}</span></div><div class="ns">${t("notenough")} · ${num(Math.max(0,MIN_SAMPLE-n))} ${t("needmore")}</div>`
    : `<div class="trust-hero"><span class="trust-n" style="color:${acol(p)}">${p}%</span><span class="idx-l">${t("trust")} · ${num(n)} ${t("votes")} ${t("thismonth")}</span></div>
       <div class="meter"><span class="meter-up" style="width:${p}%"></span><span class="meter-dn" style="width:${100-p}%"></span></div>`;
  const stars = avgStars(a);
  const voteRow = canVote ? `<div class="vrow">
      <button class="vbtn ${my.vote==="up"?"vu":""}" onclick="doVote(${o.id},'up')"><i class="ti ti-thumb-up"></i> ${t("trust")}</button>
      <button class="vbtn ${my.vote==="dn"?"vd":""}" onclick="doVote(${o.id},'dn')"><i class="ti ti-thumb-down"></i> ${t("distrust")}</button></div>
    <div class="myvote">${A.user ? (my.vote ? `${t("yourvote")}: <strong>${my.vote==="up"?t("trust"):t("distrust")}</strong> · ${t("changeok")}` : t("novote")) : `<button class="linkbtn" onclick="setState({showAuth:true})">${t("sl")}</button>`}</div>` : "";
  if(compact) return `<div class="sent-box">${head}${voteRow}</div>`;
  return `<div class="sent-box">${head}
    <div style="display:flex;align-items:center;gap:10px;margin-top:10px;flex-wrap:wrap">${canVote?renderStars(o):""}<span style="font-size:13px;color:var(--g4)">${stars?`${stars} / 5 · ${num(a.stars.cnt)}`:t("rate")}</span></div>
    ${voteRow}
    <div class="anon"><i class="ti ti-shield-lock"></i><span>${t("anon")}</span></div>
  </div>${renderTrustChart(o)}`;
}
function subCard(s){
  const CAT = {allegation:["#f8e9e5","#8a3a28"],corruption:["#f8e9e5","#8a3a28"],promise:["#f8f0de","#7a5308"],achievement:["#e6f3ea","#1f5c38"],statement:["#e3f1f2","#0a3f45"],response:["#e3f1f2","#0a3f45"],general:["#eef0f4","#3b4559"]};
  const c = CAT[s.category]||CAT.general; const catL = {allegation:t("cAll"),corruption:t("cCor"),promise:t("cPro"),achievement:t("cAch"),statement:t("cSta"),response:t("cResp"),general:t("cGen")}[s.category]||s.category;
  return `<div class="sub-card"><div class="sbadges"><span class="cbadge" style="background:${c[0]};color:${c[1]}">${esc(catL)}</span><span class="sevbadge" style="background:var(--g2);color:var(--g4)">${esc(s.severity)}</span><span class="crebadge" style="background:var(--g2);color:var(--g4)">${esc(s.credibility)}</span></div>
    <div class="sum">${esc(s.summary)}</div>
    ${(s.key_claims||[]).length?`<ul class="claims">${s.key_claims.map(c=>`<li>${esc(c)}</li>`).join("")}</ul>`:""}
    <div class="smeta">${s.sourceUrl?`<a href="${esc(s.sourceUrl)}" target="_blank" rel="noopener nofollow"><i class="ti ti-link"></i> ${esc(new URL(s.sourceUrl).hostname)}</a>`:""}<span>${s.publishedAt?new Date(s.publishedAt).toLocaleDateString(LOC()):""}</span>${s.moderatorNote?`<span>· ${esc(s.moderatorNote)}</span>`:""}</div></div>`;
}
function renderTab(o){
  const subs = A.published[o.id]||[];
  if(A.tab==="bio") return `${trustBlock(o,true)}
    <div class="bio-grid">
      <div class="bi"><div class="bk">${t("br")}</div><div class="bv">${esc(L(o,"role"))}${statusBadge(o)}</div></div>
      <div class="bi"><div class="bk">${t("ba")}</div><div class="bv">${esc(L(o,"party"))}</div></div>
      <div class="bi"><div class="bk">${t("bsi")}</div><div class="bv">${esc(o.since)}</div></div>
      <div class="bi"><div class="bk">${t("bl")}</div><div class="bv">${esc(L(o,"loc"))}</div></div>
    </div>
    <div class="stitle">${t("bs")}</div><p class="btx">${esc(L(o,"bio"))}</p>
    ${(o.tenure||[]).length?`<div style="margin-top:1.1rem"><div class="stitle">${t("bten")}</div>${[...o.tenure].reverse().map(tn=>`<div class="tenure"><strong>${esc(lang==="ar"?tn.roleAr:tn.roleEn)}</strong> · ${esc(tn.start||"")} – ${tn.end?esc(tn.end):t("present")}${tn.source?` · <a href="${esc(tn.source)}" target="_blank" rel="noopener" style="color:var(--blue-md)"><i class="ti ti-link"></i></a>`:""}</div>`).join("")}</div>`:""}
    ${(o.cv||[]).length?`<div style="margin-top:1.1rem"><div class="stitle">${t("bca")}</div>${o.cv.map(c=>`<div class="cvi"><div class="cvd"></div><div><div class="cvy">${esc(c.y)}</div><div class="cvr">${esc(lang==="ar"?c.r.ar:c.r.en)}</div><div class="cvo">${esc(lang==="ar"?c.o.ar:c.o.en)}</div></div></div>`).join("")}</div>`:""}
    ${(L(o,"iss")||[]).length?`<div style="margin-top:1.1rem"><div class="stitle">${t("bi")}</div><div class="tgs" style="justify-content:flex-start">${(lang==="ar"?o.issAr:o.issEn).map(i=>`<span class="tg">${esc(i)}</span>`).join("")}</div></div>`:""}
    ${(o.sources||[]).length?`<div style="margin-top:1.1rem" class="srcs"><div class="stitle">Sources</div>${o.sources.slice(0,8).map(s=>`<a href="${esc(s.url)}" target="_blank" rel="noopener">${esc(s.outlet||s.url)}</a>`).join("")}</div>`:""}`;
  if(A.tab==="prom"){
    const ps = subs.filter(s=>s.category==="promise"||s.category==="achievement");
    return `<div class="stitle">${t("pt")}</div>${(o.proms||[]).length?o.proms.map(p=>`<div class="prom-item"><span class="ps ps-${p.s[0]}">${t("p"+p.s[0])}</span><span class="ptx">${esc(lang==="ar"?p.ar:p.en)}${p.source?` <a href="${esc(p.source)}" target="_blank" rel="noopener" style="color:var(--blue-md)"><i class="ti ti-link"></i></a>`:""}</span></div>`).join(""):`<div class="empty">—</div>`}
    ${ps.length?`<div class="stitle" style="margin-top:1rem">${t("pcs")}</div>${ps.map(subCard).join("")}`:""}`;
  }
  if(A.tab==="alleg"){
    const as = subs.filter(s=>s.category==="allegation"||s.category==="corruption"||s.category==="response");
    return `<div class="ai-note"><i class="ti ti-file-text"></i><span>${t("record_note")}</span></div>${(o.allegs||[]).length?`<div class="stitle">${t("ta")}</div>${o.allegs.map(a=>`<div class="alleg-item"><div class="at">${esc(lang==="ar"?a.ar:a.en)}</div><div class="ad">${esc(lang==="ar"?a.dar:a.den)}</div>${a.src?`<div class="asrc"><i class="ti ti-file-text"></i> ${esc(a.src)}</div>`:""}</div>`).join("")}`:""}
    ${as.length?`<div class="stitle" style="margin-top:.85rem">${t("acs")}</div>${as.map(subCard).join("")}`:""}
    ${!(o.allegs||[]).length&&!as.length?`<div class="empty"><i class="ti ti-shield-check"></i>${t("ae")}</div>`:""}
    <div class="reply-box"><span>${t("reply_s")}</span><button class="btn" onclick="setState({showSubmit:true,result:null,err:null,asOffice:true})"><i class="ti ti-message-reply"></i> ${t("reply")}</button></div>`;
  }
  if(A.tab==="comm") return `<div class="ai-note"><i class="ti ti-shield-check"></i><span>${t("cn")}</span></div>${subs.length?subs.map(subCard).join(""):`<div class="empty"><i class="ti ti-file-plus"></i>${t("ce")}</div>`}`;
  if(A.tab==="trust") return trustBlock(o,false);
  return "";
}
function renderSubmit(o){
  const r = A.result;
  return `<div class="sov" onclick="if(event.target.classList.contains('sov'))setState({showSubmit:false})"><div class="smod" style="direction:${lang==='ar'?'rtl':'ltr'};overflow-y:auto">
    <div class="smhd"><div><div style="font-size:15px;font-weight:600">${t("stl")}</div><div style="font-size:12px;color:var(--g4)">${esc(N(o))}</div></div><button class="xbtn" onclick="setState({showSubmit:false})"><i class="ti ti-x"></i></button></div>
    <div class="smbody">
      <div class="ai-note"><i class="ti ti-info-circle"></i><span>${t("si2")}</span></div>
      ${r ? `<div class="pend"><i class="ti ti-clock"></i> ${t("rt")} — ${t("thanks")}</div>${subCard(r)}<button class="btn" onclick="setState({showSubmit:false,result:null})">${t("lc")}</button>` : `
      <div class="who"><label class="${A.asOffice?"":"on"}"><input type="radio" name="who" ${A.asOffice?"":"checked"} onchange="setState({asOffice:false})"> ${t("who_public")}</label><label class="${A.asOffice?"on":""}"><input type="radio" name="who" ${A.asOffice?"checked":""} onchange="setState({asOffice:true})"> ${t("who_office")}</label></div>
      <input class="inp" type="url" placeholder="${esc(t("src_ph"))}" value="${esc(A.surl)}" oninput="A.surl=this.value">
      <textarea class="sta" rows="6" placeholder="${esc(t("txt_ph"))}" oninput="A.stxt=this.value">${esc(A.stxt)}</textarea>
      ${A.err?`<div class="err"><i class="ti ti-alert-triangle"></i>${esc(A.err)}</div>`:""}
      <button class="btn btn-p" onclick="doSubmit()" ${A.analyzing?"disabled":""}><i class="ti ti-${A.analyzing?"loader-2 spin":"send"}"></i> ${A.analyzing?t("analyzing"):t("ab")}</button>`}
    </div></div></div>`;
}
function renderAuth(){
  const btn = (id, bg, fg, border, icon, label) => `<button class="socbtn" style="background:${bg};color:${fg};border:1.5px solid ${border}" onclick="doLogin('${id}')" ${A.authLoading?"disabled":""}><span class="sic">${A.authLoading===id?`<i class="ti ti-loader-2 spin"></i>`:icon}</span><span style="flex:1;text-align:start;font-size:14px">${A.authLoading===id?t("li"):label}</span></button>`;
  return `<div class="aov" onclick="if(event.target.classList.contains('aov'))setState({showAuth:false})"><div class="amod" style="direction:${lang==='ar'?'rtl':'ltr'}">
    <div class="alogo"><div class="alogo-ic"><i class="ti ti-eye"></i></div><div class="atitle">${t("lt")}</div><div class="asub">${t("ls")}</div></div>
    ${!fb.ready?`<div class="pend">Firebase is not configured. Fill in config.js.</div>`:""}
    ${btn("google","#fff","#3c4043","#dadce0",`<i class="ti ti-brand-google"></i>`,t("lg"))}
    ${btn("facebook","#1877f2","#fff","#1877f2",`<i class="ti ti-brand-facebook"></i>`,t("lf"))}
    ${btn("x","#000","#fff","#000",`<i class="ti ti-brand-x"></i>`,t("lx"))}
    <div class="anon"><i class="ti ti-shield-lock"></i><span>${t("anon")}</span></div>
    <button class="acancel" onclick="setState({showAuth:false})">${t("lc")}</button>
  </div></div>`;
}
function renderMod(){
  const list = A.pendingList;
  return `<div class="aov" onclick="if(event.target.classList.contains('aov'))setState({showMod:false})"><div class="amod" style="max-width:640px;direction:${lang==='ar'?'rtl':'ltr'};max-height:85vh;overflow:auto">
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px"><strong>${t("pending")}</strong><button class="xbtn" onclick="setState({showMod:false})"><i class="ti ti-x"></i></button></div>
    ${list==null?`<div class="empty"><i class="ti ti-loader-2 spin"></i></div>`:!list.length?`<div class="empty">${t("none_pending")}</div>`:list.map(p=>{ const o=byId(p.officialId); return `<div class="mod-item">
      <div><strong>${esc(o?N(o):p.officialId)}</strong> · ${esc(p.category)} · ${esc(p.severity)} · ${esc(p.credibility)}${p.needs_source?' · <span style="color:var(--amber)">needs source</span>':''}</div>
      <div style="margin:4px 0">${esc(p.summary)}</div>${p.moderator_note?`<div style="font-size:12px;color:var(--g4)">${esc(p.moderator_note)}</div>`:""}
      ${p.sourceUrl?`<a href="${esc(p.sourceUrl)}" target="_blank" rel="noopener nofollow" style="font-size:12px">${esc(p.sourceUrl)}</a>`:""}
      <div class="raw">${esc(p.rawText)}</div>
      <div style="display:flex;gap:8px"><button class="btn btn-p" onclick="doModerate(${p.officialId},'${esc(p.id)}','publish')">${t("publish")}</button><button class="btn" onclick="doModerate(${p.officialId},'${esc(p.id)}','reject')">${t("reject")}</button></div></div>`; }).join("")}
  </div></div>`;
}
function renderLog(){
  const items = [...A.changelog].reverse().slice(0,100);
  return `<div class="aov" onclick="if(event.target.classList.contains('aov'))setState({showLog:false})"><div class="amod" style="max-width:600px;direction:${lang==='ar'?'rtl':'ltr'};max-height:85vh;overflow:auto">
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px"><strong>${t("changelog")}</strong><button class="xbtn" onclick="setState({showLog:false})"><i class="ti ti-x"></i></button></div>
    ${items.length?items.map(c=>`<div class="tenure"><strong>${esc((TR[lang].chg||{})[c.type]||c.type)}</strong> · ${esc(lang==="ar"?c.nameAr:c.nameEn)} · ${esc(lang==="ar"?c.roleAr:c.roleEn)} · ${esc(c.date)}<div style="font-size:12px;color:var(--g4)">${esc(lang==="ar"?c.detail_ar:c.detail_en)} ${(c.sources||[]).map(s=>`<a href="${esc(s.url)}" target="_blank" rel="noopener">${esc(s.outlet||"source")}</a>`).join(" ")}</div></div>`).join(""):`<div class="empty">—</div>`}
  </div></div>`;
}
function header(back){
  return `<header class="hdr">
    ${back?`<button class="btn" onclick="setState({sel:null,showSubmit:false})"><i class="ti ti-arrow-${lang==='ar'?'right':'left'}"></i> ${t("back")}</button>`:""}
    <a class="logo" href="#" onclick="event.preventDefault();setState({sel:null,showSubmit:false})"><div class="logo-eye"><i class="ti ti-eye"></i></div><div class="logo-nm">${t("sn")}<span>${t("sub")}</span></div></a>
    <div class="hdr-r">
      <button class="lang-btn" onclick="toggleLang()">${t("ltog")}</button>
      ${A.isMod?`<button class="btn" onclick="setState({showMod:true,pendingList:null});loadPending()"><i class="ti ti-shield-check"></i> ${t("mod")}</button>`:""}
      ${A.user?`<div class="upill" title="${t("so")}" onclick="doLogout()"><div class="uav" style="background:var(--blue-lt);color:var(--blue)"><i class="ti ti-user"></i></div><span style="font-size:13px">${t("so")}</span></div>`:`<button class="btn btn-p" onclick="setState({showAuth:true})"><i class="ti ti-login"></i> ${t("si")}</button>`}
    </div></header>`;
}
function renderProfile(o){
  const subs = A.published[o.id]||[];
  const ac = (o.allegs||[]).length + subs.filter(s=>s.category==="allegation"||s.category==="corruption").length;
  const tabs = [["bio",t("tb")],["prom",t("tp")],["alleg",t("ta")+(ac?` <span class="status-badge" style="background:#fee2e2;color:#991b1b">${ac}</span>`:"")],["comm",t("tc")+(subs.length?` <span class="status-badge">${subs.length}</span>`:"")],["trust",t("ts")]];
  document.getElementById("app").innerHTML = `${header(true)}
<div class="pp-hero"><div class="pp-photo-ring">${pEl(o,108)}</div><div class="pp-name">${esc(N(o))}</div><div class="pp-role-badge">${esc(L(o,"role"))}${o.status!=="active"?` · ${o.status==="deceased"?t("deceased"):t("former")}`:""}</div>
  <div class="share-bar">
    ${navigator.share?`<button class="sh-btn sh-copy" onclick="shareOn('native',${o.id})"><i class="ti ti-share"></i> ${t("share")}</button>`:""}
    <button class="sh-btn sh-x" onclick="shareOn('x',${o.id})"><i class="ti ti-brand-x"></i> X</button>
    <button class="sh-btn sh-fb" onclick="shareOn('facebook',${o.id})"><i class="ti ti-brand-facebook"></i> Facebook</button>
    <button class="sh-btn sh-wa" onclick="shareOn('whatsapp',${o.id})"><i class="ti ti-brand-whatsapp"></i> WhatsApp</button>
    <button class="sh-btn sh-tg" onclick="shareOn('telegram',${o.id})"><i class="ti ti-brand-telegram"></i> Telegram</button>
    <button class="sh-btn sh-copy" onclick="shareOn('copy',${o.id})"><i class="ti ti-link"></i> ${t("copy")}</button>
  </div></div>
<div class="pp-tabs-bar">${tabs.map(([id,l])=>`<button class="pp-tab${A.tab===id?" on":""}" onclick="setState({tab:'${id}'})">${l}</button>`).join("")}</div>
<div class="pp-body">${renderTab(o)}</div>
<div class="pp-footer"><span class="pp-footer-hint">${t("fn")}</span><button class="btn btn-p" onclick="setState({showSubmit:true,result:null,err:null})"><i class="ti ti-file-plus"></i> ${t("sb2")}</button></div>
${A.showSubmit?renderSubmit(o):""}${A.showAuth?renderAuth():""}${A.showMod?renderMod():""}`;
  const h = "#"+o.slug; if(location.hash !== h && location.hash !== "#p"+o.id) history.pushState(null,"",h);
  if(A.tab==="trust") wireChart(o);
}
function movers(){
  const cur = monthKey(), prev = prevMonthKey(cur);
  const rows = A.officials.filter(active).map(o => { const a = pctOf(agg(o.id,cur)), b = pctOf(agg(o.id,prev)); return a!=null&&b!=null ? {o, d:a-b, a} : null; }).filter(Boolean);
  if(!rows.length) return "";
  const up = [...rows].sort((x,y)=>y.d-x.d).filter(r=>r.d>0).slice(0,5), dn = [...rows].sort((x,y)=>x.d-y.d).filter(r=>r.d<0).slice(0,5);
  const row = r => `<div class="mv-row" onclick="openOfficial(${r.o.id})">${pEl(r.o,28)}<span>${esc(N(r.o))}</span><span class="mv-d ${r.d>0?"mv-up":"mv-dn"}">${r.d>0?"+":""}${r.d} <small style="font-weight:400;color:var(--g4)">(${r.a}%)</small></span></div>`;
  return `<div class="movers"><div class="mv"><h3>${t("movers_up")} · ${t("vs")}</h3>${up.length?up.map(row).join(""):`<div class="ns">—</div>`}</div><div class="mv"><h3>${t("movers_dn")} · ${t("vs")}</h3>${dn.length?dn.map(row).join(""):`<div class="ns">—</div>`}</div></div>`;
}
function orgChart(list){
  const pres = list.find(o=>o.grp==="president"); const sec = list.filter(o=>o.grp==="security"); const cab = list.filter(o=>o.grp==="gov");
  const card = (o, cls, sz) => { const p = pctOf(agg(o.id)); const c = acol(p); return `<div class="oc-card ${cls}" onclick="openOfficial(${o.id})">${pEl(o,sz)}<div class="oc-nm">${esc(N(o))}</div><div class="oc-rl">${esc(L(o,"role"))}</div><div class="oc-aprow"><div class="oc-bar-track"><div class="oc-bar-fill" style="width:${p==null?0:p}%;background:${cls==="oc-pres"?"rgba(255,255,255,.65)":c}"></div></div><span class="oc-pct" style="color:${cls==="oc-pres"?"#fff":c}">${p==null?"—":p+"%"}</span></div></div>`; };
  return `<div class="oc-root"><div class="oc-t1">${pres?card(pres,"oc-pres",84):""}</div><div class="oc-divider"><span>${lang==='ar'?'الحقائب السيادية':'Sovereign portfolios'}</span></div><div class="oc-t2">${sec.map(o=>card(o,"oc-sov",58)).join("")}</div><div class="oc-divider"><span>${lang==='ar'?'الوزارات':'Cabinet'}</span></div><div class="oc-t3">${cab.map(o=>card(o,"oc-cab",46)).join("")}</div></div>`;
}
function card(o){
  const a = agg(o.id); const p = pctOf(a); const n = totalOf(a); const c = acol(p); const my = A.my[o.id]||{}; const iss = (lang==="ar"?o.issAr:o.issEn)||[];
  return `<div class="pcard" onclick="openOfficial(${o.id})">${pEl(o,68)}
    <div class="pc-name">${esc(N(o))}</div><div class="pc-role">${esc(L(o,"role"))}</div>
    <span class="rbadge" style="background:${o.bg};color:${o.col}">${o.grp==="governor"?esc(L(o,"gov")):grpLbl(o)}${o.status!=="active"?` · ${t("former")}`:""}</span>
    <div class="ap-row" style="width:100%"><span class="ap-l">${t("trust")}</span><span class="ap-p" style="color:${c}">${p==null?`<span title="${esc(t("notenough"))}">— · ${num(n)}</span>`:p+"%"}</span></div>
    <div class="ap-bar" style="width:100%"><div class="ap-fill" style="width:${p==null?0:p}%;background:${c}"></div></div>
    <div class="tgs">${iss.slice(0,2).map(i=>`<span class="tg">${esc(i)}</span>`).join("")}</div>
    ${active(o)?`<div class="qv-row" onclick="event.stopPropagation()"><button class="qv-btn qv-up${my.vote==="up"?" on":""}" onclick="doVote(${o.id},'up')"><i class="ti ti-thumb-up"></i></button><button class="qv-btn qv-dn${my.vote==="dn"?" on":""}" onclick="doVote(${o.id},'dn')"><i class="ti ti-thumb-down"></i></button></div>`:""}
  </div>`;
}
function render(){
  if(!A.loaded){ return; }
  if(A.sel){ const o = byId(A.sel); if(o){ renderProfile(o); return; } }
  const cur = monthKey();
  const FILT = [["all",t("fa")],["president",t("fp")],["security",t("fs")],["gov",t("fg")],["governor",t("fgov")],["parliament",t("fpar")],["former",t("fformer")]];
  const q = A.search.trim().toLowerCase();
  const pool = A.filter==="former" ? A.officials.filter(o=>!active(o)) : A.officials.filter(active);
  const filtered = pool.filter(o => (A.filter==="all"||A.filter==="former"||o.grp===A.filter) && (!q || L(o,"name").toLowerCase().includes(q) || L(o,"role").toLowerCase().includes(q) || (o.nameEn+o.nameAr).toLowerCase().includes(q)));
  const sorted = [...filtered].sort((a,b)=>{
    if(A.sort==="trust"){ const pa = pctOf(agg(a.id)), pb = pctOf(agg(b.id)); return (pb??-1)-(pa??-1) || totalOf(agg(b.id))-totalOf(agg(a.id)); }
    if(A.sort==="rating") return (Number(avgStars(agg(b.id)))||0)-(Number(avgStars(agg(a.id)))||0);
    return L(a,"name").localeCompare(L(b,"name"), lang);
  });
  let up=0, dn=0; A.officials.forEach(o=>{ const a=agg(o.id,cur); if(a){ up+=a.up||0; dn+=a.dn||0; } });
  const idx = up+dn >= MIN_SAMPLE ? Math.round(100*up/(up+dn)) : null;
  const showOrg = A.filter==="all" && !A.viewGrid && !q;
  document.getElementById("app").innerHTML = `${header(false)}
<section class="hero"><div class="hero-in"><h1 class="hero-title">${t("sn")}</h1><p class="hero-sub">${t("hero_s")}</p>
  <div class="hero-stats">
    <div class="hs"><div class="hs-n">${num(A.officials.filter(active).length)}</div><div class="hs-l">${t("h_off")}</div></div>
    <div class="hs"><div class="hs-n">${num(up+dn)}</div><div class="hs-l">${t("h_vt")}</div></div>
    <div class="hs"><div class="hs-n">${idx==null?"—":idx+"%"}</div><div class="hs-l">${t("h_idx")}</div></div>
    <div class="hs"><div class="hs-n" style="font-size:18px;padding-top:8px">${esc(A.meta.updated||"—")}</div><div class="hs-l">${t("h_upd")} · <a href="#" onclick="event.preventDefault();setState({showLog:true})">${t("changelog")}</a></div></div>
  </div>
  <div class="hero-note">${fmtMonth(cur)} · ${t("idx_sub")}${idx==null?` · ${t("idx_none")}`:""}</div>
  <div class="principles">${[["p1","file-certificate"],["p2","scale"],["p3","message-reply"]].map(([k,ic])=>`<div class="pr"><i class="ti ti-${ic}"></i><div><strong>${t(k)}</strong>${t(k+"s")}</div></div>`).join("")}</div>
</div></section>
<main class="main">
  ${movers()}
  <div class="filters"><span class="fl">${t("sb")}</span>${FILT.map(([id,l])=>`<button class="fb${A.filter===id?" on":""}" onclick="setState({filter:'${id}',viewGrid:false})">${l}</button>`).join("")}
    <div class="search-wrap"><i class="ti ti-search search-ico"></i><input id="sk-search" class="search-inp" type="text" placeholder="${esc(t("search"))}" value="${esc(A.search)}" oninput="A.search=this.value;window.render()"></div>
    ${!showOrg?`<select class="ss" onchange="setState({sort:this.value})"><option value="trust"${A.sort==="trust"?" selected":""}>${t("sap")}</option><option value="rating"${A.sort==="rating"?" selected":""}>${t("sr")}</option><option value="name"${A.sort==="name"?" selected":""}>${t("sn2")}</option></select>`:""}
    ${A.filter==="all"&&!q?`<button class="oc-toggle" onclick="setState({viewGrid:!A.viewGrid})"><i class="ti ti-${A.viewGrid?"hierarchy":"grid-dots"}"></i> ${A.viewGrid?(lang==="ar"?"الهيكل":"Org chart"):(lang==="ar"?"شبكة":"Grid")}</button>`:""}
  </div>
  ${showOrg ? orgChart(A.officials.filter(active)) : `<div class="grid">${sorted.length?sorted.map(card).join(""):`<div class="empty" style="grid-column:1/-1">—</div>`}</div>`}
  <div class="footer">${t("footer")}<br>
    <a href="${DATA}officials.json">officials.json</a> · <a href="${DATA}trust/trust.csv">trust.csv</a> · <a href="${DATA}changelog.json">changelog.json</a> · <a href="README.md">${t("method")}</a>
    ${A.user?` · <button class="linkbtn" onclick="doDeleteAccount()">${t("del")}</button>`:""}
  </div>
</main>
${A.showAuth?renderAuth():""}${A.showMod?renderMod():""}${A.showLog?renderLog():""}`;
  const inp = document.getElementById("sk-search"); if(inp && q !== "" && document.activeElement !== inp){ /* keep typing focus */ }
}
window.render = render;

// ── boot ──────────────────────────────────────────────────────────────────────
async function init(){
  document.documentElement.lang = lang; document.documentElement.dir = lang==="ar"?"rtl":"ltr";
  try { await loadStatic(); } catch(e){ document.getElementById("app").innerHTML = `<div class="empty">Could not load data/officials.json (${esc(e.message)})</div>`; return; }
  A.loaded = true;
  initFirebase();
  routeFromHash();
  window.addEventListener("hashchange", routeFromHash);
  document.addEventListener("keydown", e => { if(e.key==="Escape"){ if(A.showSubmit) setState({showSubmit:false}); else if(A.showAuth) setState({showAuth:false}); else if(A.showMod) setState({showMod:false}); else if(A.showLog) setState({showLog:false}); else if(A.sel) setState({sel:null}); } });
  // keep the search box focused across re-renders
  document.addEventListener("input", e => { if(e.target.id==="sk-search"){ const v = e.target.selectionStart; requestAnimationFrame(()=>{ const i = document.getElementById("sk-search"); if(i){ i.focus(); i.setSelectionRange(v,v); } }); } });
  render();
}
init();
})();
