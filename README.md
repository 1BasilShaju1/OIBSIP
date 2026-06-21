# Sky — Web Assistant

## What's in this repo (push all of it to GitHub)

```
sky-web/
├── .gitignore
├── render.yaml              <- lets Render deploy with one click
├── README.md
├── backend/
│   ├── brain.py              core AI logic (intent detection, calculator, weather, Q&A)
│   ├── database.py           per-user settings/reminders/notes (SQLite)
│   ├── main.py                FastAPI app - the web server, also serves frontend/
│   └── requirements.txt
└── frontend/
    └── index.html             single-file UI: particle face, waveform, chat, voice
```

Do **not** push: `.env` (your API keys) or `sky.db` (created automatically
at runtime, holds user data). The `.gitignore` already excludes both —
just don't force-add them.

## Run it locally first (always test before deploying)

```bash
cd backend
pip install -r requirements.txt   # or: pip install -r requirements.txt --break-system-packages
```

Create `backend/.env`:
```
GROQ_API_KEY=your_real_key
NVIDIA_API_KEY=your_real_key
WEATHER_API_KEY=your_real_key
```

```bash
uvicorn main:app --reload
```

Visit **http://localhost:8000** — full UI. **http://localhost:8000/docs**
for the raw API. Click the mic (Chrome/Edge), or type. Try two different
browsers/incognito windows side by side and confirm settings/notes don't
leak between them.

## Push to GitHub

```bash
cd sky-web
git init
git add .
git commit -m "Sky web assistant"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/sky-web.git
git push -u origin main
```

## Deploy on Render (free tier)

**Option A — one-click via render.yaml (recommended, this repo has it):**

1. Push the repo to GitHub (above).
2. Go to dashboard.render.com → **New** → **Blueprint**.
3. Connect your GitHub account, pick the `sky-web` repo. Render reads
   `render.yaml` automatically and configures the service for you.
4. It will prompt you to fill in the three env vars marked `sync: false`
   (`GROQ_API_KEY`, `NVIDIA_API_KEY`, `WEATHER_API_KEY`) — paste your real
   keys into the Render dashboard, never into the repo.
5. Click **Apply**. Render builds and deploys. You get a URL like
   `https://sky-assistant.onrender.com` — that's your public link.

**Option B — manual, if you skip render.yaml:**

1. **New** → **Web Service** → connect the repo.
2. **Root Directory**: `backend`
3. **Runtime**: Python 3
4. **Build Command**: `pip install -r requirements.txt`
5. **Start Command**: `uvicorn main:app --host 0.0.0.0 --port $PORT`
6. Under **Environment**, add `GROQ_API_KEY`, `NVIDIA_API_KEY`, `WEATHER_API_KEY`
   with your real values.
7. **Create Web Service**. Wait for the build to finish, then open the
   given URL.

**Free tier note:** Render's free web services spin down after 15 minutes
of no traffic and take ~30-50 seconds to wake up on the next request.
That's fine for a demo/personal project; for an always-on assistant
you'd need a paid instance.

Anyone who opens that URL gets the chat + voice UI, gets a random
`user_id` stored in their own browser's `localStorage`, and their
settings/reminders/notes stay private to them via the per-user database
rows — none of that needs further setup on your end.

## What's intentionally not ported (and why)

- **Volume/brightness control** — cannot control a stranger's device
  from your server.
- **Opening desktop apps (Notepad, Chrome, Calculator)** — meaningless
  for a remote visitor.
- **Email sending** — logic is portable from your original script, but
  left out here so a public URL can't be used to spam through your
  Gmail account. Add it back behind rate-limiting if you need it.
- **Server-held timers** — moved to the browser (`setTimeout`) instead
  of a server-side thread.

## On the new UI

- **Particle face** (canvas) — idles with a slow drift, brightens and
  pulses faster when listening or speaking.
- **Waveform** (canvas) — three modes:
  - idle: a calm resting curve
  - listening: **real** mic amplitude via the Web Audio API `AnalyserNode`
  - speaking: **simulated** bars, because browsers don't expose raw
    audio samples from `speechSynthesis` (TTS) to the Web Audio API —
    this is a platform limitation, not a shortcut taken here.
- Chat thread sits below the hero, same backend contract as before
  (`POST /chat` with `{text, user_id}` → `{reply, intent}`).
