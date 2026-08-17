# AI OS Intelligence Core — Frontend

Premium iOS-style glassmorphic web interface for the AI Mining OS Intelligence
Core. React + Vite + Tailwind CSS v4. Fully self-contained — deploy it anywhere
(Vercel, Cloudflare Pages, Netlify) and point it at your backend with one
environment variable.

## Architecture

```
Backend (your Mac / server)          Frontend (Vercel)
FastAPI :8000  <———— HTTPS ————>  this folder (static SPA)
Ollama/SQLite/RAG                    VITE_API_URL = https://aios-api.your-domain
```

The frontend is a static single-page app. **All data and AI processing stay on
your backend.** The frontend only renders it over the API link.

## Run locally

```bash
cd frontend
npm install
npm run dev          # http://localhost:5173
```

Local dev uses `http://localhost:8000` by default — no config needed if the
backend runs on the same machine.

## Deploy to Vercel

1. Create a new GitHub repo and copy **only this `frontend/` folder** into it.
2. Log in to Vercel → **Add New Project** → import that repo.
3. Keep the defaults (Vite is auto-detected via `vercel.json`).
4. Add the environment variable below (Settings → Environment Variables):

   | Name | Value |
   |---|---|
   | `VITE_API_URL` | `https://aios-api.<your-domain>` (your Cloudflare tunnel URL) or `http://<server-ip>:8000` |
   | `VITE_API_KEY` | *(optional)* the same `API_KEY` set in your backend `.env` |

5. **Deploy.** Done — the UI is live and talking to your backend over the API link.

> The `VITE_` prefix is required — Vite only exposes variables prefixed with
> `VITE_` to the browser bundle.

## API link

The single point of connection is `VITE_API_URL` in `src/services/api.ts`.
Leave the source untouched; just set the env var for each environment:

```env
VITE_API_URL=https://aios-api.your-domain.com
```

If you use a Cloudflare tunnel, run `deployment/cloudflared_setup.sh` on the
server — it auto-writes this value for you.

## Verify

```bash
npm run build   # tsc + vite — must pass with zero errors
npm run lint    # oxlint — zero warnings
```
