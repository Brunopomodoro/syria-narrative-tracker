#!/usr/bin/env node
/**
 * One-off: give a user the admin or moderator claim from your own machine.
 * Needs a service-account key: GOOGLE_APPLICATION_CREDENTIALS=/path/key.json
 *
 *   node set_claim.js <uid> admin
 *   node set_claim.js <uid> moderator
 *   node set_claim.js <uid> none
 *
 * Find the uid in Firebase Console -> Authentication -> Users. Do this for yourself once; afterwards
 * grant moderators from the site with the setModerator function.
 */
const admin = require("firebase-admin");
admin.initializeApp();
const [uid, role] = process.argv.slice(2);
if (!uid || !["admin", "moderator", "none"].includes(role)) {
  console.error("usage: node set_claim.js <uid> admin|moderator|none");
  process.exit(1);
}
admin.auth().setCustomUserClaims(uid, role === "none" ? {} : { [role]: true, ...(role === "admin" ? { moderator: true } : {}) })
  .then(() => { console.log(`claims for ${uid} set to ${role}`); process.exit(0); })
  .catch((e) => { console.error(e.message); process.exit(1); });
