# 🚀 AI OS Intelligence Core - Deployment & Run Guide

This guide outlines exactly how to spin up your Intelligence Core. 

**Architecture Summary:**
- **Backend & AI Engine:** Runs locally on your dedicated server (FastAPI, SQLite, Ollama, Local Storage).
- **Frontend:** Hosted globally on Vercel (React + Vite) or run locally on your machine for testing, styled with an ultra-premium Apple iOS 26/27 glassmorphic design.

---

## 1. Running the Backend (On your Local Server)

Your server acts as the absolute source of truth. All data, documents, and chat histories are stored securely on the machine itself.

### Prerequisites (Server)
* **Python 3.13** (Python 3.14 is NOT supported — `psycopg2-binary`/`pillow` have no wheels and fail to compile). Install via Homebrew: `brew install python@3.13`
* **Ollama** (for local AI inference): [Install Ollama](https://ollama.com/)

### Steps
1. **Clone/Copy the project** to your server.
2. **Setup the Virtual Environment (use 3.13):**
   ```bash
   cd "mine ai"
   /opt/homebrew/bin/python3.13 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```
3. **Configure Environment:**
   ```bash
   cp .env.example .env
   ```
   *Edit `.env` and ensure `LOCAL_LLM_URL` points to your Ollama instance (usually `http://localhost:11434/v1`). Set `MOCK_LLM=false` if you want real AI processing. If Ollama is off, the assistant automatically falls back to a fast built-in conversational engine.*
4. **Start the API Gateway:**
   ```bash
   # Run the server on port 8000, accessible to the network
   uvicorn backend.main:app --host 0.0.0.0 --port 8000
   ```

*The backend is now running locally. SQLite data is saved persistently to `storage/local_data/ai_os.db`.*

### Fast & Always-Saved Chat (guarantees)

- **Token streaming:** `/api/chat/stream` streams the reply token-by-token (first token in <0.5s locally) — no more long "processing" waits. Casual messages (greetings, small talk) skip heavy embedding/vector search and answer instantly.
- **Always saved:** the user message is persisted the moment it's sent; the assistant reply is appended on completion. Every session resumes with full history via `/api/chat/history/{id}` and appears in the sidebar's memory list via `/api/chat/sessions`.
- **General conversation:** the assistant is a general-purpose conversational AI (ChatGPT/Gemini-style) that talks naturally about anything — it only routes to mining/finance/reporting tools when the question actually needs them. No assumptions: it asks for clarification rather than guessing.
- **Never stuck:** if a stream errors or drops, the frontend always releases the composer and refreshes the session list (no frozen "processing" state).

---

### 2. Frontend Configuration

To connect the frontend to the deployed backend server:

1. Open `/frontend/.env`
2. Change the `VITE_API_URL` to point to the server's IP address:
```env
VITE_API_URL=http://192.168.100.25:8000
```
3. Deploy the frontend to Vercel (or any other hosting provider). Ensure you set the `VITE_API_URL` environment variable in the Vercel dashboard to `http://192.168.100.25:8000` so the production build knows where the backend is hosted.

**Note on Security**: Make sure port `8000` is open on your server firewall (`sudo ufw allow 8000`) and the frontend's HTTPS domain is allowed by the backend's CORS policy.

---

### 2.5 Exposing the Backend with Cloudflare Tunnel (replaces ngrok)

No more random ngrok URLs. Cloudflare Tunnel gives a **stable HTTPS URL** (e.g. `https://aios-api.your-domain.com`) straight to the local backend on port 8000 — no port forwarding, no dynamic IP problems.

**Requirement:** a domain you own, added to your Cloudflare account as a zone (free — dash.cloudflare.com → Add Site).

```bash
cd "mine ai"
bash deployment/cloudflared_setup.sh --domain your-domain.com --subdomain aios-api
```

What the script does:
1. Installs `cloudflared`.
2. Logs you into Cloudflare (opens a browser).
3. Creates a named tunnel `aios-api` and routes `aios-api.your-domain.com` to it.
4. Installs the tunnel as a background service.
5. **Auto-updates** `backend/.env` (`BASE_URL`, `CORS_ORIGINS`) and `frontend/.env` (`VITE_API_URL`) to the Cloudflare URL.

Then:
- Restart the backend so `BASE_URL`/CORS take effect.
- Set `VITE_API_URL=https://aios-api.your-domain.com` in the **Vercel dashboard** and redeploy.
- Verify: `curl https://aios-api.your-domain.com/health`

**No domain yet?** Use `--quick` for a temporary `*.trycloudflare.com` URL (random on each restart — not for production).

## 3. Previewing the Frontend Locally (Testing the iOS Design)

If you just want to see the brand new Apple-inspired UI on your machine before pushing to Vercel:

### Steps
1. **Open a new terminal window** and navigate to the frontend:
   ```bash
   cd "mine ai/frontend"
   ```
2. **Install Dependencies:**
   ```bash
   npm install
   ```
3. **Run the Development Server:**
   ```bash
   npm run dev
   ```
4. **Open in Browser:**
   Go to `http://localhost:5173`. 
   *(Note: The frontend will automatically look for the backend at `http://localhost:8000` by default. If your backend is running on a different machine, you need to create a `.env` file inside the `frontend/` folder with `VITE_API_URL=http://YOUR_SERVER_IP:8000`).*

---

### Frontend Architecture & Design

The interface is a modular React + Vite + Tailwind v4 app with an **iOS 26 Liquid Glass** design system (dark, frosted-glass panels, aurora background, spring-based motion via `framer-motion`).

```
frontend/src/
├── components/
│   ├── ui/        # Reusable primitives: GlassPanel, Button, Badge, Sheet, Sparkline, StatCard, …
│   ├── layout/    # AppShell, Sidebar, TopBar, RightPanel, MobileTabBar
│   ├── chat/      # ChatView (SSE streaming), MessageBubble, Composer
│   ├── modules/   # MiningIntelView, FinanceView, TaskView, KnowledgeView
│   └── settings/  # SettingsSheet (backend health check)
├── hooks/         # usePolling (shared), useTelemetry, useMarketPrices, useTasks, useSessions
├── services/      # api.ts — single client bound to VITE_API_URL
└── types.ts       # Shared domain types
```

- **Responsive:** desktop = 3 columns; tablet = sidebar + content; mobile = bottom tab bar + slide-in sheets (nav left, telemetry right).
- **Data hooks** poll the backend (`/api/system/telemetry` every 10s, `/api/research/market-prices` every 60s, `/tasks` every 10s) and degrade gracefully to "Offline" pills when unreachable.
- **API key:** `/api/chat/stream` needs no key, but sessions/telemetry/tasks/uploads require `Authorization: Bearer`. Set `VITE_API_KEY` in `frontend/.env` and Vercel to match the backend `API_KEY`.

### Build & Verify

```bash
cd "mine ai/frontend"
npm run build   # tsc + vite — must pass with zero errors
npm run lint    # oxlint — zero warnings
```

---

## 3. Deploying the Frontend to Vercel

When you are ready to make the frontend accessible from anywhere in the world, while keeping your data and AI processing securely on your home server:

### Steps
1. **Push your code to GitHub.**
2. **Log into Vercel** and click **"Add New Project"**.
3. Select your GitHub repository.
4. **Configure the Build:**
   - **Framework Preset:** Vite
   - **Root Directory:** `frontend` (Important! Tell Vercel your frontend is in the `frontend` folder).
5. **Set Environment Variables in Vercel:**
   - Name: `VITE_API_URL`
   - Value: `http://<YOUR_SERVER_PUBLIC_IP>:8000` *(You will need to ensure port 8000 is open/forwarded on your server's router so Vercel can talk to it, or put it behind an Nginx reverse proxy with SSL).*
   - Name: `VITE_API_KEY`
   - Value: `<YOUR_BACKEND_API_KEY>` *(This must exactly match the `API_KEY` set in your backend `.env` file for secure authentication).*
6. **Deploy.**

### Final Security Step (CORS)
Once Vercel gives you a URL (e.g., `https://my-ai-os.vercel.app`), go back to your **server's backend `.env` file** and update the CORS setting so it accepts requests from Vercel:

```env
CORS_ORIGINS=https://my-ai-os.vercel.app,http://localhost:5173
```
Restart your backend server.

---

## 🎉 You're Done
You now have a top-tier, ultra-premium web interface hosted globally, powered entirely by your private local intelligence server. All data stays local. All processing stays local.
