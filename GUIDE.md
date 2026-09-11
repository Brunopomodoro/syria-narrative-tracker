# Setup guide: Syria narrative tracker

This guide takes you from nothing to a live website that updates itself every hour. No coding is needed; everything happens in your web browser. Plan on about 45 minutes.

## What you will end up with

A public website at an address like `https://YOUR-NAME.github.io/syria-narrative-tracker/` showing the main narratives in Syrian online discussion over the last 24 hours, the tone around each one, and a 7–14 day "mosaic" of how the mood changed hour by hour.

Behind it, GitHub runs a small program every hour that collects public posts, asks Claude to analyze them, and saves the results. The website reads those results.

## What it costs

| Part | Cost |
|---|---|
| GitHub (runs the hourly job, hosts the website) | Free for public repositories |
| Telegram channels and news RSS feeds | Free |
| Claude API (the analysis) | Pay per use, see below |
| YouTube comments (optional) | Free within Google's daily quota |
| X / Twitter (optional) | About $0.005 per post read (roughly $36/month at default settings) |

Claude cost depends on how many posts you analyze. With the default settings (up to 150 posts per run) and the default model `claude-haiku-4-5-20251001`, a busy hour costs roughly 2 to 5 US cents, which works out to about $20–40 a month if every hour is busy. With only a few sources it will be much less, and runs are skipped (free) when nothing new was posted. If you later want a more nuanced reading of dialect and sarcasm, switch the model to `claude-sonnet-5` in `config.yaml`; it costs about twice as much. Every run prints its exact cost in the log, so you can watch it.

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

The two starter Telegram channels (SANA's English channel and Enab Baladi's English channel) are only there to get you running. The tracker's value depends almost entirely on which sources you pick, so this is the most important step to spend time on.

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
4. The **Sources in this update** table at the bottom of the website shows which sources work.

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

The default settings use about half of Google's free daily allowance. No billing account is needed.

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

### C. Languages

The website is fully bilingual. Everything is written in both English and Arabic, and visitors switch with the button at the top right; the site remembers their choice. To make the site open in Arabic by default, set `default_language: "ar"` in `config.yaml`. You can also link straight to either version by adding `?lang=ar` or `?lang=en` to your site address.

### D. Update less often to save money

In `.github/workflows/update.yml`, change `"17 * * * *"` to `"17 */2 * * *"` for every 2 hours, or `"17 */3 * * *"` for every 3 hours.

---

## Troubleshooting

| What you see | What to do |
|---|---|
| Run fails with `authentication_error` or `invalid x-api-key` | The secret is missing or wrong. Redo step 5; the name must be exactly `ANTHROPIC_API_KEY`. |
| Run fails with `credit balance is too low` | Add credit at platform.claude.com. |
| Run fails with `not_found_error` mentioning a model | The `model` line in `config.yaml` has a typo. |
| Run fails at "Save results" with `Permission denied` | Settings → Actions → General → Workflow permissions → choose **Read and write permissions** → Save. Run again. |
| Run fails with a `yaml` error | `config.yaml` has a spacing mistake. Compare your edit with the entries around it. |
| A source says "no public preview" | The channel name is wrong, or the channel is private or has web preview turned off. |
| Website shows "404" | Wait a few minutes after step 7, and check the repository is Public. |
| Website shows "No results yet" | Run the workflow (step 6) and check it finished with a green check. |
| Website says updates may have stopped | Open the Actions tab and look at the latest runs. GitHub can pause hourly schedules; if it emailed you that the workflow was disabled, re-enable it on the Actions tab. |

Hourly runs can start a few minutes late when GitHub is busy. That's normal.

## Using it responsibly

The website is built to show patterns, not people: it never names private users, doesn't link to individual users' posts, and replaces @handles before anything is sent for analysis. Keep it that way if you customize it, since people discussing Syrian politics online can face real risks. Remember too that the narratives shown are what people are saying, not verified facts, and that online discussion over-represents some groups. The "How this works" section on the website says this to visitors as well.
