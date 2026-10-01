# شايفك · Shayfak

A bilingual (Arabic / English) accountability site for Syria's transitional government: every official with their
biography, promises and allegations, a **monthly trust vote**, and a chart of how trust moves over time.

This folder is a complete, deployable site. It shares the repository with the narrative tracker because the two
feed each other (the tracker's narratives can be linked from each official's page later).

```
shayfak/
  index.html, app.js, styles.css, config.js   the site (static; host on GitHub Pages, Firebase Hosting or Cloudflare Pages)
  data/officials.json                         the roster: who holds which office, bios, promises, allegations, tenure history
  data/changelog.json                         every personnel change applied, with sources
  data/pending_changes.json                   changes the rules could not confirm; a human approves or rejects them
  data/trust/                                 monthly vote aggregates exported as open data (JSON + CSV)
  p/<slug>.html                               one share page per official with Open Graph tags (generated)
  scripts/update_officials.py                 daily personnel check: Wikidata + Claude web search, photos, share pages
  scripts/snapshot_trust.py                   exports Firebase aggregates into data/trust/
  firebase/                                   database rules + Cloud Functions (the only thing that can write votes)
  tests/                                      offline tests for the pipeline logic
  config.yaml                                 pipeline settings
```

## How the pieces fit

| Concern | Where it lives | Why |
|---|---|---|
| Who the officials are | `data/officials.json` in git, updated by a GitHub Action | Every change is reviewable, diffable and sourced. No visitor can edit it. |
| Votes and ratings | Firebase Realtime Database, written only by Cloud Functions | One vote per account per official per month, enforced server side. |
| Community reports | Classified by Claude in a Cloud Function, published by a moderator | Nothing appears unreviewed; the submitter is never shown. |
| Trust history | `/monthly` in Firebase, snapshotted daily to `data/trust/` | Public, citable, survives a Firebase outage. |

### Privacy model (read this before launch)

- Sign-in (Google, Facebook or X) exists only to stop one person voting twice.
- The functions store a vote under `HMAC-SHA256(VOTER_HASH_KEY, uid)`. The key lives in Secret Manager, never in the database.
  A copy of the database alone cannot be mapped back to anyone. Name, email, photo and provider are never written anywhere.
- The browser never writes to the database (`firebase/database.rules.json` denies all client writes) and never holds an API key.
- "Inside Syria" is a flag derived from the request's country at the edge. The address itself is not stored.
- Users can delete their account from the footer; the link between their sign-in and their ballots is destroyed.
- What a powerful adversary could still learn: that a person *has* an account on Shayfak (from Google, Facebook or X), not how they voted. Say this on the site; the sign-in dialog does.

## Setup

### 1. Firebase project

1. Create a project at console.firebase.google.com and add a Web app. Paste its config into `config.js`.
2. **Authentication → Sign-in method**: enable Google, Facebook and Twitter/X. Under *Settings*, choose
   "Link accounts that use the same email" so one person with two providers counts once.
   - Facebook: create an app at developers.facebook.com, add *Facebook Login*, set the OAuth redirect to
     `https://<project>.firebaseapp.com/__/auth/handler`, publish a privacy policy URL and a data-deletion URL
     (point it at this site's footer "Delete my account"), then submit for App Review. Until review passes only test users can sign in.
   - X: create an app on developer.x.com with OAuth 1.0a enabled and the same callback URL.
3. **Realtime Database**: create it in `europe-west1`, then deploy the rules (step 3).
4. **App Check**: register the web app with reCAPTCHA v3, paste the site key into `config.js` → `appCheckSiteKey`,
   and enforce App Check for Realtime Database and Cloud Functions in the console.

### 2. Cloud Functions

```bash
cd shayfak/firebase/functions && npm install
firebase functions:secrets:set VOTER_HASH_KEY     # paste 64 random hex chars:  openssl rand -hex 32
firebase functions:secrets:set ANTHROPIC_API_KEY
cd .. && firebase deploy --only functions,database
```

The functions default to `ENFORCE_APP_CHECK=true`. Set the parameter to `false` only in a throwaway test project.

Give yourself the admin claim once (download a service-account key from *Project settings → Service accounts*):

```bash
GOOGLE_APPLICATION_CREDENTIALS=key.json node firebase/functions/set_claim.js <your-uid> admin
```

Admins can then grant moderators from the site (the "Moderation" button appears after sign-in).

### 3. The site

Any static host works. The repo is already served by GitHub Pages, so `https://<your-domain>/shayfak/` works as is;
for a clean domain, point it at this folder or use `firebase deploy --only hosting` from `shayfak/firebase/`
(that also sets the Content-Security-Policy and other headers in `firebase.json`). Set `siteUrl` in `config.js`
and `site_url` in `config.yaml` to the final address so share links carry a preview image.

### 4. The daily update

`.github/workflows/shayfak-update.yml` runs every day at 05:10 UTC with the repository's `ANTHROPIC_API_KEY` secret:

1. Wikidata: resolves each official and reads "position held" with start and end dates.
2. Claude with web search looks for appointments, resignations, dismissals, deaths and reshuffles since the last check,
   in Arabic and English, and returns them as JSON with source URLs.
3. A change is applied automatically only if Wikidata confirms it, or the model rates it high-confidence **and** cites
   an official source or two independent outlets (`config.yaml`). Everything else goes to `data/pending_changes.json`
   and the workflow opens or updates an issue labelled `shayfak-review`.
4. Photos are cached from Wikipedia, share pages are regenerated, and `snapshot_trust.py` exports the vote aggregates.

Review a pending change with:

```bash
python shayfak/scripts/update_officials.py --approve <id>     # or --reject <id>
```

Run the whole thing locally: `pip install -r shayfak/requirements.txt && python shayfak/scripts/update_officials.py --dry-run`.
Tests: `python -m pytest shayfak/tests`.

## Voting rules

- One ballot per account per official per calendar month (UTC). It can be changed until the month ends.
- A percentage is shown only when an official has at least `minSample` (30) votes that month, on the site and in the exports.
- Three series are kept: all voters, voters inside Syria, and verified voters (a custom claim `verified` that a future
  phone or Telegram verification function can set; nothing sets it yet).
- Aggregates are never edited retroactively, including when an account is deleted, so published numbers cannot be probed.

## Open data

`data/trust/trust.csv` (one row per official per month), `data/trust/index.json` (government-wide index),
`data/officials.json`, `data/changelog.json`. Licence: CC BY 4.0, same as the rest of the repository.

## What changed from the first prototype

- Seeded vote and rating counts and the hard-coded "sentiment breakdown" are gone. Counts start at zero and are real.
- The Claude API is no longer called from the browser (it had no key, so it never worked, and a key there would be public).
- Visitors can no longer write to the database; the old rules let any signed-in account rewrite officials and vote totals.
- Submitter names are no longer stored or shown; "AI verified" became "classified by AI, checked by a moderator".
- The 8 AM "auto-update" that ran in each visitor's browser became a daily server-side job with sources and a review queue.
- Photos are cached once by the pipeline instead of 110 Wikipedia requests per visit.
- Facebook sign-in added; the sign-in dialog explains exactly what the account is used for.
