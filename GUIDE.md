# Setup guide: Syria Narrative Tracker

This guide takes you from nothing to a live website that updates itself every hour. No coding is needed; everything happens in your web browser. Plan on about 45 minutes.

## What you will end up with

A public website at an address like `https://YOUR-NAME.github.io/syria-narrative-tracker/` showing the main narratives in Syrian online discussion over the last 24 hours, the tone around each one, and a 7–14 day "mosaic" of how the mood changed hour by hour.

Behind it, GitHub runs a small program every hour that collects public posts, asks Claude to analyze them, and saves the results. The website reads those results.

## What it costs

| Part | Cost |
|---|---|
| GitHub (runs the hourly job, hosts the website) | Free for public repositories |
| Telegram channels, news RSS feeds, Bluesky, Threads, Instagram hashtags and Reddit | Free |
| Claude API (the analysis) | Pay per use, see below |
| YouTube comments (optional) | Free within Google's daily quota |
| X / Twitter (optional) | About $0.005 per post read (roughly $36/month at default settings) |

Claude cost depends on how many posts you analyze and which model reads them. With the default settings (up to 800 posts per run) and the default model `claude-sonnet-5`, a run costs about 30 US cents (about 22 cents at 400 posts). GitHub currently runs the update every 4 to 6 hours, so that is roughly $1.35 a day, about $40 a month; if it ran every hour (extra E below) it would be about $220 a month. Two ways to spend less: switch `model` in `config.yaml` to `claude-haiku-4-5-20251001` (about half the cost, a less careful reading of dialect and sarcasm), or lower `max_posts` (for example to 150). Runs are skipped (free) when nothing new was posted, and every run prints its exact cost in the log. The weekly digest adds one call a week, a few cents.

---

## Step 1: Get your Claude API key

1. Go to **https://platform.claude.com** and create an account.
2. Open **Billing** and add credit. $10 is plenty for the first few days of testing.
3. Still in billing or limits settings, **set a monthly spend limit** (for example $50). This guarantees you can never be surprised by a bill.
4. Open **API keys** and click **Create key**. Name it `narrative-tracker`.
5. **Copy the key now** and keep it somewhere safe, like a password manager. It starts with `sk-ant-` and it is only shown once. Never paste it into any file or share it; you will store it in a secure place in step 5.

## Step 2: Create a GitHub repository

A repository ("repo") is a folder on GitHub that holds your project.

1. Go to **https://github.com** and create a free account if you don't have one.
2. Click the **+** in the top right corner, then **New repository**.
3. Repository name: `syria-narrative-tracker`
4. Choose **Public**. (Free website hosting needs a public repository. Your API key stays private regardless.)
5. Leave everything else as it is and click **Create repository**.

## Step 3: Upload the project files

1. Unzip `syria-narrative-tracker.zip` on your computer.
2. On your new repository page, click the link **uploading an existing file**. (If you don't see it: **Add file → Upload files**.)
3. Open the unzipped folder and drag these into the browser window:
   - `index.html`
   - `config.yaml`
   - `requirements.txt`
   - `README.md`
   - `GUIDE.md`
   - the whole `scripts` folder
4. Scroll down and click **Commit changes**.

## Step 4: Add the automation file

This file tells GitHub to run the program every hour. It lives in a folder called `.github`, which most computers hide, so it's easier to create it directly on GitHub.

1. In your repository, click **Add file → Create new file**.
2. In the file name box, type exactly: `.github/workflows/update.yml`
   (Each `/` you type turns the text before it into a folder. That's expected.)
3. Paste this into the big text area:

```yaml
name: Update narratives

on:
  schedule:
    - cron: "17 * * * *"   # every hour, at minute 17 (UTC)
  workflow_dispatch:        # adds a "Run workflow" button for manual runs

permissions:
  contents: write           # lets the job save new results into the repository

concurrency:
  group: update-narratives
  cancel-in-progress: false

jobs:
  update:
    runs-on: ubuntu-latest
    timeout-minutes: 15
    steps:
      - uses: actions/checkout@v5

      - uses: actions/setup-python@v6
        with:
          python-version: "3.12"
          cache: pip

      - name: Install
        run: pip install -r requirements.txt

      - name: Collect and analyze
        env:
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
          YOUTUBE_API_KEY: ${{ secrets.YOUTUBE_API_KEY }}
          X_BEARER_TOKEN: ${{ secrets.X_BEARER_TOKEN }}
          BLUESKY_HANDLE: ${{ secrets.BLUESKY_HANDLE }}
          BLUESKY_APP_PASSWORD: ${{ secrets.BLUESKY_APP_PASSWORD }}
          TELEGRAM_API_ID: ${{ secrets.TELEGRAM_API_ID }}
          TELEGRAM_API_HASH: ${{ secrets.TELEGRAM_API_HASH }}
          TELEGRAM_SESSION: ${{ secrets.TELEGRAM_SESSION }}
        run: python scripts/pipeline.py

      - name: Save results
        run: |
          git config user.name "narrative-bot"
          git config user.email "41898282+github-actions[bot]@users.noreply.github.com"
          git add data
          if git diff --cached --quiet; then
            echo "No changes to save."
          else
            git commit -m "Update narratives $(date -u +'%Y-%m-%d %H:%M UTC')"
            git pull --rebase
            git push
          fi
```

4. Click **Commit changes** (twice, if a confirmation box appears).

## Step 5: Store your API key as a secret

Secrets are encrypted. Nobody, including visitors to your public repository, can read them.

1. In your repository, click **Settings** (top menu, far right).
2. In the left menu: **Secrets and variables → Actions**.
3. Click **New repository secret**.
4. Name: `ANTHROPIC_API_KEY` (exactly like this, capital letters and underscores).
5. Secret: paste the key from step 1.
6. Click **Add secret**.

## Step 6: Run the first update

1. Click the **Actions** tab at the top of your repository.
2. If GitHub asks, click **I understand my workflows, go ahead and enable them**.
3. In the left list, click **Update narratives**.
4. On the right, click **Run workflow**, then the green **Run workflow** button.
5. After a few seconds a run appears. Wait 1–3 minutes for a green check mark.
6. Click the run, then **update**, then **Collect and analyze** to read the log. You'll see each source marked `ok` or `FAIL`, how many posts were found, and what the run cost.

A new `data` folder now appears in your repository. From here on, this happens automatically every hour.

## Step 7: Turn on the website

1. Go to **Settings → Pages** (left menu).
2. Under **Build and deployment**, set Source to **Deploy from a branch**.
3. Branch: **main**, folder: **/ (root)**. Click **Save**.
4. Wait 1–3 minutes and refresh the page. Your website address appears at the top of the Pages settings. Open it.

Bookmark it. The page also refreshes itself every 10 minutes.

## Step 8: Choose your sources

`config.yaml` comes with about 25 tested Telegram channels and news feeds across official, opposition-leaning, independent, Kurdish and regional outlets, in Arabic, English and Kurdish. Each one was checked to be public and posting recently when it was added. The tracker's value depends almost entirely on which sources you pick, so review the list and add the local channels you know. Druze (Suwayda) and coastal community channels are still missing, because none could be verified; add them when you find reliable ones.

**To find channels:** search Telegram for the outlets, cities and communities you care about. For each one, find its link (like `t.me/SomeChannel`) and test it by opening `https://t.me/s/SomeChannel` in your browser. If you can see posts there, the tracker can read it. (Private channels and groups can't be read.)

**Aim for balance.** Include official and state media, opposition-leaning outlets, Kurdish, Druze and coastal community channels, independent media, and local city news channels, in both Arabic and English. A tracker that only reads one side will only show one side's narratives.

**To edit:**

1. In your repository, click `config.yaml`, then the **pencil icon** (Edit).
2. Add channels under `telegram_channels`, copying the pattern exactly:

```yaml
  - name: SomeChannel
    label: "Readable name - who runs it"
    filter: false
```

   Use `filter: true` for general channels that post about many countries; the tracker then keeps only posts that mention one of the `keywords`.
3. Click **Commit changes**, then run the workflow manually (step 6) to test.
4. To see which sources work, open the **Actions** tab, click the latest run, then **Collect and analyze**. Each source has a line starting with `ok` or `FAIL` (with the reason).

**Spacing matters** in `config.yaml`: use spaces, never tabs, and line things up exactly like the existing entries.

---

## Optional extras

The starter sources are outlets: what channels and news sites publish. To hear ordinary people, add one or both of the public-voice sources below. The website then shows "How people are reacting" for each story, next to how outlets cover it.

### A1. Add YouTube comments (free, 10 minutes)

1. Go to **https://console.cloud.google.com** and sign in with a Google account.
2. At the top, click the project picker, then **New project**. Name it `narrative-tracker` and click **Create**. Make sure it's selected afterwards.
3. In the search bar at the top, type **YouTube Data API v3**, open it, and click **Enable**.
4. Open the menu (☰) → **APIs & Services → Credentials → Create credentials → API key**. Copy the key.
5. Recommended: click the new key, and under **API restrictions** choose **Restrict key** and tick **YouTube Data API v3**. Save.
6. In GitHub, add a secret named `YOUTUBE_API_KEY` with this key (same way as step 5).
7. In `config.yaml`, under `youtube:`, change `enabled: false` to `enabled: true`. Commit.
8. Run the workflow manually (step 6) and check the log for `ok    youtube`.

The default settings use most of Google's free daily allowance when the job runs every hour: each search term costs 100 units per run, while the `channels:` list under `youtube:` (comments under the newest videos of selected outlets' channels) costs only 2 units per channel plus 1 per video. So add channels freely, but keep search terms to three. No billing account is needed.

### A2. Add Telegram comments, reactions and groups (free, 20 minutes)

This is the richest source of Syrian public opinion: the comment sections under channel posts, the emoji reactions on each post (😡 👍 😢), and open community group chats. It needs a one-time login, which you'll do in your browser with Google Colab (nothing to install).

**Before you start:** the tracker reads Telegram as a normal user account. It's best to use a **separate Telegram account** (a second phone number) rather than your personal one. It doesn't need to join any channels.

**1. Get your Telegram API ID**

1. Go to **https://my.telegram.org** and log in with the phone number of the account you'll use. Telegram sends the code to your Telegram app.
2. Click **API development tools**.
3. Fill in App title: `narrative tracker`, Short name: `narrtracker`, Platform: **Desktop**. Leave the rest.
4. Click **Create application**. Copy the **api_id** (a number) and **api_hash** (letters and numbers).

**2. Create your login "session" in Google Colab**

1. Go to **https://colab.research.google.com** and click **New notebook**.
2. In the first box (cell), paste this and press the ▶ button:

```
!pip -q install telethon
```

3. Click **+ Code** to add a second cell, paste this, and press ▶:

```python
from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.errors import SessionPasswordNeededError
from getpass import getpass

api_id = int(input("API ID: "))
api_hash = input("API hash: ").strip()
phone = input("Phone number with country code, e.g. +963...: ").strip()

client = TelegramClient(StringSession(), api_id, api_hash)
await client.connect()
await client.send_code_request(phone)
code = input("Login code Telegram just sent to your Telegram app: ").strip()
try:
    await client.sign_in(phone, code)
except SessionPasswordNeededError:
    await client.sign_in(password=getpass("Your Telegram two-step verification password: "))
print("\nYour session string. Treat it like a password:\n")
print(client.session.save())
await client.disconnect()
```

4. Boxes appear under the cell asking for your API ID, API hash, phone number and the login code. Type each and press Enter.
5. A long line of letters and numbers is printed. That's your **session string**. Copy all of it.
6. **Delete the notebook afterwards** (File → Move to trash), because the session string is shown in it. Anyone with that string can use the Telegram account.

**3. Add three secrets in GitHub** (same way as step 5):

| Name | Value |
|---|---|
| `TELEGRAM_API_ID` | the api_id number |
| `TELEGRAM_API_HASH` | the api_hash |
| `TELEGRAM_SESSION` | the session string |

**4. Turn it on:** in `config.yaml`, under `telegram_api:`, change `enabled: false` to `enabled: true`. Commit, then run the workflow manually and look for `ok    comments` lines in the log.

**5. Choose channels with comment sections.** Comments are read from every channel in `telegram_channels`. Busy local and news channels with active comment sections give the best picture. To add public group chats, list them under `groups:` in the `telegram_api` section.

You can disconnect the tracker at any time: in the Telegram app, open **Settings → Devices** and end the session named after your app.

### B. Add X (Twitter) posts (paid)

X charges about $0.005 for every post the tracker reads, paid from credits you buy in advance. With the default setting (10 posts an hour) that's about 7,200 posts, roughly $36, a month. With 20 an hour, it's about $72.

1. Go to **https://console.x.com** and sign in with an X account.
2. Accept the Developer Agreement. When asked how you'll use the API, describe it plainly, for example: *"Non-commercial dashboard that summarizes public discussion about Syria. Posts are analyzed in aggregate only; no individual users are displayed, profiled or linked, and post text is not republished."*
3. In **Billing**, buy a small amount of credit (for example $10) and **set a spending limit**. Leave automatic top-up off until you've seen a few days of real costs.
4. Create a new **App** (any name, e.g. `narrative-tracker`). Copy the **Bearer Token**. It's shown only once, so keep it in your password manager.
5. In GitHub, add a secret named `X_BEARER_TOKEN` with the Bearer Token (same way as step 5).
6. X is already switched on in `config.yaml` (`enabled: true` under `x_twitter:`). If you ever want to stop paying for it, change that to `enabled: false`.
7. Run the workflow manually. The log shows a line like `X: 10 posts read, about $0.05`.

Good to know: the X search picks up everyone writing in Arabic about Syria, not only Syrians, so treat it as regional discussion. The tracker skips reposts and posts with links, which makes each paid post more likely to be someone's own opinion.

### A3. Reddit (free, already on) and Bluesky (free, 5 minutes)

Both are small next to Telegram and YouTube, and lean English-speaking and diaspora, so treat them as one extra window rather than a picture of Syria.

**Reddit** needs no key and is already on: the tracker reads the newest comments in r/syria and the Syria threads of r/Kurdistan (read together in one request, because Reddit allows GitHub's servers about one request a minute; r/syriancivilwar refuses them entirely). Reddit sometimes briefly limits requests from GitHub's servers. When that happens its line in the run log says `FAIL` for that hour, and it recovers on its own. Keep the list short for that reason.

**Bluesky** needs a free account, because Bluesky usually refuses searches from GitHub's servers without one:

1. Create an account at **https://bsky.app** (any account works; it never posts anything).
2. Go to **Settings → Privacy and security → App passwords → Add App Password**. Name it `narrative-tracker` and copy the password it shows.
3. Add two secrets in GitHub (same way as step 5): `BLUESKY_HANDLE` (for example `yourname.bsky.social`) and `BLUESKY_APP_PASSWORD`.
4. In `config.yaml`, under `bluesky:`, change `enabled: false` to `enabled: true`. Commit and run the workflow.

### A4. Add Threads posts (free, about an hour plus Meta's review)

Threads is the one Meta platform whose public posts you can search yourself. Meta's Threads API has a keyword search that returns recent public posts for a word, in Arabic too, for apps that Meta has approved.

1. You need a Threads account for the tracker (any account; it never posts). Sign in at **https://developers.facebook.com** with the Facebook or Instagram login attached to it, and click **My Apps → Create App**.
2. Choose the **Threads** use case (Meta calls it "Access the Threads API"), name the app `narrative-tracker` and create it.
3. In the app, open **Use cases → Threads API → Customize** and add the permissions `threads_basic` and `threads_keyword_search`.
4. Under **App roles → Roles**, add your Threads account as a **Threads tester**, then accept the invitation in the Threads app under **Settings → Account → Website permissions**.
5. Open **Tools → Graph API Explorer** (or the "User Token Generator" on the Threads use case page), choose your app, tick both permissions and generate a token. Exchange it for a long-lived token, which lasts 60 days: open in a browser
   `https://graph.threads.net/access_token?grant_type=th_exchange_token&client_secret=APP_SECRET&access_token=SHORT_TOKEN`
   (the app secret is under **App settings → Basic**). Copy the `access_token` from the answer.
6. In GitHub, add a secret named `THREADS_ACCESS_TOKEN` with that token (same way as step 5).
7. Submit the app for **App review** with the `threads_keyword_search` permission. Describe the use plainly, for example: *"Non-commercial research dashboard that summarizes public discussion about Syria in aggregate. Posts are analyzed as a batch by a language model; no individual users are displayed, profiled or linked, and post text is not republished."* Until Meta approves, the run log says `FAIL threads ... not approved for this app yet`; afterwards it says `ok    threads`.

The token expires after 60 days. Repeat step 5 and replace the secret when the log says the token was rejected. Meta allows about 2,200 searches a day; the five default search terms use at most 120 a day.

### A5. Add Instagram hashtag posts (free, needs a business account)

Instagram gives outsiders no comments and no timeline, but its official **hashtag search** returns the captions of recent public posts under a hashtag, up to 30 different hashtags a week. It is the only legitimate window into Instagram without an institutional agreement.

1. Turn the tracker's Instagram account into a **professional** account (**Settings → Account type and tools → Switch to professional account**, choose Business or Creator) and connect it to a Facebook Page (any page you own).
2. At **https://developers.facebook.com** create an app (or reuse the one from A4) with the **Instagram** use case and the **Instagram API with Facebook login**. Add the permissions `instagram_basic` and `pages_read_engagement`.
3. In **Tools → Graph API Explorer**, select the app, tick those permissions, and generate a token. Then find your Instagram user id: call `GET /me/accounts` and, for your page, `GET /PAGE_ID?fields=instagram_business_account`. The number in the answer is the **user id**.
4. Exchange the token for a long-lived one (60 days): `https://graph.facebook.com/v21.0/oauth/access_token?grant_type=fb_exchange_token&client_id=APP_ID&client_secret=APP_SECRET&fb_exchange_token=SHORT_TOKEN`.
5. Add two GitHub secrets: `INSTAGRAM_ACCESS_TOKEN` and `INSTAGRAM_USER_ID`.
6. Hashtag search works while the app is in development mode for the app's own testers, so the run log should show `ok    instagram` right away. To keep it working for the long term, submit the app for review with the `instagram_basic` permission and the "hashtag search" feature.

The hashtags are listed under `instagram:` in `config.yaml`. Meta counts unique hashtags per rolling week, so keep the list under 30.

### E. Reliable hourly updates

GitHub runs scheduled jobs late or skips them when its servers are busy, which is why the tracker updates every three to six hours rather than every hour, and why it once went 10 hours without one.

**Built in: the update keeper.** `.github/workflows/keeper.yml` makes sure the gap never grows past 5 hours: whenever an update finishes, it waits 5 hours and then starts the next one, and every update that finishes in the meantime restarts the countdown. It needs no token or account (it uses the repository's own built-in key) and costs nothing on GitHub (runner time is free for public repositories); each update it starts costs the usual Claude amount. Change `KEEPER_HOURS` in that file to change the gap (at most 5), or turn it off under **Actions → Update keeper → … → Disable workflow**. The keeper counts from the last real update, and a scheduled run that comes less than 3 hours after the last update skips itself (free), so the two never pile up; change `MIN_GAP_HOURS` in `update.yml` to change that.

**For updates on the hour,** a free external timer can start them on an exact schedule instead:

1. In GitHub, open **Settings → Developer settings → Personal access tokens → Fine-grained tokens → Generate new token**. Give it access to this repository only, with the permission **Actions: Read and write**, and an expiry of a year. Copy the token.
2. At **https://cron-job.org** (free) create a job that runs every hour and sends `POST https://api.github.com/repos/YOUR_USER/YOUR_REPO/actions/workflows/update.yml/dispatches` with the headers `Authorization: Bearer YOUR_TOKEN`, `Accept: application/vnd.github+json`, and the body `{"ref":"main"}`.

The scheduled job inside GitHub can stay as it is; the concurrency setting makes sure two updates never run at the same time. Hourly runs multiply the Claude cost accordingly (see "What it costs").

### F. Facebook and TikTok: the institutional route

Facebook comments and TikTok are the biggest missing voices, and neither can be read by a project like this on its own. Meta's **Content Library** (https://developers.facebook.com/docs/content-library-and-api/) gives access to public Facebook and Instagram posts, pages, groups and comments to researchers at academic and non-profit institutions, through an application handled by ICPSR at the University of Michigan. TikTok's **Research API** (https://developers.tiktok.com/products/research-api/) gives public videos and comments to academic researchers in the US, UK and EU. Both require an institutional affiliation, and Meta's data must be analysed inside its own secure environment, so only aggregate results (for example daily volume by keyword) could be exported to this site. A partnership with a university or think tank unlocks both. Scraping Facebook or Instagram through third-party services breaks Meta's terms and is not used here.

### G. Testing your sources

**Actions → Maintenance → Run workflow → test-sources** collects from every source without analysing or saving anything, and the log shows an `ok` or `FAIL` line for each. Run it after editing the source lists in `config.yaml`.

### C. Languages

Posts are read in Arabic, Kurdish (Kurmanji and Sorani) and English. Each post's language is detected automatically, and the "About" section of the website shows the language mix of every update. Kurdish coverage comes from Kurdish-run outlets (ANHA, North Press, Rudaw, Kurdistan24), the Kurdish YouTube and Bluesky search terms, and Kurdish words in the X search. The default model, `claude-sonnet-5`, reads Kurmanji more reliably than Haiku.

The website is fully bilingual. Everything is written in both English and Arabic, and visitors switch with the button at the top right; the site remembers their choice. To make the site open in Arabic by default, set `default_language: "ar"` in `config.yaml`. You can also link straight to either version by adding `?lang=ar` or `?lang=en` to your site address.

### D. Update less often to save money

In `.github/workflows/update.yml`, change `"17 * * * *"` to `"17 */2 * * *"` for every 2 hours, or `"17 */3 * * *"` for every 3 hours.

---

## For research use

Everything below is already switched on. This section explains what exists and the few things only you can do.

### The Trends and Data pages

- **Trends** shows how the discussion moved over time: the share and tone of each of the 12 fixed themes, people against outlets, the tone by language of the people posting and by kind of outlet, and markers for events. Add events under `events:` in `config.yaml` (date and a label in both languages); they appear on the charts after the next run. Every chart has a **Table** button.
- **Data** lets anyone download a date range as CSV or JSON, lists the monthly files and the daily archive, documents every column, and states the licence (CC BY 4.0, see `LICENSE-DATA.md`) with a ready citation.
- **About** now carries the full methodology: sampling, the model, the exact instructions given to it, the themes, the sources, the limitations, and a changelog. When you change sources, the model, sampling settings or the instructions, add a line under `method_changelog:` in `config.yaml` so the record stays complete.

### Themes

The 12 themes live under `themes:` in `config.yaml`, each with a description that tells the analysis what belongs where. You can reword labels and descriptions freely. Avoid changing an `id` or adding and removing themes casually: the trend charts and downloads compare themes across months by id, so a change breaks the continuity. If you do change them, run the **rebuild-index-and-exports** maintenance job afterwards.

### Story pages, daily briefs, weekly digests and feeds

- Every story has a permanent page in both languages (`stories/en/…`, `stories/ar/…`; the "Permanent page" link under each story on the tracker), with its full latest analysis, every update it appeared in, and share links. Cite those pages rather than the front page when you refer to a specific story.
- Every day with data has a **daily brief** (`daily/en/…`, `daily/ar/…`): the day in a word, the day in numbers with a theme chart, and every story of the day with its analysis. It is built from the archive at each update (no model call), so it costs nothing, and it has the same share links and print layout as the reports. The last seven days are listed on the Reports tab, every day under "All days".
- After every completed week the tracker writes a **weekly digest** in English and Arabic (`weekly/en/…`, `weekly/ar/…`), with the week's theme table. Each digest is a page with share links and a print layout, and a **PDF** next to it (`weekly/en/2026-W40.pdf` and so on). The digests are listed on the Reports tab and published as RSS feeds (`feed.xml`, `feed-ar.xml`), which newsletter tools and feed readers can follow. Turn this off with `weekly_digest: false` in `config.yaml`.
- After every completed month it writes a **monthly report** (`monthly/en/…`, `monthly/ar/…`), laid out as a one-page briefing for donors, organisations and journalists: key findings, the month in numbers with two charts, the analysis, the stories that mattered, what to watch, the weeks in brief, the stories that carried coordination signals, the theme and tone tables, and an "About this report" block with the method, the sources, the licence and a citation line. Each report has share links (X, Facebook, Telegram, WhatsApp, with hashtags; see below), a print layout, and a **PDF** made by `scripts/report_pdf.py` with the Chrome that GitHub's runners already have. Each PDF is one long page, as tall as the report, with no page breaks, laid out to be easy on the eye: one column, larger type, a band for each numbered part with a "↑ Contents" link back to the clickable contents, a line between stories, and bookmarks (the reader's sidebar) for every heading; a report taller than about 5 metres, which PDF readers do not handle, falls back to A4 pages. Set `PAGE_MODE = "a4"` in `scripts/report_pdf.py` to go back to A4 pages for all of them. The Reports tab lists the reports, the weekly digests and the daily briefs. A month needs at least 10 days of data. Turn it off with `monthly_review: false`.

### Newsletter by email

Readers can get the reports by email: on the sign-up page (`subscribe/en.html`, `subscribe/ar.html`, linked from the end of every report, the footer, the homepage and the Reports tab) they enter their address and choose **the daily brief, the weekly digest and/or the monthly report**, in **Arabic, English or both**. They then get an email asking them to confirm (double opt-in, so no one can sign up someone else), and from then on each report they chose arrives when it is published: the main points, the stories that mattered and, for the daily brief, what the media and experts said, with buttons to the full report and its PDF. Every email has an unsubscribe link and a link to change the choices (filling in the form again replaces them).

How it works: the site is static, so the sign-up goes through a small **Cloudflare Worker** (`worker/newsletter.js`, on `www.syrianpulse.org/api/*`), which sends the confirmation email and, once confirmed, adds the address to the right lists in **Brevo**, the mailing service. Brevo keeps the subscribers (never this repository, which is public) and sends the emails: after every update `scripts/newsletter.py` checks what is due and sends each report once per language to its list (`syrianpulse-daily-ar`, `syrianpulse-weekly-en` and so on). Yesterday's daily brief goes out once the media and experts analysis of the day is in (about 6:00 Damascus time), each weekly digest and monthly report as soon as it is written. What was sent is recorded in `data/newsletter.json` (counts only, no addresses).

**Cost.** Brevo's free plan has no limit on subscribers but sends at most **300 emails a day**, with a small Brevo logo in each email. The daily brief is one email per daily subscriber per day, so the free plan lasts up to about 250 daily subscribers; weekly and monthly subscribers cost little. Past that, a paid Brevo plan (priced by emails a month, from about $9) removes the limit and the logo; until then a report that would pass the limit waits for the next day and the update log says so. The Cloudflare Worker is free.

**Setting it up** (once, about half an hour):
1. **Brevo account.** Sign up at https://www.brevo.com (free plan). Give the organisation name and an address when asked (the law requires a postal address in newsletters; Brevo adds it to the footer). New accounts are sometimes reviewed before they can send campaigns; answer Brevo's questions honestly (a public research site, people sign up themselves with double opt-in).
2. **The sending address.** In Brevo, open **Senders, domains & dedicated IPs → Domains → Add a domain**, enter `syrianpulse.org` and choose to authenticate it yourself: Brevo shows a few DNS records (a Brevo code, DKIM and DMARC). Add each one in **Cloudflare → syrianpulse.org → DNS → Records** (proxy status "DNS only"), then click **Authenticate** in Brevo. Then under **Senders** add `newsletter@syrianpulse.org` with the name "Syria Narrative Tracker". To receive replies, forward that address to your own inbox with **Cloudflare → Email → Email Routing** (free).
3. **The API key.** In Brevo, **SMTP & API → API keys → Generate a new API key**. Add it as the repository secret `BREVO_API_KEY` at https://github.com/Brunopomodoro/syria-narrative-tracker/settings/secrets/actions/new.
4. **The lists.** Run **Actions → Maintenance → newsletter-setup**. It makes the six lists in Brevo.
5. **The Cloudflare token.** In Cloudflare, **My Profile → API Tokens → Create Token → "Edit Cloudflare Workers"**; under Account resources choose your account and under Zone resources `syrianpulse.org`; create it and add it as the secret `CLOUDFLARE_API_TOKEN`. Add your **Account ID** (on the right of the domain's Overview page in Cloudflare) as the secret `CLOUDFLARE_ACCOUNT_ID`.
6. **The Worker.** Run **Actions → Deploy newsletter worker**. It puts the sign-up on `www.syrianpulse.org/api/` and gives it the Brevo key.
7. **Switch it on.** Set `enabled: true` under `newsletter:` in `config.yaml` and run **rebuild-pages**: the sign-up page, the links and the newsletter section of the privacy page appear. Sign up yourself to test, and run **newsletter-check** to see the lists' sizes and what would be sent.

**newsletter-check** (Maintenance) shows the lists and how many subscribers each has, and what is due; it sends nothing. To stop sending, set `enabled: false`. To export or delete subscribers, use Brevo's **Contacts** page.

The monthly review's feeds (`feed-monthly.xml`, `feed-monthly-ar.xml`) still carry the full text of every review, so an RSS reader or another RSS-to-email service can use them too.

### Maintenance jobs

Open **Actions → Maintenance → Run workflow** and pick a task:

| Task | What it does | Cost |
|---|---|---|
| rebuild-index-and-exports | Recompute the per-day index, the monthly downloads and the methodology file from the archive. Run after editing themes, events or the changelog. | free |
| rebuild-pages | Rebuild every story page, daily brief, digest and report page, the listings, feeds and the sitemap, then the PDFs. Run after changing how pages look. | free |
| newsletter-setup | Make the newsletter's six lists in Brevo (once, after adding `BREVO_API_KEY`). | free |
| newsletter-check | Show the newsletter's lists, their subscriber counts and what would be sent now; sends nothing. | free |
| audience-snapshot | Rebuild the audience snapshot (indicators, report page and PDF) from the whole archive. | free |
| backfill-themes | Give a theme to archived stories that have none. | a few cents |
| backfill-weekly | Write the digest of every completed week that has none. | a few cents per week |
| backfill-monthly | Write the review of every completed month that has none. | about 15 cents per month |
| brand | Remake the logo files: icons, preview cards, wordmarks. Run after changing the site's name or tagline. | free |
| backfill-arabic | Translate Arabic text that past updates left empty or in English, then rebuild the pages. New updates do this themselves. | a cent or two |
| telegram-probe | Check Telegram channels before adding them: active, subscribers, last post, share of posts about Syria. Leave *names* empty for the built-in list, type channel names, or type `--discover` to find candidates from the channels' forwards and Syrian outlets' websites. | free |
| social-check | Check the Facebook and X keys and show the latest daily, weekly and monthly posts for each. Posts nothing. | free |
| quality-report | The tracker's health over the last 7 days compared with the 7 before: updates and gaps, outlet share, languages, failing or quiet sources, retries, missing Arabic, cost. It is printed in the job's log. | free |
| backfill-archive | Rebuild the archive from the git history of the results. Only needed if the archive is lost. | free |

### Quality log and weekly review

Every update adds one line to `data/quality.json` (kept for 60 days): posts collected and analysed, outlet share, languages, sources that failed or had nothing new, number of stories, retries, Arabic filled in afterwards, tokens and cost. It holds counts and source names only, never post text. `scripts/quality_report.py` (the **quality-report** maintenance task) turns it into a weekly summary, and a weekly Claude review reads that summary and the published pages, fixes small problems through pull requests and reports bigger ones.

### Contact page

Every page has a **Contact** link (menu and footer, both languages) to `contact/en.html` and `contact/ar.html`: a form with name (optional), email, topic (question, correction, media, partnership, technical problem) and message. Messages reach your inbox through **Web3Forms**, a free form service (250 messages a month), so your email address never appears on the site. The form works without any script, a hidden field catches simple spam bots, and after sending, visitors land on a thank-you page in their language.

To switch it on: open https://web3forms.com, enter the email address that should receive the messages and press **Create Access Key**; Web3Forms emails you a key. Put it under `contact: web3forms_access_key:` in `config.yaml` (the key is meant to be public; it only lets the form send to you). Until then the page points to `contact_url`.

### Support page

The site has a bilingual **Support** page (`support/en.html`, `support/ar.html`) that shows what the tracker costs (the analysis cost of the last 30 days, measured from its own records), what support pays for, the ways to give, where the money goes, the funding rules (no funder influences the findings, every institutional funder is named, no data about individuals is ever sold) and the list of funders. Its link appears in the menu and the footer only once at least one way to give is set.

**Where the money goes is decided by the account you link:**
- **Open Collective** (https://opencollective.com): create a collective and apply to a fiscal host (for a European project, a European host). The host holds the money, every payment and every expense is public, and you are paid back by submitting expenses such as the monthly Claude invoice. Best for credibility; the host takes a fee, shown on its page.
- **GitHub Sponsors** (https://github.com/sponsors): payments go to your GitHub account and then your bank. Simple; it is personal income.
- **Ko-fi** (https://ko-fi.com) or **PayPal**: payments go straight to you. Also personal income.

In Germany, money paid to you personally is taxable income; money held by a fiscal host or, later, a registered non-profit is not yours personally. A tax adviser can tell you which suits you.

To switch it on, put the link under `support:` in `config.yaml` (for example `open_collective: "https://opencollective.com/syrian-pulse"`). The page and links appear at the next update, or at once with the **rebuild-pages** maintenance task. Add institutional funders under `funders:` as they come.

### Posting to Facebook

Once set up, the tracker posts to its Facebook Page by itself: **yesterday's daily brief** every morning (the first update after 4:00 UTC, 7:00 in Damascus), each **weekly digest** once it is written (Monday), and each **monthly report** once it is written (early in the month). Each post has the headline, a few lines, the top stories or key findings, the link, the PDF link for digests and reports, hashtags, and a line saying it is an automatic summary. Arabic comes first and English below; the link preview shows the page's card. At most one post goes out per update, so a Monday with two reports spreads them out. What has been posted is kept in `data/social.json`, so nothing is posted twice and a failed post is tried again.

Setting it up takes about half an hour, all in a browser. Meta for Developers must be reachable from where you are (it is not from Syria).

**1. The Page.** On Facebook, open **Pages → Create new Page**. Name: `Syria Narrative Tracker | متتبّع السرديات السورية`. Category: *News & media website*. Bio: `ملخص آلي يومي وأسبوعي وشهري لما يُقال عن سوريا على الإنترنت. Automatic daily, weekly and monthly summaries of what is said about Syria online.` Add the website `https://www.syrianpulse.org`. Profile picture: `assets/avatar.png`. Cover: `assets/cover-facebook.png` (download both from the repository). Your own Facebook account must have **full control** of the Page.

**2. The app.** Go to https://developers.facebook.com, log in with the same Facebook account and accept the developer terms if asked. **My Apps → Create app**. Name: `Syrian Pulse poster`, your email as contact. Use case: **Manage everything on your Page**. Business portfolio: *I don't want to connect a business portfolio yet*. Finish with **Create app**.

**3. Permissions.** In the app, open **Use cases → Manage everything on your Page → Customize** and make sure `pages_manage_posts`, `pages_read_engagement` and `pages_show_list` are added.

**4. App settings.** Open **App settings → Basic** and fill in: Privacy policy URL `https://www.syrianpulse.org/privacy/en.html`; User data deletion → *Data deletion instructions URL* `https://www.syrianpulse.org/privacy/en.html#deletion`; App icon `assets/avatar.png`; Category *News*. **Save changes.**

**5. Live mode (important).** Posts made by an app in *development* mode are visible only to you, not to the public. Open **Publish** in the left menu (or switch **App mode** at the top from *Development* to *Live*) and publish the app. No App Review is needed: the app only posts to a Page you manage yourself.

**6. The Page token.** Open **Tools → Graph API Explorer** (https://developers.facebook.com/tools/explorer).
- Meta App: your app. User or Page: *Get User Access Token*. Add the permissions `pages_manage_posts`, `pages_read_engagement`, `pages_show_list`. Press **Generate Access Token** and, in the window that opens, choose your Page and allow everything.
- Press the **ⓘ** next to the token → **Open in Access Token Tool** → **Extend Access Token** at the bottom, and copy the long token it shows.
- Back in the Explorer, paste that long token into the *Access Token* field, type `me/accounts?fields=id,name,access_token` in the query box and press **Submit**. Under your Page, copy the `id` and the `access_token`.
- Check it: paste the Page token into the Access Token Debugger (https://developers.facebook.com/tools/debug/accesstoken). *Expires* should say **Never**, and the type **Page**.

**7. The secrets.** In this repository: **Settings → Secrets and variables → Actions → New repository secret**. Add `FB_PAGE_ID` (the id) and `FB_PAGE_TOKEN` (the Page access token). Optionally, add `FB_APP_SECRET` (App settings → Basic → App secret → Show) and turn on **Require app secret** under App settings → Advanced; then a stolen token alone cannot post. Never paste a token anywhere else, not in chat, an issue or a file.

**8. Check.** Run **Actions → Maintenance → social-check**. The log says "Token works: it can post to the Page …" and shows the posts that would go out. The first real post goes out at the next update; to post right away, run **Actions → Update narratives → Run workflow**.

**Good to know.**
- The Page token stops working if you change your Facebook password, leave the Page, or remove the app; the update log then says so, and posting resumes once you make a new token (step 6) and replace `FB_PAGE_TOKEN`. Updates of the site are never held up by Facebook.
- To pause posting, set `enabled: false` under `facebook:` in `config.yaml`. To show English first, set `first_lang: en`. To skip a kind, set `daily`, `weekly` or `monthly` to `false`.
- Turn on two-factor authentication on the Facebook account that owns the Page and the app.

### Posting to X

Once set up, the tracker posts to its X account, in English: yesterday's daily brief every morning, and each weekly digest and monthly report once written. (`languages`, `daily_languages` and `story_language` under `x:` set the language; add `ar` to post in Arabic too, which doubles the cost of those posts.) Each report post has the label and date, the headline, as much of the summary as fits, the link and up to three hashtags; every post stays within 280 characters. At most two report posts go out per update. The record in `data/social.json` keeps anything from going out twice.

**Story posts.** Between the reports, the account posts the current stories one at a time, in English, at hours that suit Europe and the US (Damascus time: 20:00 first, then 17:00, 22:00, 15:00 and 12:00). Stories that ordinary people talk about come first, then those where people and the media feel differently (the post then says so, which is what gets replies and shares), then new ones; a story is not posted again within 48 hours, and only stories with at least 5 comments from people count. A story post links to the story's page on the site, so readers can see the full picture, and is kept to about eight lines on a phone, because X folds longer posts behind "Show more" and hides the hashtags. Set `story_links: false` under `x:` to post stories without the link. The profile's bio and website field should also carry `syrianpulse.org`.

**Images and the link in a reply.** Every post carries an image card, drawn by `scripts/cards.py` with the same Chrome that makes the PDFs: the label and date, the headline, a meter for how people and the media feel (in words), one line of context (comments, or the most discussed themes) and @SyrianPulseOrg. The post itself goes out without a link, and the link follows at once in a reply ("التحليل الكامل: …" / "Full analysis: …"), because X shows posts with links to fewer people. The reply is the paid link post ($0.20) and the main post costs the plain price ($0.015), so a post with its reply costs $0.215; the budget counts both. If the card cannot be drawn or uploaded, the post goes out without it. **social-check** draws and uploads one card (nothing is posted) to show that images work. To look at sample cards: `python scripts/cards.py`. Set `images: false` or `link_in_reply: false` under `x:` to turn either off.

**Follow invitations on the site.** Every report, daily brief, story page and Media and experts page ends with a "Follow us on X" box (also in the PDFs, where the button links to the account), the homepage shows a follow line under the introduction, and every footer links to the account.

**A human voice.** The words of every X post (stories and reports) are written by Claude from the story's or report's own text, as a person would post it: a hook first, plain words, sometimes a question to invite replies, and a different opening from the last few posts. The rules: nothing that is not in the material, every number from the material, what people say rather than what is true, no individual commenter named or quoted, a neutral tone, no emojis. The link and hashtags are added afterwards by the code. A draft that brings in a number not in the material, runs too long, or fails for any reason is dropped, and the plain format goes out instead. It costs about a cent a post (about $2 a month on the Claude bill; **social-check** shows the month's total). Set `rewrite: false` under `x:` to go back to the plain format.

**The budget.** Every post costs money, and a post with a link costs much more: in October 2026 X charged about $0.015 for a plain post and $0.20 for one with a link (`cost_per_post_usd` and `cost_per_link_post_usd` under `x:`; correct them if the console shows other prices). Every post carries a link, so `monthly_budget_usd` (15 dollars) buys about 75 posts a month. The reports come first: about 31 daily briefs, 8 to 10 weekly posts and 2 monthly ones, about $8.40. What is left goes to story posts, spread evenly over the month (about 33, roughly one a day). When the month's dollars are used up, nothing more goes out until the 1st. **social-check** shows the numbers: spent this month, kept for the reports to come, left for stories, and the next story posts. Every page links to the account ("Follow on X" in the footer) and search engines see it as the site's profile.

**Cost.** X charges per post from prepaid credits; there has been no free tier for new developers since February 2026. Reported prices range from about 1 cent a post to 20 cents for a post with a link; check the price list in the console. The tracker keeps to the monthly budget set under `x:` (see The budget above), and a spending limit in the console is a second safeguard.

**1. The account.** Sign up at https://x.com/i/flow/signup with a new email for the tracker. Name `Syria Narrative Tracker`, handle such as `@SyrianPulse`. Profile picture `assets/avatar.png`, header `assets/cover-x.png`. Bio: `ملخص آلي يومي لما يُقال عن سوريا على الإنترنت · Automatic summaries of what is said about Syria online. syrianpulse.org`, and `https://www.syrianpulse.org` in the Website field (story posts point readers there). Turn on two-factor authentication at https://x.com/settings/account/login_verification.

**2. The automated label.** At https://x.com/settings/account/automation choose your personal X account as the managing account. The tracker's profile then shows "Automated by @you", which X's rules ask of bots.

**3. The developer account.** Logged in as the tracker's account, open https://developer.x.com and sign up. Describe the use honestly: "Posts the daily, weekly and monthly summaries of syrianpulse.org, a public research site, to this account. No reading of other accounts, no replies, no direct messages." Add a payment method, buy the minimum credits, and set a monthly spending limit.

**4. The app.** In the console, create an app (a default one may already exist). Open its **User authentication settings → Set up**: App permissions **Read and write**; Type of app **Web App, Automated App or Bot**; Callback URL `https://www.syrianpulse.org/`; Website `https://www.syrianpulse.org/`. Save.

**5. The keys.** Open the app's **Keys and tokens**:
- **API Key and Secret** (also called consumer keys): generate or regenerate, copy both.
- **Access Token and Secret**: generate, copy both. It must say **Read and Write**. If it says Read only, the token was made before step 4: regenerate it.

**6. The secrets.** At https://github.com/Brunopomodoro/syria-narrative-tracker/settings/secrets/actions/new add four secrets: `X_API_KEY`, `X_API_SECRET`, `X_ACCESS_TOKEN`, `X_ACCESS_TOKEN_SECRET`.

**7. Check.** Run **Actions → Maintenance → social-check** (https://github.com/Brunopomodoro/syria-narrative-tracker/actions/workflows/tools.yml). The log says "Keys work: they can post as @…" and shows the posts. The first posts go out at the next update, or at once with **Actions → Update narratives → Run workflow**.

**If posting stops**, the update log says why: no credits left (add credits), keys rejected (copy them again), or read-only (step 5). To pause, set `enabled: false` under `x:`.

### Facebook through Zapier

The site publishes two feeds of ready-made posts: `https://www.syrianpulse.org/feed-social-ar.xml` (Arabic) and `feed-social.xml` (English). Each item is one post for each daily brief (once the day's media and experts analysis is in, about 6:00 Damascus time), weekly digest and monthly report: the label and date, the headline, the mood of people and of the media in words, the brief or the key points, the top stories, the link and a few hashtags (no tone scores, no counts). `scripts/social.py` rewrites them every hour.

**Story posts.** Besides the reports, the Arabic feed gets `stories_per_day` story posts a day (under `facebook:` in config.yaml; 2 by default), at the first hours of `story_hours` (Damascus time: 14:00 and 21:00 for two a day). Each is the most discussed current story of the last day that the feed has not carried in the last two days: the headline, what people say and how they feel (written by Claude in a human voice, about a cent a post; the story's summary and reactions when Claude is not available), the mood of people and the media in words, the link to the story's page, hashtags and its image card. `feed_story_languages` sets the feeds (`[ar]`; add `en` for the English feed). Set `stories_per_day: 0` to stop them. So that Zapier's free plan never runs out (it would then pause the Zap until the next month, reports included), a story post is skipped when it would leave too few of the month's `zapier_monthly_limit` posts (100) for the reports still to come; set `zapier_cycle_day` to the day your Zapier usage resets (Zapier, **Settings → Usage**), or `zapier_monthly_limit: 0` on a paid plan.

To post them to the Facebook Page with **Zapier** (free plan: 100 posts a month; the reports need about 36 and two story posts a day about 60 more, so three or more a day need a paid Zapier plan):
1. Sign up at https://zapier.com and click **Create → Zaps**.
2. **Trigger:** search **RSS by Zapier**, event **New Item in Feed**, Feed URL `https://www.syrianpulse.org/feed-social-ar.xml`. Click **Test trigger**: it shows the newest item.
3. **Action:** search **Facebook Pages**, event **Create Page Post**. Connect your Facebook account (it must be an admin of the Page) and allow Zapier to post for the Page. Choose the Page. **Message:** pick the feed item's **Description**. **Link URL:** pick the item's **Link** (Facebook then shows the page's preview card).
4. **Test step** (this publishes one post to the Page; delete it afterwards if you like), then **Publish** the Zap.

**With a picture.** Each item of the Arabic feed carries an image card (`cards/ar/…png`: the headline and the mood of people and the media, drawn with Chrome by `scripts/cards.py`; `feed_images` under `facebook:` in config.yaml sets the languages). To post it as a photo with the text as its caption (photo posts reach more people than link posts), use the Facebook Pages action that uploads a photo (**Create Page Photo**, sometimes shown as "Upload Photo") instead of **Create Page Post**: **Photo / Photo URL:** the item's **Enclosure URL** (or **Media Content URL**); **Caption / Message:** the item's **Description**. The link to the full report is in the caption.

From then on, Zapier checks the feed every 15 minutes and posts each new item once. To post in English too, make a second Zap with `feed-social.xml`.

### Hashtags on the share links

The X, Facebook and Telegram links in the share bar of every daily brief, weekly digest, monthly report and story page carry hashtags chosen from the page: the tags that go on every share (`#Syria`, and `#سوريا` on Arabic pages), then the places and names found in the page's story titles (Hasakah, Aleppo, the Golan, the SDF, Captagon and so on, each in the page's language), then the tags of the page's main themes, then `#SyrianPulse`. The list is cut to what fits in a post on X, and X gets all of it, Telegram all of it under the text, and Facebook the first tag (its share dialog takes one). WhatsApp messages carry none.

The lists live under `share_hashtags:` in `config.yaml`: `always` by language, `themes` by theme id, `places` with the tag in each language and the spellings to look for in titles, `brand`, and `max` (the most tags on a share, 7 by default). Edit them freely; a theme with empty lists gets no tag of its own. Pages pick up a change at the next update, or at once with the **rebuild-pages** maintenance task.

### The logo

The logo is a speech bubble carrying a pulse line: what is being said, and how it moves. It is in the site's brass on a transparent background, and it is the same mark everywhere: the browser tab, the header of every page, the print header of the reports and digests (so it is on every PDF), the card shown when a page is shared on X, Facebook, Telegram or WhatsApp, the RSS feeds and the newsletter.

The files, all under `assets/`:

| File | Use |
|---|---|
| `logo.svg` | the mark, any size; `logo-mono.svg` is the same in ink for one-colour print |
| `logo-wordmark.svg`, `logo-wordmark-ar.svg` | the mark with the name in English or Arabic, as outlines (no font needed); the `-dark` versions have the name in white for dark backgrounds |
| `logo-wordmark.png`, `logo-wordmark-ar.png` | the same as PNG, 1600 px wide with a transparent background, for documents, slides and posts |
| `og.png`, `og-ar.png` | the preview card (1200 × 630) shown when a page is shared; pages pick the one in their language |
| `logo-512.png`, `logo-192.png`, `apple-touch-icon.png`, `favicon-32.png`, `favicon-16.png`, `favicon.ico` (at the root) | browser and home-screen icons |
| `logo-144.png` | the mark on paper, for the feeds and the newsletter |

When using it elsewhere, keep the mark whole and in one of its two colours, on a plain background, with clear space around it of at least a quarter of its height; do not stretch it or add effects.

`scripts/brand.py` draws the mark and makes all of these. After changing the name or the tagline, run the **brand** maintenance task (or `pip install fonttools uharfbuzz` and `python scripts/brand.py` on your computer, which needs Chrome) and the files are remade.

### Citing the tracker and getting a DOI

The website's Data page shows a ready citation and BibTeX, and the repository has a `CITATION.cff` file that GitHub turns into a **Cite this repository** button. Put your own name in `CITATION.cff` and `.zenodo.json` if you want to be cited as the author.

For a DOI that journals accept, use Zenodo (free, run by CERN):

1. Go to **https://zenodo.org**, sign in with GitHub, and open **GitHub** in your account menu.
2. Switch on the toggle next to `syria-narrative-tracker`.
3. In GitHub, open **Releases → Create a new release**. Tag: `v2026.09`, title: `Dataset, September 2026`. Publish it.
4. Zenodo archives that release within a few minutes and shows its DOI (like `10.5281/zenodo.1234567`) and a "concept DOI" that always points to the latest version.
5. Put the concept DOI in `config.yaml` (`doi: "10.5281/zenodo.1234567"`). After the next run it appears in the citation box on the website.

Make a new release every month or two; each one becomes a new versioned snapshot under the same concept DOI.

### Timeline

The Timeline page (`timeline/en.html`, `timeline/ar.html`) lists the main political, security and economic events since the fall of the Assad government on 8 December 2024. Each event has a date, an area (security, economy, governance), a region, one or two neutral sentences in English and Arabic, and at least two published sources; where sources give different figures, the range is shown. From September 2026, each event links to the tracker's daily brief of that day and the Media and experts analyses of that week. Events marked `key` also appear as markers on the Trends charts.

- **The file.** `data/timeline.json`. To correct or add an event, edit its entry (or ask Claude to); the page is rebuilt at the next update, or at once with the maintenance task **rebuild-pages**. Set `updated` to the day you checked it.
- **New events.** The weekly quality review proposes events from the stories that dominated the tracker and were confirmed by several international sources, with sources and draft wording. They are added only after the site owner approves them.

### Media and experts

The **Media and experts** tab (formerly the Media and experts; pages under `experts/`) is our analysis of what Syrian and international media, think tanks and international organisations say about Syria's security, economy and governance (`scripts/experts.py`). The site's division is **people vs media**: the tracker centres on what ordinary Syrians say, and this tab on what professional sources say.

- **Syrian media.** Syrian outlets (SANA, Syria TV, Enab Baladi, North Press, Halab Today, Zaman al-Wasl, Hawar, Al-Watan, Syria Direct, Al-Jumhuriya; `kind: syrian`) are a category of their own. Because the tracker already reads their daily news, the summarising step keeps from them only investigations, in-depth reports, analysis, interviews with officials and official statements. The analyses say whether a Syrian outlet is state-run, affiliated with the Kurdish-led administration or independent.
- **Compared with what people said.** Each analysis compares the media and experts with what ordinary Syrians said on the tracker, counting only people's own posts and comments (not outlets): the stories people gave most attention to, their share of people's posts and the tone of people's reactions.

- **Material.** After every update the feeds listed under `experts: sources:` in `config.yaml` are read; Claude files each new item under security, economy or governance (or sets it aside) and writes one line on it. Items are kept for 180 days in `data/experts/library.json`, with the status of every source.
- **Daily brief.** Each morning by 6:00 Damascus time (3:00 UTC), one page on the day before (a UTC day), written by `.github/workflows/experts-daily.yml` after it reads the newest reports. GitHub often starts night-time schedules hours late, so that job is started at 2:40 UTC by `brief-timer.yml`, which, like the update keeper, is set whenever an update finishes and waits inside a running job; the 2:30 UTC schedule and the first update after 3:00 UTC are second and third chances. Its content: what the reports said in each area, in a few sentences, and how it compared with what Syrians discussed that day. Files: `data/experts/analyses/<date>.json`, page `experts/<lang>/<date>.html`.
- **Analyses.** Every week (after the weekly digest) and every month (from the 2nd), one page per area with enough items and an overall page: findings, where sources agree and differ, their recommendations, how it compares with what Syrians discussed in that area on the tracker, and what to watch. The reports drawn on are linked at the bottom of each page. Files: `data/experts/analyses/<period>.json`, pages `experts/<lang>/<period>.html` (overall) and `<period>-<area>.html`.
- **Sources.** Every source the site uses, for the tracker and the Media and experts, is listed on the Sources page (`sources/en.html`), built from `config.yaml`. To add an Media and experts source, add a line with its name, kind (`intl`, `thinktank` or `media`) and feed URL; publishers that block automated readers can be read through a Google News search limited to their site. `exclude_orgs` leaves out Syrian outlets the tracker already reads; `max` caps a source per update.
- **Language check.** After each analysis is written, any English field containing Arabic (or an Arabic name inside an English sentence) and any Arabic field that is mostly not Arabic is rewritten in the right language by one short call, keeping the links. The maintenance task `experts-fix-languages` runs the same check on every analysis already published.
- **Links to the articles.** In the analyses and daily briefs, the name of the organisation behind a point links to the article it comes from (the model writes `[Crisis Group](item id)`; the page turns it into a link, and a name with an unknown id stays plain text). Feeds, page descriptions and the listings show the plain name. Every linked article also appears in the list of sources at the bottom of the page.
- **Known organisations only, from broad searches.** The three broad Google News searches (`known_only: true`) let in any outlet Google News indexes, so they keep only items from the organisations listed under `known_orgs` in `config.yaml`, each filed under the kind given there (international organisation, think tank or research centre, media) rather than the search's own. Add an organisation to the list once it is known to be established; the list is shown on the Sources page. Sources read from their own feed or a search limited to their site are not affected.
- **Leanings.** When the analyses cite an outlet or think tank whose political orientation, ownership or state funding is widely documented, they say so briefly (for example "the pro-Israel Middle East Forum"), so a broad range of sources can be kept with readers able to weigh each one.
- **Cost.** A cent or two a day for the one-line summaries, about 5 cents a day for the daily brief, about 35 cents a week and 70 cents a month for the analyses.
- **By hand.** Maintenance tasks `experts-collect`, `experts-daily`, `experts-weekly`, `experts-monthly` and `experts-probe` (checks every feed; results in `data/experts/probe.json`).
- **Languages.** Sources in Arabic, English, French, German, Turkish, Hebrew, Russian, Persian, Chinese, Spanish and Italian. Set `lang` on a source (a language code such as `fr`) so its titles are marked correctly and its language appears on the Sources page; the one-line summaries are always in English and Arabic.
- **Limits.** Mostly based outside Syria, and no paywalled outlets; the pages say so.

### Arabic quality

Every prompt that writes Arabic carries the same style rules (`scripts/arabic.py`): write as a Syrian newsroom editor would rather than translate, verb-first sentences where natural, correct agreement, a neutral register, Syrian month names, «» quotation marks, no transliterated English jargon. It also carries the glossary `arabic_terms` in `config.yaml`, the Arabic to use for terms that keep coming back. After each update the Arabic texts are tidied automatically, at no cost: straight and curly quotes become «», Gregorian month names next to a date become Syrian ones (أكتوبر → تشرين الأول), digits become Arabic-Indic like the rest of the site, and any whole word or phrase listed under `avoid` in the glossary is replaced. When you see a term translated badly, add a line to `arabic_terms` (with the bad form under `avoid` if it should be replaced automatically); the weekly quality review also lists doubtful Arabic phrases for you to approve as glossary lines. Names of people and places are fixed the same way in `names`.

### Reports: people and the media in one report

Each weekly and monthly report is one page and one PDF covering both halves of the site, ordered from the quickest read to the most detailed, with a contents list at the top:

1. **At a glance:** 3 to 5 key points (the monthly report adds the month in numbers and charts), one of them comparing people and the media.
2. **What people said:** the tracker's analysis, the stories that mattered, themes and tone (the monthly report adds the weeks, and stories with coordination signals).
3. **People and the media:** the five stories ordinary people talked about most (average share of people's posts, outlets not counted) next to what the media and experts focused on, how the two compare, and what people raised that the media and experts barely covered.
4. **What the media and experts said:** the period's Media and experts analysis in full: the overall picture, then security, economy and governance, each with findings, where sources agree and differ, and recommendations. In the PDF it starts on a new page.
5. **What to watch:** from what people say, and from the media and experts' view.
6. **Sources and method:** every report and article drawn on, linked, and how the report is made.

The period's Media and experts analysis is written first, as soon as the period has ended, and the report's own text compares with it; the weekly report waits for it until 20:00 UTC on the Monday (the monthly until the 2nd). If it comes later, the report and its PDF are redrawn. Periods from before Media and experts existed have no comparison. To rewrite one week or month, run `backfill-weekly` or `backfill-monthly` with `period`.

### Story order on the home page

Stories open ordered by how much ordinary people talk about them (**Most discussed by people**): the percentage beside each story is its share of what people posted, outlets not counted, and "Everything else" shows the rest of people's posts. The other orders are a click away: **Most discussed overall** (people's and outlets' posts together, the share used in the trends, reports and data files), **Most negative** and **Biggest gap**. Outlet posts still count in the analysis as context, since most comments react to them.

### Weekly site check: health, SEO and security

`scripts/site_check.py` checks the built site in the repository, with no network and no extra packages, and prints a report. A weekly scheduled task runs it, fixes the small safe issues and reports the rest. You can also run it any time with the maintenance task `site-check`.
- **Health:** broken internal links and files, raw link markup, data and feeds that don't parse, an update older than 8 hours, report PDFs not remade after their page changed, very large pages, "undefined" or "NaN" in page text.
- **SEO:** titles and descriptions (present, unique, short enough for search results), canonical and English/Arabic hreflang links (present and pointing at each other), one heading per page, social image, page language, structured data, the sitemap (complete, no hidden pages), robots.txt, image alt text, the IndexNow key.
- **Security:** a Content-Security-Policy on every page, scripts only from the site itself, no inline scripts on static pages, new-tab links with `rel="noopener"`, no `http://` resources, forms over https, no secrets or personal email addresses in the repository, workflows with pinned actions and declared permissions, pinned Python packages, the private validation folder untracked.

`scripts/browser_check.py` opens the main pages and every tab of the app in a real browser, in English and Arabic, at desktop and phone width. It looks for script errors, failed requests, sideways scrolling on phones and "undefined" or "NaN" on screen; the weekly task runs it too.

Report PDFs are remade when the report on their page has changed since the PDF was made, ignoring the menu and footer around it. Daily briefs are one page and one PDF too: the day at a glance, what people said, what the media and experts said, and sources and method. Each gets its PDF once the day is over. Briefs from the last 30 days are remade when they change; older ones are made only if missing, so the repository doesn't fill up with PDFs. A fingerprint of each page is kept in `data/pdf_state.json`, because file times on GitHub's runners are all the same after a fresh checkout. Long page titles drop the site's name, and descriptions are cut at about 160 characters at a word boundary, so search results show them whole. The Support page stays out of search engines until donations are switched on.

### What to watch

Above the stories, the home page lists up to five things worth keeping an eye on, worked out by `scripts/watch.py` from the numbers of the last updates, with no extra Claude call:
- a story whose share grew in at least two updates in a row;
- a new story already at 10% or more of the discussion;
- people's tone at least half the scale away from the outlets' tone;
- people's tone down by more than a third of the scale within 36 hours;
- coordination signs at a moderate or strong level two updates running.

They are observations about the recent past, not forecasts, and the page says so. Every list is saved in latest.json and in the archive (`watch`), so after a few months it can be checked how often "gaining" stories went on gaining before anything more forecast-like is considered. The thresholds are at the top of `scripts/watch.py`.

### Coordination signals

Every story carries measurable signs that its public reaction may be organised rather than spontaneous, computed by `scripts/signals.py` from the posts assigned to the story in that update: copy-paste posting, near-identical posts, a sudden burst, a burst with no outlet coverage in that hour, the same text on several platforms within an hour, a few commenters writing most comments, and regular timing. Each triggered signal is shown under the story with its value, a level (weak, moderate, strong) and its innocent explanation, and the values are in the `stories.csv` downloads (`signal_level`, `signal_count`, `signals`). The About page's "Coordination signals" section documents each one.

Two rules of reading them: they are signals, not proof, since real breaking news, popular slogans and a few devoted commenters produce them too; and they never say who is behind anything. Nobody is identified: commenter concentration is counted from one-way hashes that exist only in memory during the update. The signals get far more informative once Telegram comments are connected (extra A2), which is where most organised activity in the Syrian space happens.

### Audience snapshot: indicators for audience research

`scripts/audience.py` reads the whole archive and draws audience indicators from it: how close each type of outlet
(state, independent and private Syrian, Arab and regional, Kurdish, international) is to the public mood on the stories
it covered, how much of people's attention carries doubt about official accounts or media reports, which topics people
talk about more or less than outlets cover them, signs of fatigue (topics losing people's attention while outlets keep
covering them, and the weekly share of tired or resigned reactions), platforms and engagement by topic, languages and
emotions. Each story counts once a day. It writes `data/audience.json` and, with `--report`, a report page at
`audience/en.html` with an A4 PDF beside it (`audience/en.pdf`), kept out of search engines and not linked from the menu,
meant to be sent to partners and funders. Rebuild it at any time with the **audience-snapshot** maintenance job (free).

The indicators describe what people say in public online; they are not a sample of Syrians and say nothing about age,
gender, education, income, people offline, private messaging or Facebook. Closeness to an outlet type's tone is a proxy,
not a measure of trust. They are meant to sit beside a representative survey and interviews.

### Validation study: how accurate are the labels?

Researchers will ask how well the generated themes and tones match human judgement. The tools for a validation study are built in; the human part takes two Arabic (and ideally Kurdish) readers a few days.

1. **Draw the sample.** Open **Actions → Maintenance → Run workflow**, pick **validation-sample** and enter the sample size (300 is enough for a first study). The job runs a normal update and additionally builds a private file with a sample of the posts it analysed, each with the tracker's story-level theme and tone, and empty columns for two coders. It is uploaded as a workflow artifact (open the finished run and download `validation-sample`), never committed to the repository, and it is deleted from GitHub after 30 days. The sample contains post texts, so keep it private and delete it after the study.
2. **Code it.** Each coder fills in `coder1_theme` / `coder1_tone` (or `coder2_…`) for every row without seeing the tracker's columns (hide them in the spreadsheet). Themes are the ids from the `codebook.csv` in the same download; tones run from −1 to +1 (−1, −0.5, 0, 0.5 or 1 is fine).
3. **Compare.** On a computer with Python installed, run `python scripts/validation_compare.py coded-sample.csv --note "Coded by two Syrian researchers in October 2026."` It prints the agreement (share of matching themes and Cohen's κ; tone correlation, mean error and agreement on direction, per coder and between the coders) and writes `data/validation.json`. Commit that file; the numbers appear in the Accuracy section of the About page.

Repeat the study after any major change to the model or the instructions, so the published accuracy matches what is running.

### Search engines

The site has a sitemap, link previews and a crawlable copy of the current analysis. Every story, brief, digest and report also carries structured data (schema.org Article or Report), and the home page describes the site and the dataset (WebSite, Organization, Dataset), which is how the tracker can appear in Google Dataset Search. The Arabic home has its own address, `/ar/`. Stories seen in only one update stay on the site but are kept out of search results and the sitemap (`seo: index_min_runs` in `config.yaml`); each story page links to related stories of the same theme. To be found sooner, register it with **Google Search Console** (https://search.google.com/search-console) and **Bing Webmaster Tools**, verify by adding the DNS record they show, and submit `https://www.syrianpulse.org/sitemap.xml`. Both also show which searches bring readers.

- **Breadcrumbs.** Story, brief, digest, report, Media and experts and Sources pages carry a breadcrumb trail (schema.org BreadcrumbList), which search engines often show instead of the bare address. Media and experts pages also list the reports they cite (`citation`) and what they are about.
- **Links between sections.** The tracker's daily brief links to the Media and experts brief of the same day and back; the weekly digest to the week's analyses and back; a story page to the Media and experts analysis of its area for that week. The crawlable block on the home pages links to the Media and experts and the Sources page.
- **Feeds.** `feed.xml` (weekly digests), `feed-monthly.xml` (monthly reports) and `feed-experts.xml` (Media and experts briefs and analyses), each with an Arabic version (`-ar`).
- **IndexNow.** After every update and maintenance run, `scripts/indexnow.py` announces the pages that changed to Bing, Yandex and the other search engines that take part, so new pages are crawled within hours. The key (`indexnow_key` in `config.yaml`) is public by design and matches the file `<key>.txt` at the site's root.

---

## Troubleshooting

| What you see | What to do |
|---|---|
| Run fails with `authentication_error` or `invalid x-api-key` | The secret is missing or wrong. Redo step 5; the name must be exactly `ANTHROPIC_API_KEY`. |
| Run fails with `credit balance is too low` | Add credit at platform.claude.com. |
| Run fails with `not_found_error` mentioning a model | The `model` line in `config.yaml` has a typo. |
| Run fails at "Save results" with `Permission denied` | Settings → Actions → General → Workflow permissions → choose **Read and write permissions** → Save. Run again. |
| Run fails with a `yaml` error | `config.yaml` has a spacing mistake. Compare your edit with the entries around it. |
| A source's line in the run log says "no public preview" | The channel name is wrong, or the channel is private or has web preview turned off. |
| Website shows "404" | Wait a few minutes after step 7, and check the repository is Public. |
| Website shows "No results yet" | Run the workflow (step 6) and check it finished with a green check. |
| Website says updates may have stopped | This appears when the last update is more than 8 hours old. Open the Actions tab and look at the latest runs. GitHub can pause hourly schedules; if it emailed you that the workflow was disabled, re-enable it on the Actions tab. |

Hourly runs can start a few minutes late when GitHub is busy. That's normal.

## Using it responsibly

The website is built to show patterns, not people: it never names private users, doesn't link to individual users' posts, and replaces @handles before anything is sent for analysis. Keep it that way if you customize it, since people discussing Syrian politics online can face real risks. Remember too that the narratives shown are what people are saying, not verified facts, and that online discussion over-represents some groups. The "How this works" section on the website says this to visitors as well.
