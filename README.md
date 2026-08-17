# AI Operating System (AI OS) - Mining & Finance Orchestrator

An agentic AI Operating System framework designed for high-performance mining data extraction, financial analysis, document synthesis (PDF, DOCX, XLSX generation), and semantic long-term memory retrieval.

The system runs entirely on your local server with a web-based frontend deployed on Vercel.

---

## Architecture Flow

```
                     Vercel (Frontend)
                    React Chat Interface
                           │
                           ▼ (HTTPS / SSE)
                 Your Local Server (Backend)
                      FastAPI Backend
                           │
                           ▼
                     AI Orchestrator
                           │
           ┌───────────────┼────────────────┐
           │               │                │
           ▼               ▼                ▼
     SQLite (Local)   Local Files     Local LLM
     Conversations    Documents       (Ollama)
     Tasks / Memory   Reports
```

---

## 🛠️ Setup

### 1. Prerequisites
- **Python 3.13** (or 3.11+)
- **Ollama** (for local LLM inference): https://ollama.ai
- **Node.js 18+** (for the frontend)

### 2. Backend Setup
```bash
# Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Configure Environment
Copy and edit the `.env` file:
```bash
cp .env.example .env
```
Key settings:
- `LOCAL_LLM_URL` — your Ollama endpoint (default: `http://localhost:11434/v1`)
- `LOCAL_LLM_MODEL` — the model to use (default: `llama3.1:8b`)
- `CORS_ORIGINS` — your Vercel frontend URL (e.g. `https://your-app.vercel.app`)
- `MOCK_LLM=true` — set to `true` if you want to test without running Ollama

### 4. Run the Backend
```bash
.venv/bin/uvicorn backend.main:app --reload --port 8000
```
- Swagger docs: `http://localhost:8000/docs`
- Health check: `http://localhost:8000/health`

### 5. Frontend Setup
```bash
cd frontend
npm install
npm run dev
```
The frontend will connect to `http://localhost:8000` by default.

### 6. Deploy Frontend to Vercel
1. Push the `frontend/` directory to GitHub
2. Import into Vercel
3. Add environment variable: `VITE_API_URL=http://YOUR_SERVER_IP:8000`
4. Update backend `.env`: `CORS_ORIGINS=https://your-app.vercel.app`

---

## 📦 Storage

Everything is stored locally on your server:
- **Database**: SQLite (automatic fallback, no PostgreSQL needed)
- **Files**: Local filesystem under `storage/local_data/`
- **Vector Embeddings**: Local Qdrant instance (or in-memory fallback)
- **LLM**: Ollama running locally

No external cloud services required.
