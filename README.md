---
title: AI OS Mining WhatsApp Worker
emoji: ⛏️
colorFrom: amber
colorTo: green
sdk: docker
pinned: false
license: mit
---

# AI Operating System (AI OS) - Mining & Finance Orchestrator

An agentic AI Operating System framework designed for high-performance mining data extraction, financial analysis, document synthesis (PDF, DOCX, XLSX generation), and semantic long-term memory retrieval. 

The system implements a **cost-optimized, on-demand GPU VM architecture**. The lightweight orchestration engine runs on an always-on cheap CPU VM, while the compute-heavy GPU instance only spins up when active LLM inference is requested, automatically shutting down after 5 minutes of inactivity.

---

## Architecture Flow

```
                     Always Running (Cheap CPU VM)
                   WhatsApp Cloud API
                          │
                          ▼
                     FastAPI Backend
                          │
                          ▼
                    AI Orchestrator
                          │
          ┌───────────────┼────────────────┐
          │               │                │
          ▼               ▼                ▼
    PostgreSQL        Qdrant          File Storage
          │
          ▼
    Check if GPU is running?
          │
     ┌────┴─────┐
     │          │
    YES        NO
     │          │
     ▼          ▼
 Send Request   Start GPU VM (Compute Engine API)
     │          │
     │     Wait until healthy (Health check ping)
     │          │
     └──────────┘
          │
          ▼
    Local LLM Server (vLLM / Ollama)
          │
          ▼
     Return Response
          │
          ▼
   Idle Timer (5 min) ➔ No Requests? ➔ Stop GPU Instance
```

---

## 🛠️ Step-by-Step Environment Setup

### 1. Prerequisites
Ensure you have the following installed on your machine:
- **Python 3.13** (Homebrew-installed Python is recommended for macOS)
- **Docker & Docker Compose** (for running local database/vectors/storage engines)

### 2. Set Up the Virtual Environment
Create and activate the virtual environment in the project root:
```bash
# Create the virtual environment using Python 3.13
python3.13 -m venv .venv

# Activate it
source .venv/bin/activate

# Install all Python 3.13 compatible dependencies (wheels preferred)
pip install -r requirements.txt
```

### 3. Configure the Environment Variables
Copy the `.env.example` file to `.env`:
```bash
cp .env.example .env
```
Open `.env` and fill out or modify the config variables.

---

## 💻 Running in MOCK / Offline Mode (Recommended for Development)

In Mock Mode, the system runs completely locally without calling GCP, Meta WhatsApp, or other paid APIs. It simulates the GCE VM provisioning steps and LLM responses locally.

### 1. Start the Local Service Container Stack
Use Docker Compose to launch local instances of PostgreSQL, Qdrant, Redis, and MinIO:
```bash
docker compose up -d
```
*This starts:*
- **PostgreSQL** on port `5432` (analytical/relational database)
- **Qdrant** on port `6333` (vector embedding database)
- **Redis** on port `6379` (telemetry anomaly caching)
- **MinIO** on port `9000` (local S3 object storage simulation)

### 2. Verify Config Settings for Mock Mode
Ensure `.env` contains:
- `MOCK_LLM=true` (forces the adapter to use mock reasoning engine instead of making HTTP queries)
- Keep `# GOOGLE_APPLICATION_CREDENTIALS` commented out (forces `GPUManager` to run in mock mode)

### 3. Run Verification Tests
Verify that the components, services, and the GPU manager lifecycle checks compile and run cleanly:
```bash
python verify.py
```
This runs the full test suite (using PyTest) and should report `13 passed`.

### 4. Run the Backend API Server Locally
Start the FastAPI server:
```bash
.venv/bin/uvicorn backend.main:app --reload --port 8000
```
- Open Swagger documentation at: `http://localhost:8000/docs`
- Send a mock user message payload to `POST /api/v1/whatsapp/webhook` to observe the mock GPU spin-up logs:
  - `GPU Manager: Initiating compute.instances.start()...`
  - `[MOCK GPU] Instance status: PROVISIONING / STAGING`
  - `[MOCK GPU] Instance status: RUNNING`
  - `LLM health check PASSED. Model loaded successfully!`
  - `Scheduled Job: Checking GPU VM idle state... Idle elapsed time: 60s / 300s limit.`
  - After 5 minutes (300 seconds) of no queries, you will see the logs trigger: `GPU Manager: Idle limit reached. Shutting down GPU.`

---

## 🚀 Running in PRODUCTION Mode (With Cloud Integration)

Production mode connects to the live Google Cloud Platform Compute Engine and WhatsApp Cloud API.

### 1. Deploy the GPU VM on Google Cloud (GCP)
1. Provision a GPU VM instance in Google Compute Engine (e.g., equipped with NVIDIA L4, A10G, or T4).
2. Configure it to run an OpenAI-compatible endpoint server:
   - **vLLM** (Recommended for performance): `python -m vllm.entrypoints.openai.api_server --model unsloth-mining-model --port 8000`
   - Or **Ollama**
3. Create a service account in GCP with the role **Compute Instance Admin (v1)** and download the credentials JSON file.

### 2. Configure Production Variables in `.env`
Update the following settings in your `.env` file:
```env
# Enable production LLM routing
MOCK_LLM=false
LOCAL_LLM_URL=http://<YOUR_GPU_VM_IP>:8000/v1
LOCAL_LLM_MODEL=unsloth-mining-model

# GCP GCE VM Manager Config
GOOGLE_APPLICATION_CREDENTIALS=/absolute/path/to/gcp-credentials.json
GCP_PROJECT=your-gcp-project-id
GCP_ZONE=us-central1-a
GCP_INSTANCE_NAME=your-gpu-instance-name
GPU_IDLE_TIMEOUT_MINUTES=5

# WhatsApp Cloud API credentials
WHATSAPP_TOKEN=your_permanent_system_user_whatsapp_token
WHATSAPP_VERIFY_TOKEN=your_secure_verify_webhook_token
WHATSAPP_PHONE_NUMBER_ID=your_whatsapp_phone_number_id

# External Search Service (for Research agent fallback)
SERPER_API_KEY=your_serper_api_key_here
```

### 3. WhatsApp Cloud API Webhook Verification
1. Expose your local server to the internet (e.g., using `ngrok` or deploying to a cloud VM):
   ```bash
   ngrok http 8000
   ```
2. In the Meta Developer Console (WhatsApp Webhook Configuration):
   - Set **Callback URL** to: `https://<YOUR_FORWARDING_DOMAIN>/api/v1/whatsapp/webhook`
   - Set **Verify Token** to the exact value of `WHATSAPP_VERIFY_TOKEN` in `.env`.
   - Subscribe to the `messages` event.

### 4. Running the Production Server
Start the server in production mode:
```bash
.venv/bin/uvicorn backend.main:app --host 0.0.0.0 --port 8000
```
- **Lifecycle Integration**: The backend automatically tracks incoming WhatsApp webhook payloads. It starts the GPU VM instantly when a query arrives, loops a health ping against the model port, handles the prompt orchestration, and issues `compute.instances.stop()` 5 minutes after the last user request.
