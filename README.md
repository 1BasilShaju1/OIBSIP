# Sky — Web Assistant

## Run it locally (Ring 0–3 complete: brain + API + frontend + voice)

```bash
cd backend
pip install -r requirements.txt --break-system-packages   # or use a venv
```

Create `backend/.env`:
```
GROQ_API_KEY=your_real_key
NVIDIA_API_KEY=your_real_key
WEATHER_API_KEY=your_real_key
```

Run:
```bash
cd backend
uvicorn main:app --reload
```

Visit **http://localhost:8000** — that's your whole app, frontend and
backend, served from one URL. Visit **http://localhost:8000/docs** to
see and test the raw API.

Click the mic, talk to it (Chrome/Edge), or just type. Open the same
URL in a different browser/incognito window — notice settings, notes,
and reminders don't bleed between the two "users." That's the
per-user database doing its job.

## Going live on a real URL (Ring 5)

Pick a host that runs Python servers (not static-site hosts like
GitHub Pages — those can't run FastAPI):

- **Railway** or **Render**: connect your GitHub repo, point it at
  `backend/`, set start command `uvicorn main:app --host 0.0.0.0 --port $PORT`,
  add your API keys as environment variables in their dashboard (never
  commit `.env`). They give you a public URL automatically
  (e.g. `sky-production.up.railway.app`).
- **Fly.io**: similar, slightly more config, generous free tier.

Once deployed, anyone clicking that URL gets their own `user_id`
(generated client-side, see `getUserId()` in index.html) and their
own private settings/reminders/notes — this is what "accessible to
anyone via URL" actually requires under the hood.

## What's intentionally NOT ported (and why)

- **Volume/brightness control** — cannot control a stranger's device
  from your server. Would need a from-scratch redesign (e.g. controlling
  audio of media playing *in the browser tab*, not the OS).
- **Opening desktop apps (Notepad, Chrome, Calculator)** — meaningless
  for a remote visitor; "open Chrome" on your server doesn't open
  anything on their screen.
- **Email sending** — logic is portable (see your original
  `send_email()`), but deliberately left out of this pass so a public
  URL can't be used to spam through your Gmail account. Add it back
  behind rate-limiting if you need it.
- **Server-held timers** — moved to the browser (`setTimeout`) instead
  of a server-side thread, so one server doesn't end up holding open
  threads for every visitor's countdown.

## File map

```
backend/
  brain.py       core AI logic (intent detection, calculator, weather, Q&A)
  database.py    per-user settings/reminders/notes (SQLite)
  main.py        FastAPI app — the actual web server
  requirements.txt
frontend/
  index.html     chat UI + Web Speech API (mic in, voice out)
```
