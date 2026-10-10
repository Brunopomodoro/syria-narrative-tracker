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

Claude cost depends on how many posts you analyze and which model reads them. With the default settings (up to 400 posts per run) and the default model `claude-sonnet-5`, a run costs about 20 to 25 US cents. GitHub currently runs the update every 3 to 6 hours, so that is roughly $1.50 a day, about $45 a month; if it ran every hour (extra E below) it would be about $170 a month. Two ways to spend less: switch `model` in `config.yaml` to `claude-haiku-4-5-20251001` (about half the cost, a less careful reading of dialect and sarcasm), or lower `max_posts` (for example to 150). Runs are skipped (free) when nothing new was posted, and every run prints its exact cost in the log. The weekly digest adds one call a week, a few cents.

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

GitHub runs scheduled jobs late or skips them when its servers are busy, which is why the tracker updates every three to six hours rather than every hour. A free external timer fixes that:

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
- After every completed month it writes a **monthly report** (`monthly/en/…`, `monthly/ar/…`), laid out as a one-page briefing for donors, organisations and journalists: key findings, the month in numbers with two charts, the analysis, the stories that mattered, what to watch, the weeks in brief, the stories that carried coordination signals, the theme and tone tables, and an "About this report" block with the method, the sources, the licence and a citation line. Each report has share links (X, Facebook, Telegram, WhatsApp, with hashtags; see below), a print layout, and a **PDF** made by `scripts/report_pdf.py` with the Chrome that GitHub's runners already have. The Reports tab lists the reports, the weekly digests and the daily briefs. A month needs at least 10 days of data. Turn it off with `monthly_review: false`.

### Monthly review and newsletter

The monthly review is written to be sent as a newsletter. Its feeds (`feed-monthly.xml` in English, `feed-monthly-ar.xml` in Arabic) carry the full text of every review, with absolute links, so an RSS-to-email service can send each new review to subscribers without anything else to build. The site itself cannot send email: it is static, has no server, and subscriber addresses must never be put in the repository.

1. Create an account with an RSS-to-email service. **Buttondown** (https://buttondown.com) is free up to 100 subscribers, hosts the sign-up page, the unsubscribe link and the consent record that email law requires, and has an "RSS-to-email" automation; **follow.it** is a simpler free alternative. Some US services refuse accounts from certain countries; if one does, try the other.
2. Point the automation at `https://www.syrianpulse.org/feed-monthly.xml` (or the Arabic feed), set it to send each new item automatically, and send yourself a test.
3. Put the service's sign-up page address in `config.yaml` as `newsletter_url`. The monthly pages and the Trends page then show a "Subscribe by email" link.

If no service will take your account, the fallback is to send the review yourself from the Maintenance workflow through a Gmail app password to addresses kept in a repository secret, with a Google Form for sign-ups; ask for that to be set up if you need it. The first review is written by **Actions → Maintenance → backfill-monthly**; afterwards each new month's review is written automatically on the first update after the month ends.

### Maintenance jobs

Open **Actions → Maintenance → Run workflow** and pick a task:

| Task | What it does | Cost |
|---|---|---|
| rebuild-index-and-exports | Recompute the per-day index, the monthly downloads and the methodology file from the archive. Run after editing themes, events or the changelog. | free |
| rebuild-pages | Rebuild every story page, daily brief, digest and report page, the listings, feeds and the sitemap, then the PDFs. Run after changing how pages look. | free |
| backfill-themes | Give a theme to archived stories that have none. | a few cents |
| backfill-weekly | Write the digest of every completed week that has none. | a few cents per week |
| backfill-monthly | Write the review of every completed month that has none. | about 15 cents per month |
| brand | Remake the logo files: icons, preview cards, wordmarks. Run after changing the site's name or tagline. | free |
| telegram-probe | Check Telegram channels before adding them: active, subscribers, last post, share of posts about Syria. Leave *names* empty for the built-in list, type channel names, or type `--discover` to find candidates from the channels' forwards and Syrian outlets' websites. | free |
| social-check | Check the Facebook and X keys and show the latest daily, weekly and monthly posts for each. Posts nothing. | free |
| backfill-archive | Rebuild the archive from the git history of the results. Only needed if the archive is lost. | free |

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

Once set up, the tracker posts to its X account on the same schedule as Facebook: yesterday's daily brief every morning, each weekly digest and each monthly report once written. Each report is two posts, one in Arabic and one in English, each with the label and date, the headline, as much of the summary as fits, the link and up to four hashtags; every post stays within 280 characters. At most two posts go out per update. The record in `data/social.json` keeps anything from going out twice.

**Cost.** X charges per post from prepaid credits; there has been no free tier for new developers since February 2026. About 35 reports a month means about 70 posts. Reported prices range from about 1 cent a post to 20 cents for a post with a link, so expect roughly $1 to $15 a month; check the price list in the console. Set `languages: [ar]` under `x:` in `config.yaml` to post in Arabic only and halve it.

**1. The account.** Sign up at https://x.com/i/flow/signup with a new email for the tracker. Name `Syria Narrative Tracker`, handle such as `@SyrianPulse`. Profile picture `assets/avatar.png`, header `assets/cover-x.png`. Bio: `ملخص آلي يومي لما يُقال عن سوريا على الإنترنت · Automatic summaries of what is said about Syria online. syrianpulse.org`. Turn on two-factor authentication at https://x.com/settings/account/login_verification.

**2. The automated label.** At https://x.com/settings/account/automation choose your personal X account as the managing account. The tracker's profile then shows "Automated by @you", which X's rules ask of bots.

**3. The developer account.** Logged in as the tracker's account, open https://developer.x.com and sign up. Describe the use honestly: "Posts the daily, weekly and monthly summaries of syrianpulse.org, a public research site, to this account. No reading of other accounts, no replies, no direct messages." Add a payment method, buy the minimum credits, and set a monthly spending limit.

**4. The app.** In the console, create an app (a default one may already exist). Open its **User authentication settings → Set up**: App permissions **Read and write**; Type of app **Web App, Automated App or Bot**; Callback URL `https://www.syrianpulse.org/`; Website `https://www.syrianpulse.org/`. Save.

**5. The keys.** Open the app's **Keys and tokens**:
- **API Key and Secret** (also called consumer keys): generate or regenerate, copy both.
- **Access Token and Secret**: generate, copy both. It must say **Read and Write**. If it says Read only, the token was made before step 4: regenerate it.

**6. The secrets.** At https://github.com/Brunopomodoro/syria-narrative-tracker/settings/secrets/actions/new add four secrets: `X_API_KEY`, `X_API_SECRET`, `X_ACCESS_TOKEN`, `X_ACCESS_TOKEN_SECRET`.

**7. Check.** Run **Actions → Maintenance → social-check** (https://github.com/Brunopomodoro/syria-narrative-tracker/actions/workflows/tools.yml). The log says "Keys work: they can post as @…" and shows the posts. The first posts go out at the next update, or at once with **Actions → Update narratives → Run workflow**.

**If posting stops**, the update log says why: no credits left (add credits), keys rejected (copy them again), or read-only (step 5). To pause, set `enabled: false` under `x:`.

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

### Coordination signals

Every story carries measurable signs that its public reaction may be organised rather than spontaneous, computed by `scripts/signals.py` from the posts assigned to the story in that update: copy-paste posting, near-identical posts, a sudden burst, a burst with no outlet coverage in that hour, the same text on several platforms within an hour, a few commenters writing most comments, and regular timing. Each triggered signal is shown under the story with its value, a level (weak, moderate, strong) and its innocent explanation, and the values are in the `stories.csv` downloads (`signal_level`, `signal_count`, `signals`). The About page's "Coordination signals" section documents each one.

Two rules of reading them: they are signals, not proof, since real breaking news, popular slogans and a few devoted commenters produce them too; and they never say who is behind anything. Nobody is identified: commenter concentration is counted from one-way hashes that exist only in memory during the update. The signals get far more informative once Telegram comments are connected (extra A2), which is where most organised activity in the Syrian space happens.

### Validation study: how accurate are the labels?

Researchers will ask how well the generated themes and tones match human judgement. The tools for a validation study are built in; the human part takes two Arabic (and ideally Kurdish) readers a few days.

1. **Draw the sample.** Open **Actions → Maintenance → Run workflow**, pick **validation-sample** and enter the sample size (300 is enough for a first study). The job runs a normal update and additionally builds a private file with a sample of the posts it analysed, each with the tracker's story-level theme and tone, and empty columns for two coders. It is uploaded as a workflow artifact (open the finished run and download `validation-sample`), never committed to the repository, and it is deleted from GitHub after 30 days. The sample contains post texts, so keep it private and delete it after the study.
2. **Code it.** Each coder fills in `coder1_theme` / `coder1_tone` (or `coder2_…`) for every row without seeing the tracker's columns (hide them in the spreadsheet). Themes are the ids from the `codebook.csv` in the same download; tones run from −1 to +1 (−1, −0.5, 0, 0.5 or 1 is fine).
3. **Compare.** On a computer with Python installed, run `python scripts/validation_compare.py coded-sample.csv --note "Coded by two Syrian researchers in October 2026."` It prints the agreement (share of matching themes and Cohen's κ; tone correlation, mean error and agreement on direction, per coder and between the coders) and writes `data/validation.json`. Commit that file; the numbers appear in the Accuracy section of the About page.

Repeat the study after any major change to the model or the instructions, so the published accuracy matches what is running.

### Search engines

The site has a sitemap, link previews and a crawlable copy of the current analysis. To be found sooner, register it with **Google Search Console** (https://search.google.com/search-console) and **Bing Webmaster Tools**, verify by adding the DNS record they show, and submit `https://www.syrianpulse.org/sitemap.xml`. Both also show which searches bring readers.

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
