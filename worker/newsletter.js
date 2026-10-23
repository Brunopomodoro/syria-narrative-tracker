// The newsletter sign-up for syrianpulse.org, a Cloudflare Worker on www.syrianpulse.org/api/* (GUIDE.md, "Newsletter
// by email"). The site itself is static, so this is the only part that runs on a server.
//
//   POST /api/subscribe   the sign-up form: checks it, then emails a confirmation link (double opt-in), signed so it
//                         cannot be forged, valid 3 days. Nothing is stored until the link is clicked.
//   GET  /api/confirm     the link in that email: adds the address to the chosen Brevo lists (and takes it off the
//                         others, so filling in the form again changes the choices).
//
// The subscriber list lives only in Brevo. Secrets (set by the deploy workflow): BREVO_API_KEY, NEWSLETTER_SECRET.
// Settings (wrangler.toml / the workflow): SITE, SENDER_EMAIL, SENDER_NAME_EN, SENDER_NAME_AR.

const BREVO = "https://api.brevo.com/v3";
const KINDS = ["daily", "weekly", "monthly"];
const LIST_PREFIX = "syrianpulse";            // lists are named syrianpulse-<kind>-<lang>, as scripts/newsletter.py makes them
const TOKEN_DAYS = 3;
const PER_HOUR = 5;                           // sign-ups per visitor address and hour

const WORDS = {
  en: {
    subject: "Confirm your subscription to the Syria Narrative Tracker",
    hello: "Please confirm your subscription",
    body: "You asked to receive {what} from the Syria Narrative Tracker, in {langs}. Click the button to confirm. If you did not ask for this, ignore this email and nothing will be sent.",
    button: "Confirm my subscription",
    kinds: { daily: "the daily brief", weekly: "the weekly digest", monthly: "the monthly report" },
    langs: { ar: "Arabic", en: "English", both: "Arabic and English" },
    and: " and ",
  },
  ar: {
    subject: "أكّد اشتراكك في متتبّع السرديات السورية",
    hello: "يُرجى تأكيد اشتراكك",
    body: "طلبتَ استلام {what} من متتبّع السرديات السورية، {langs}. انقر الزر للتأكيد. إذا لم تطلب ذلك فتجاهل هذه الرسالة ولن يُرسل إليك شيء.",
    button: "تأكيد اشتراكي",
    kinds: { daily: "الموجز اليومي", weekly: "الملخص الأسبوعي", monthly: "التقرير الشهري" },
    langs: { ar: "بالعربية", en: "بالإنجليزية", both: "بالعربية والإنجليزية" },
    and: " و",
  },
};

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    try {
      if (url.pathname === "/api/subscribe" && request.method === "POST") return await subscribe(request, env);
      if (url.pathname === "/api/confirm" && request.method === "GET") return await confirm(url, env);
    } catch (e) {
      console.log("newsletter error", e && e.message);
      return back(env, (url.searchParams.get("p") || "en"), "error");
    }
    return new Response("Not found", { status: 404 });
  },
};

function back(env, page, what) {
  const lang = page === "ar" ? "ar" : "en";
  return Response.redirect(`${env.SITE}/subscribe/${lang}-${what}.html`, 303);
}

const b64url = (bytes) => btoa(String.fromCharCode(...new Uint8Array(bytes))).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
const unb64url = (s) => Uint8Array.from(atob(s.replace(/-/g, "+").replace(/_/g, "/") + "===".slice((s.length + 3) % 4)), (c) => c.charCodeAt(0));

async function key(env) {
  return crypto.subtle.importKey("raw", new TextEncoder().encode(env.NEWSLETTER_SECRET), { name: "HMAC", hash: "SHA-256" }, false, ["sign", "verify"]);
}

async function makeToken(env, data) {
  const body = b64url(new TextEncoder().encode(JSON.stringify(data)));
  const sig = await crypto.subtle.sign("HMAC", await key(env), new TextEncoder().encode(body));
  return `${body}.${b64url(sig)}`;
}

async function readToken(env, token) {
  const [body, sig] = String(token || "").split(".");
  if (!body || !sig) return null;
  const ok = await crypto.subtle.verify("HMAC", await key(env), unb64url(sig), new TextEncoder().encode(body));
  if (!ok) return null;
  const data = JSON.parse(new TextDecoder().decode(unb64url(body)));
  return data.x > Date.now() / 1000 ? data : null;
}

async function tooMany(request) {
  // a light limit per visitor address, kept in the edge cache for an hour
  const ip = request.headers.get("CF-Connecting-IP") || "unknown";
  const cache = caches.default, id = new Request(`https://ratelimit.invalid/${encodeURIComponent(ip)}`);
  const hit = await cache.match(id);
  const n = hit ? Number(await hit.text()) || 0 : 0;
  if (n >= PER_HOUR) return true;
  await cache.put(id, new Response(String(n + 1), { headers: { "Cache-Control": "max-age=3600" } }));
  return false;
}

async function brevo(env, method, path, body) {
  const r = await fetch(BREVO + path, {
    method, headers: { "api-key": env.BREVO_API_KEY, "content-type": "application/json", accept: "application/json" },
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!r.ok && r.status !== 204) throw new Error(`Brevo ${method} ${path}: HTTP ${r.status} ${await r.text()}`);
  return r.status === 204 ? {} : r.json().catch(() => ({}));
}

const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);

async function subscribe(request, env) {
  const form = await request.formData();
  const page = form.get("page") === "ar" ? "ar" : "en";
  if (String(form.get("website") || "")) return back(env, page, "check");          // the hidden field only bots fill in
  const email = String(form.get("email") || "").trim().toLowerCase();
  const kinds = KINDS.filter((k) => form.get(k));
  const lang = ["ar", "en", "both"].includes(form.get("lang")) ? form.get("lang") : page;
  if (!/^[^\s@<>"]{1,64}@[^\s@<>"]{1,190}\.[a-z]{2,}$/i.test(email) || email.length > 200 || !kinds.length) return back(env, page, "error");
  if (await tooMany(request)) return back(env, page, "error");
  const token = await makeToken(env, { e: email, k: kinds, l: lang, p: page, x: Math.floor(Date.now() / 1000) + TOKEN_DAYS * 86400 });
  const link = `${env.SITE}/api/confirm?t=${encodeURIComponent(token)}&p=${page}`;
  const w = WORDS[page], dir = page === "ar" ? "rtl" : "ltr";
  const what = kinds.map((k) => w.kinds[k]).join(w.and);
  const text = w.body.replace("{what}", what).replace("{langs}", w.langs[lang]);
  const html = `<!doctype html><html lang="${page}" dir="${dir}"><body style="margin:0;background:#F7F1E3;font-family:Arial,sans-serif;color:#1A1814">
<div style="max-width:560px;margin:0 auto;padding:28px 24px;text-align:${page === "ar" ? "right" : "left"}" dir="${dir}">
<div style="border-top:6px solid #8A6420;padding-top:18px;font-weight:bold;color:#8A6420">${esc(page === "ar" ? env.SENDER_NAME_AR : env.SENDER_NAME_EN)}</div>
<h1 style="font-size:22px;margin:18px 0 10px">${esc(w.hello)}</h1><p style="font-size:16px;line-height:1.6">${esc(text)}</p>
<p style="margin:26px 0"><a href="${esc(link)}" style="background:#8A6420;color:#fff;text-decoration:none;padding:12px 22px;border-radius:999px;font-weight:bold;display:inline-block">${esc(w.button)}</a></p>
<p style="font-size:12px;color:#6B6559;word-break:break-all">${esc(link)}</p></div></body></html>`;
  await brevo(env, "POST", "/smtp/email", {
    sender: { email: env.SENDER_EMAIL, name: page === "ar" ? env.SENDER_NAME_AR : env.SENDER_NAME_EN },
    to: [{ email }], subject: w.subject, htmlContent: html, textContent: `${w.hello}\n\n${text}\n\n${link}`, tags: ["confirmation"],
  });
  return back(env, page, "check");
}

async function confirm(url, env) {
  const data = await readToken(env, url.searchParams.get("t"));
  const page = (data && data.p) || url.searchParams.get("p") || "en";
  if (!data) return back(env, page, "error");
  const langs = data.l === "both" ? ["ar", "en"] : [data.l];
  const lists = (await brevo(env, "GET", "/contacts/lists?limit=50&offset=0")).lists || [];
  const ours = lists.filter((x) => String(x.name).startsWith(LIST_PREFIX + "-"));
  const want = new Set(data.k.flatMap((k) => langs.map((l) => `${LIST_PREFIX}-${k}-${l}`)));
  const listIds = ours.filter((x) => want.has(x.name)).map((x) => x.id);
  const unlinkListIds = ours.filter((x) => !want.has(x.name)).map((x) => x.id);
  if (!listIds.length) throw new Error("the newsletter lists do not exist yet: run the newsletter-setup task");
  await brevo(env, "POST", "/contacts", { email: data.e, listIds, updateEnabled: true, emailBlacklisted: false });
  if (unlinkListIds.length) {                  // earlier choices that were not ticked this time
    try { await brevo(env, "PUT", `/contacts/${encodeURIComponent(data.e)}`, { unlinkListIds }); } catch (e) { console.log("unlink", e.message); }
  }
  return back(env, page, "done");
}
