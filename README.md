# Telegram Welcome Bot

Standalone Telegram Welcome Bot for a Telegram group with join requests enabled. It sends the required Spanish welcome DM, optionally approves the join request, records private referral replies, and provides a simple password-protected admin dashboard for manual review and CSV export.

This project now supports two Telegram intake modes:

- `polling` (default, recommended for your current company server)
- `webhook` (optional, only when you have a public HTTPS endpoint)

For your current environment, use `polling`.

## Features

- FastAPI admin dashboard
- Telegram join request handling
- Private DM intake and parsing
- Manual moderation workflow
- SQLite persistence by default
- CSV export
- Dockerfile included
- Parser tests included

## Project Structure

```text
app/
  config.py
  db.py
  main.py
  models.py
  polling_worker.py
  routes/
    admin.py
    webhook.py
  services/
    join_request_service.py
    parser.py
    submission_service.py
    telegram_client.py
    update_processor.py
  static/
  templates/
tests/
requirements.txt
Dockerfile
README.md
```

## Requirements

- Python 3.11 preferred
- A Telegram bot token from BotFather
- A Telegram group where the bot is admin and can approve join requests

## Environment Variables

Copy `.env.example` to `.env`:

```bash
cp .env.example .env
```

Important values:

- `BOT_TOKEN`
- `TELEGRAM_GROUP_ID`
- `ADMIN_PASSWORD`
- `TELEGRAM_MODE=polling`
- `DATABASE_URL=sqlite:///./telegram_welcome_bot.db`

Optional values:

- `BASE_URL` only needed for webhook mode
- `WEBHOOK_SECRET` only needed for webhook mode
- `POLLING_TIMEOUT_SECONDS` default `30`
- `POLLING_RETRY_SECONDS` default `3`

## BotFather Setup

1. Open Telegram and talk to [@BotFather](https://t.me/BotFather).
2. Create a new bot with `/newbot`.
3. Save the token into `BOT_TOKEN`.
4. If this token was ever pasted into chat or shared, rotate it before production.

## Telegram Group Setup

1. Add the new bot to your target group.
2. Enable **Approve New Members**.
3. Promote the bot to admin.
4. Grant permission to approve join requests.
5. Put the numeric group ID into `TELEGRAM_GROUP_ID`.

## Local Development

Install dependencies:

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Run the admin app:

```bash
uvicorn app.main:app --reload --host 127.0.0.1 --port 8010
```

Run the Telegram polling worker:

```bash
python -m app.polling_worker
```

Open the admin dashboard:

- `http://127.0.0.1:8010/admin`

## Recommended Deployment For Your Company Server

This section assumes:

- you do **not** have `sudo`
- you do **not** want to contact ops
- the server can access the internet outbound
- you are okay with Telegram intake via `polling`

### Step 1. Upload the project

Put the project in your home directory, for example:

```bash
mkdir -p /home/insta_admin/telegram-welcome-bot
cd /home/insta_admin/telegram-welcome-bot
```

Upload all files there.

### Step 2. Create the virtualenv

```bash
cd /home/insta_admin/telegram-welcome-bot
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

### Step 3. Create `.env`

Example:

```env
BOT_TOKEN=replace-with-your-new-token
TELEGRAM_GROUP_ID=-1001234567890
ADMIN_PASSWORD=your-admin-password
TELEGRAM_MODE=polling
BASE_URL=
WEBHOOK_SECRET=
APP_ENV=production
DATABASE_URL=sqlite:////home/insta_admin/telegram-welcome-bot/data/telegram_welcome_bot.db
REQUEST_TIMEOUT_SECONDS=15
AUTO_SET_WEBHOOK_ON_STARTUP=false
POLLING_TIMEOUT_SECONDS=30
POLLING_RETRY_SECONDS=3
```

Create the DB directory:

```bash
mkdir -p /home/insta_admin/telegram-welcome-bot/data
```

### Step 4. Start the admin app

```bash
cd /home/insta_admin/telegram-welcome-bot
source .venv/bin/activate
nohup uvicorn app.main:app --host 127.0.0.1 --port 8010 > logs-admin.out 2>&1 &
```

### Step 5. Start the polling worker

```bash
cd /home/insta_admin/telegram-welcome-bot
source .venv/bin/activate
nohup python -m app.polling_worker > logs-worker.out 2>&1 &
```

### Step 6. Check both processes

```bash
ps -ef | grep -E 'uvicorn|polling_worker' | grep -v grep
```

### Step 7. Open the admin dashboard from your own laptop

Because the FastAPI admin app is only bound to `127.0.0.1`, use SSH tunnel from your local machine:

```bash
ssh -L 8010:127.0.0.1:8010 insta_admin@10.133.2.153
```

Then in your browser open:

- `http://127.0.0.1:8010/admin`

This is usually the cleanest no-ops approach.

## Updating the App Later

When you upload a new version:

1. Kill the old processes.
2. Replace the code.
3. Activate `.venv`.
4. Run `pip install -r requirements.txt` again.
5. Start both processes again with the `nohup` commands above.

Example:

```bash
pkill -f "uvicorn app.main:app"
pkill -f "python -m app.polling_worker"
```

Then restart both commands.

## If You Prefer `tmux` Instead Of `nohup`

Start one session for FastAPI:

```bash
tmux new -s welcome-admin
source .venv/bin/activate
uvicorn app.main:app --host 127.0.0.1 --port 8010
```

Detach with:

```bash
Ctrl+B then D
```

Start another session for polling:

```bash
tmux new -s welcome-worker
source .venv/bin/activate
python -m app.polling_worker
```

Reattach later:

```bash
tmux attach -t welcome-admin
tmux attach -t welcome-worker
```

## How Polling Works

The worker calls Telegram `getUpdates` continuously and processes:

- `chat_join_request`
- private `message`

At startup it also calls `deleteWebhook()` so Telegram will stop trying webhook delivery and will allow polling to work.

The worker stores the polling offset in the `bot_state` table so restarts do not replay everything from the beginning.

## Testing Join Requests

1. Make sure the bot is admin in the target group.
2. Make sure **Approve New Members** is enabled.
3. Open the group invite link from another Telegram account.
4. Request to join.
5. The worker should:
   - receive `chat_join_request`
   - save the join request
   - DM the applicant via `user_chat_id`
   - approve after DM success when `AUTO_APPROVE_AFTER_DM=True`

## Testing Private Message Submissions

Valid examples:

```text
@carlos #insta360recomendado
Me invitó @carlos #insta360recomendado
@Carlos #Insta360Recomendado
```

Invalid examples:

```text
#insta360recomendado
@carlos
hola
```

Expected behavior:

- valid message: bot confirms receipt and stores it as pending review
- invalid message: bot sends a Spanish format reminder
- later valid messages from the same sender are marked `duplicate_candidate=true`

## Admin Dashboard

### `/admin`

- total join requests
- DMs sent
- approvals
- total submissions
- pending submissions
- approved submissions
- rejected submissions

### `/admin/submissions`

- filters by status
- valid-only filter
- duplicates-only filter
- approve / reject / mark pending
- note field

### `/admin/stats`

Leaderboard by `inviter_username`:

- total submissions
- approved submissions
- unique senders

### `/admin/export.csv`

Exports all submissions as CSV.

## Webhook Mode Still Exists

If you later get a public HTTPS domain, you can switch to:

```env
TELEGRAM_MODE=webhook
BASE_URL=https://your-domain.example.com
WEBHOOK_SECRET=replace-me
AUTO_SET_WEBHOOK_ON_STARTUP=true
```

Then run only the FastAPI app and set the Telegram webhook to:

```text
https://your-domain.example.com/telegram/webhook
```

## Docker

Docker is still included, but for your current no-sudo company-server setup, polling + user-space Python is the recommended path.

Build:

```bash
docker build -t telegram-welcome-bot .
```

Run:

```bash
docker run --rm -p 8000:8000 --env-file .env telegram-welcome-bot
```

## Running Tests

```bash
pytest
```
