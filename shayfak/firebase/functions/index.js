/**
 * Shayfak Cloud Functions.
 *
 * Privacy model, in one paragraph: the browser signs in with Google, Facebook or X only so that one person
 * cannot vote twice. The functions never store the account id, name, email or photo. Every write is keyed by
 * HMAC-SHA256(VOTER_HASH_KEY, uid), and the key lives in Secret Manager, not in the database. Someone holding a
 * full copy of the database cannot map a ballot back to a person. Someone holding the database AND the key
 * AND the Firebase Auth user list could; that is why the key is separate and why nothing else about the user
 * is written anywhere.
 *
 * Clients cannot write to the database at all (see ../database.rules.json). All writes go through here.
 *
 * Data layout
 *   monthly/{officialId}/{YYYY-MM}        public aggregates: {up, dn, inside:{up,dn}, verified:{up,dn}, stars:{sum,cnt}}
 *   ballots/{officialId}/{YYYY-MM}/{hash} private: {v: 1|-1|0, s: 0-5, inside, verified, ts}
 *   voters/{hash}/{YYYY-MM}/{officialId}  private: {v, s}   (lets a voter see their own month)
 *   limits/{hash}/{bucket}                private: counters for rate limiting
 *   pending/{officialId}/{id}             private: submissions waiting for a moderator
 *   published/{officialId}/{id}           public: moderated submissions, never with a submitter identity
 *   rejected/{officialId}/{id}            private
 *   site/updated                          public: last time anything changed
 */
const { onCall, HttpsError } = require("firebase-functions/v2/https");
const { defineSecret, defineString } = require("firebase-functions/params");
const { setGlobalOptions } = require("firebase-functions/v2");
const admin = require("firebase-admin");
const crypto = require("crypto");

admin.initializeApp();
setGlobalOptions({ region: "europe-west1", maxInstances: 20 });

const VOTER_HASH_KEY = defineSecret("VOTER_HASH_KEY");
const ANTHROPIC_API_KEY = defineSecret("ANTHROPIC_API_KEY");
// Set to "false" only while you are wiring up App Check in a test project.
const ENFORCE_APP_CHECK = defineString("ENFORCE_APP_CHECK", { default: "true" });
const CLAUDE_MODEL = defineString("CLAUDE_MODEL", { default: "claude-opus-5-5" });

const MAX_OFFICIAL_ID = 100000;
const VOTE_WRITES_PER_HOUR = 60;
const SUBMISSIONS_PER_DAY = 5;
const MAX_SUBMISSION_CHARS = 8000;

const db = () => admin.database();

function monthKey(d = new Date()) {
  return `${d.getUTCFullYear()}-${String(d.getUTCMonth() + 1).padStart(2, "0")}`;
}

function voterHash(uid) {
  const key = VOTER_HASH_KEY.value();
  if (!key || key.length < 32) throw new HttpsError("failed-precondition", "VOTER_HASH_KEY secret is not configured");
  return crypto.createHmac("sha256", key).update(uid).digest("hex").slice(0, 32);
}

function countryOf(req) {
  // Cloudflare in front of the site sets cf-ipcountry; Google's load balancer sets x-country-code on some paths.
  // The country is used only as a flag ("inside Syria" or not). The address itself is never stored.
  const h = req.rawRequest?.headers || {};
  const c = h["cf-ipcountry"] || h["x-country-code"] || h["x-appengine-country"] || "";
  return String(c).toUpperCase();
}

function requireUser(req) {
  if (!req.auth?.uid) throw new HttpsError("unauthenticated", "Sign in to vote.");
  return req.auth;
}

function parseOfficialId(v) {
  const n = Number(v);
  if (!Number.isInteger(n) || n < 1 || n > MAX_OFFICIAL_ID) throw new HttpsError("invalid-argument", "bad officialId");
  return n;
}

async function rateLimit(hash, bucket, limit) {
  const ref = db().ref(`limits/${hash}/${bucket}`);
  const res = await ref.transaction((cur) => (cur || 0) + 1);
  const n = res.snapshot.val() || 0;
  if (n > limit) throw new HttpsError("resource-exhausted", "Too many requests. Try again later.");
}

function callOpts(extra = {}) {
  return {
    enforceAppCheck: ENFORCE_APP_CHECK.value() !== "false",
    consumeAppCheckToken: false,
    secrets: [VOTER_HASH_KEY],
    ...extra,
  };
}

/** Cast, change or withdraw this month's vote and/or star rating for one official. */
exports.castVote = onCall(callOpts(), async (req) => {
  const auth = requireUser(req);
  const officialId = parseOfficialId(req.data?.officialId);
  const vote = req.data?.vote;             // "up" | "dn" | null
  const starsIn = req.data?.stars;         // 1..5 | null | undefined (undefined = leave unchanged)
  if (vote !== "up" && vote !== "dn" && vote !== null && vote !== undefined) throw new HttpsError("invalid-argument", "bad vote");
  if (starsIn !== undefined && starsIn !== null && !(Number.isInteger(starsIn) && starsIn >= 1 && starsIn <= 5)) throw new HttpsError("invalid-argument", "bad stars");

  const hash = voterHash(auth.uid);
  const month = monthKey();
  const hourBucket = `${month}-${new Date().getUTCDate()}-${new Date().getUTCHours()}`;
  await rateLimit(hash, hourBucket, VOTE_WRITES_PER_HOUR);

  const inside = countryOf(req) === "SY";
  const verified = auth.token?.verified === true;   // custom claim set by a future verification function
  const ballotRef = db().ref(`ballots/${officialId}/${month}/${hash}`);
  const prev = (await ballotRef.get()).val() || { v: 0, s: 0 };

  const newV = vote === undefined ? prev.v : vote === "up" ? 1 : vote === "dn" ? -1 : 0;
  const newS = starsIn === undefined ? prev.s || 0 : starsIn === null ? 0 : starsIn;
  const ballot = { v: newV, s: newS, inside, verified, ts: Date.now() };

  await db().ref(`monthly/${officialId}/${month}`).transaction((cur) => {
    const a = cur || { up: 0, dn: 0, inside: { up: 0, dn: 0 }, verified: { up: 0, dn: 0 }, stars: { sum: 0, cnt: 0 } };
    a.inside = a.inside || { up: 0, dn: 0 };
    a.verified = a.verified || { up: 0, dn: 0 };
    a.stars = a.stars || { sum: 0, cnt: 0 };
    const dec = (obj, v) => { if (v === 1) obj.up = Math.max(0, (obj.up || 0) - 1); if (v === -1) obj.dn = Math.max(0, (obj.dn || 0) - 1); };
    const inc = (obj, v) => { if (v === 1) obj.up = (obj.up || 0) + 1; if (v === -1) obj.dn = (obj.dn || 0) + 1; };
    // remove the previous ballot's contribution (using the flags it was cast with), then add the new one
    dec(a, prev.v); if (prev.inside) dec(a.inside, prev.v); if (prev.verified) dec(a.verified, prev.v);
    inc(a, newV); if (inside) inc(a.inside, newV); if (verified) inc(a.verified, newV);
    if (prev.s) { a.stars.sum = Math.max(0, a.stars.sum - prev.s); a.stars.cnt = Math.max(0, a.stars.cnt - 1); }
    if (newS) { a.stars.sum += newS; a.stars.cnt += 1; }
    return a;
  });

  const updates = {};
  updates[`ballots/${officialId}/${month}/${hash}`] = ballot;
  updates[`voters/${hash}/${month}/${officialId}`] = { v: newV, s: newS };
  updates["site/updated"] = admin.database.ServerValue.TIMESTAMP;
  await db().ref().update(updates);

  const agg = (await db().ref(`monthly/${officialId}/${month}`).get()).val();
  return { month, officialId, vote: newV === 1 ? "up" : newV === -1 ? "dn" : null, stars: newS || null, aggregate: agg };
});

/** The caller's own votes for the current month: {officialId: {vote, stars}}. Nothing else about them exists. */
exports.getMyVotes = onCall(callOpts(), async (req) => {
  const auth = requireUser(req);
  const hash = voterHash(auth.uid);
  const month = monthKey();
  const snap = await db().ref(`voters/${hash}/${month}`).get();
  const out = {};
  Object.entries(snap.val() || {}).forEach(([id, b]) => {
    out[id] = { vote: b.v === 1 ? "up" : b.v === -1 ? "dn" : null, stars: b.s || null };
  });
  return { month, votes: out };
});

/** Submit a report about an official. Claude classifies it; a moderator publishes it. The submitter is never shown. */
exports.submitReport = onCall(callOpts({ secrets: [VOTER_HASH_KEY, ANTHROPIC_API_KEY], timeoutSeconds: 120 }), async (req) => {
  const auth = requireUser(req);
  const officialId = parseOfficialId(req.data?.officialId);
  const text = String(req.data?.text || "").trim();
  const sourceUrl = String(req.data?.sourceUrl || "").trim().slice(0, 500);
  const lang = req.data?.lang === "en" ? "en" : "ar";
  const officialName = String(req.data?.officialName || "").slice(0, 200);
  const asOfficial = req.data?.asOfficial === true; // a response or correction from the official or their office
  if (text.length < 20) throw new HttpsError("invalid-argument", "Text too short");
  if (text.length > MAX_SUBMISSION_CHARS) throw new HttpsError("invalid-argument", "Text too long");
  if (sourceUrl && !/^https?:\/\//i.test(sourceUrl)) throw new HttpsError("invalid-argument", "Source must be a URL");

  const hash = voterHash(auth.uid);
  await rateLimit(hash, `sub-${new Date().toISOString().slice(0, 10)}`, SUBMISSIONS_PER_DAY);

  const Anthropic = require("@anthropic-ai/sdk").default;
  const client = new Anthropic({ apiKey: ANTHROPIC_API_KEY.value() });
  const schema = {
    type: "object",
    properties: {
      category: { type: "string", enum: ["allegation", "corruption", "promise", "achievement", "statement", "response", "general"] },
      severity: { type: "string", enum: ["low", "medium", "high", "critical"] },
      credibility: { type: "string", enum: ["unverified", "plausible", "likely", "confirmed"] },
      summary: { type: "string" },
      key_claims: { type: "array", items: { type: "string" } },
      tags: { type: "array", items: { type: "string" } },
      needs_source: { type: "boolean" },
      moderator_note: { type: "string" },
    },
    required: ["category", "severity", "credibility", "summary", "key_claims", "tags", "needs_source", "moderator_note"],
    additionalProperties: false,
  };
  const response = await client.beta.messages.create({
    model: CLAUDE_MODEL.value(),
    max_tokens: 4000,
    betas: ["server-side-fallback-2026-07-01"],
    fallbacks: "default",
    system:
      `You classify public submissions for Shayfak, a Syrian political accountability site. Respond in ${lang === "ar" ? "Arabic" : "English"}. ` +
      "Summarise neutrally in two or three sentences, list the concrete claims, and say whether the text is only an opinion or an insult " +
      "(then category 'general', severity 'low'). 'credibility' describes the evidence given, not the truth of the claim: 'confirmed' only when a " +
      "named reputable source with a URL is cited. Set needs_source when a factual allegation has no source. Never include names of private individuals in the summary. " +
      (asOfficial ? "This text is submitted as a response or correction by the official or their office: use category 'response' and summarise their position faithfully." : ""),
    messages: [{ role: "user", content: `Official: ${officialName}\nSource URL given: ${sourceUrl || "none"}\n\nSubmission:\n${text}` }],
    output_config: { format: { type: "json_schema", schema } },
  });
  if (response.stop_reason === "refusal") throw new HttpsError("failed-precondition", "The text could not be processed.");
  const textBlock = response.content.find((b) => b.type === "text");
  const result = JSON.parse(textBlock.text);
  if (asOfficial) result.category = "response";

  const ref = db().ref(`pending/${officialId}`).push();
  await ref.set({
    ...result,
    sourceUrl: sourceUrl || null,
    rawText: text.slice(0, 2000),
    lang,
    asOfficial,
    ts: Date.now(),
    by: hash,                    // for rate limiting and abuse review only; never copied to 'published'
  });
  return { id: ref.key, status: "pending", analysis: result };
});

/** Moderators publish or reject pending submissions. Requires the custom claim moderator=true (see README). */
exports.moderate = onCall(callOpts(), async (req) => {
  const auth = requireUser(req);
  if (auth.token?.moderator !== true && auth.token?.admin !== true) throw new HttpsError("permission-denied", "Moderators only");
  const officialId = parseOfficialId(req.data?.officialId);
  const id = String(req.data?.id || "");
  const action = req.data?.action;
  const note = String(req.data?.note || "").slice(0, 500);
  if (!/^[-\w]{10,40}$/.test(id)) throw new HttpsError("invalid-argument", "bad id");
  if (action !== "publish" && action !== "reject") throw new HttpsError("invalid-argument", "bad action");

  const pRef = db().ref(`pending/${officialId}/${id}`);
  const sub = (await pRef.get()).val();
  if (!sub) throw new HttpsError("not-found", "No such pending submission");

  const updates = {};
  if (action === "publish") {
    const { by, rawText, ...pub } = sub; // never publish the submitter hash or the raw text
    updates[`published/${officialId}/${id}`] = { ...pub, publishedAt: Date.now(), moderatorNote: note || null };
  } else {
    updates[`rejected/${officialId}/${id}`] = { ...sub, rejectedAt: Date.now(), moderatorNote: note || null };
  }
  updates[`pending/${officialId}/${id}`] = null;
  updates["site/updated"] = admin.database.ServerValue.TIMESTAMP;
  await db().ref().update(updates);
  return { ok: true, action };
});

/** List pending submissions for moderators. */
exports.listPending = onCall(callOpts(), async (req) => {
  const auth = requireUser(req);
  if (auth.token?.moderator !== true && auth.token?.admin !== true) throw new HttpsError("permission-denied", "Moderators only");
  const snap = await db().ref("pending").get();
  const out = [];
  Object.entries(snap.val() || {}).forEach(([officialId, items]) => {
    Object.entries(items || {}).forEach(([id, s]) => {
      const { by, ...rest } = s;
      out.push({ officialId: Number(officialId), id, ...rest });
    });
  });
  out.sort((a, b) => (a.ts || 0) - (b.ts || 0));
  return { pending: out };
});

/** Admins grant or revoke the moderator claim. The first admin is set with scripts/set_claim.js. */
exports.setModerator = onCall(callOpts(), async (req) => {
  const auth = requireUser(req);
  if (auth.token?.admin !== true) throw new HttpsError("permission-denied", "Admins only");
  const uid = String(req.data?.uid || "");
  const moderator = req.data?.moderator === true;
  if (!uid) throw new HttpsError("invalid-argument", "uid required");
  const user = await admin.auth().getUser(uid);
  await admin.auth().setCustomUserClaims(uid, { ...(user.customClaims || {}), moderator });
  return { ok: true, uid, moderator };
});

/** Delete everything the caller's account has produced, then the account itself (GDPR-style erasure). */
exports.deleteMyAccount = onCall(callOpts(), async (req) => {
  const auth = requireUser(req);
  const hash = voterHash(auth.uid);
  // Ballots are not removed from aggregates on purpose: aggregates contain no identity, and retroactively
  // changing published monthly results would let an attacker probe who voted how. The link is destroyed instead.
  await db().ref(`voters/${hash}`).remove();
  await db().ref(`limits/${hash}`).remove();
  await admin.auth().deleteUser(auth.uid);
  return { ok: true };
});
