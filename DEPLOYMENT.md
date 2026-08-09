# AI OS — Full Online Deployment Guide

Deploy the WhatsApp gold-mining AI as a **100% cloud system** — no laptop, no
Colab, no local process required. Every component below runs on free/low-cost
tiers and stays online 24/7.

```
WhatsApp user
   │
   ▼
[1] Cloudflare Worker  (always-on webhook, free tier)
   │   - validates Meta signature
   │   - answers instant /grade + /help math directly (~100ms)
   │   - sends "*Got it*" receipt
   │   - writes message to Supabase queue (wa_inbox)
   ▼
[2] Supabase Postgres  (managed database, free tier)
   │   - wa_inbox queue, conversations, memories, tasks
   ▼
[3] Hugging Face Space  (Docker, "CPU Upgrade" ~$0.03/hr, always-on)
   │   - polls wa_inbox every few seconds
   │   - runs the AI OS orchestrator + retrieval over Qdrant
   │   - replies to the user via WhatsApp Cloud API
   ▼
[4] Supporting services (all remote, set once, forget)
   - Qdrant Cloud        vector search over the mining knowledge base
   - MinIO (or S3)       uploaded files / media
   - HF Inference Router openai/gpt-oss-120b  (LLM + tool calling)
   - Serper              live web search
```

---

## 0. Prerequisites — accounts you need

| Service            | Sign up at                                   | What you need                        |
| ------------------ | -------------------------------------------- | ------------------------------------ |
| Hugging Face       | huggingface.co                               | username + a **write** access token (`hf_...`) |
| Supabase           | supabase.com                                 | project + service_role key + DB URL  |
| Cloudflare         | dash.cloudflare.com                          | account for Workers                  |
| Qdrant Cloud       | cloud.qdrant.io                              | cluster URL + API key                |
| MinIO              | (use any S3: Cloudflare R2 / Backblaze B2)   | endpoint + access/secret keys        |
| Meta for Devs      | developers.facebook.com                      | WhatsApp Cloud API app credentials   |
| Serper             | serper.dev                                   | API key                              |

Estimated monthly cost on the always-on path: **~$1.50** (Space ~$21/mo on
CPU-Upgrade; use the **sleep-on-idle** option to cut this to near $0).

---

## 1. Supabase — database

1. Create a project at [supabase.com](https://supabase.com) (free tier, choose
   a region close to your WhatsApp users).
2. Open **Project Settings → Database → Connection string**.
   - Copy the **Session pooler** string (for the Space) — e.g.
     `postgresql://postgres.<ref>:<password>@aws-0-<region>.pooler.supabase.com:6543/postgres`
   - Note: the worker does **not** use this string (it uses PostgREST), so only
     the Space needs it.
3. In **Project Settings → API**, copy:
   - **Project URL** (https://`<ref>`.supabase.co) → `SUPABASE_URL`
   - **service_role secret key** → `SUPABASE_SERVICE_KEY` (never expose this)
4. Open **SQL Editor** and run the entire contents of
   [`deployment/supabase_schema.sql`](deployment/supabase_schema.sql) once.
   This creates `wa_inbox`, `conversations`, `user_memories`, `tasks`,
   `audit_logs`, the timestamp trigger, and permissive RLS for the
   service_role key. Verify: **Table Editor → wa_inbox** exists.

---

## 2. Qdrant — vector database

1. Create a free cluster at [cloud.qdrant.io](https://cloud.qdrant.io).
2. Copy the cluster URL (https://`<cluster>`.qdrant.io) → `QDRANT_URL`.
3. Generate an API key in the cluster's **Access Control** → `QDRANT_API_KEY`.
4. No collections need to be created manually — the Space creates
   `company_knowledge` and seeds it on first boot.

---

## 3. Object storage — MinIO / S3-compatible

Any S3-compatible bucket works. Recommended (no new account):
**Cloudflare R2** (10 GB free) or **Backblaze B2** (10 GB free).

- `MINIO_ENDPOINT`   e.g. `https://<account>.r2.cloudflarestorage.com`
- `MINIO_ACCESS_KEY`, `MINIO_SECRET_KEY`, `MINIO_BUCKET_NAME=ai-os-storage`

If you skip this, the bot still works — media just isn't archived to object
storage (it stays referenced by WhatsApp media id).

---

## 4. Hugging Face Space — the brain

The Space is a Docker container running `hf_runner.py` (FastAPI + the queue
worker in one process). It auto-creates and seeds all DB tables, downloads the
embedding model, and ingests the Kapoeta/mining knowledge base on first boot.

### 4.1 Local test (optional but recommended)

```bash
# requires Docker; from repo root
docker build -t aios-worker:test .
docker run --rm -p 17860:7860 \
  -e DATABASE_URL="postgresql://..." -e QDRANT_URL="..." -e QDRANT_API_KEY="..." \
  -e LOCAL_LLM_URL="https://router.huggingface.co/v1" \
  -e LOCAL_LLM_MODEL="openai/gpt-oss-120b" \
  -e LOCAL_LLM_API_KEY="hf_..." -e PROCESSING_MODE="queue" \
  -e HF_TOKEN="hf_..." -e WHATSAPP_TOKEN="..." -e WHATSAPP_PHONE_NUMBER_ID="..." \
  -e API_KEY="x" -e SECRET_KEY="x" -e ENVIRONMENT="production" \
  aios-worker:test
# then:  curl http://localhost:17860/health  -> {"status":"healthy",...}
```

### 4.2 Create the Space

```bash
pip install -U "huggingface_hub[hf_transfer]"
hf auth login          # paste your write token

cp hf.secrets.example.env hf.secrets.env
# ... edit hf.secrets.env and fill in every value from the steps above ...

./hf_deploy.sh <your-hf-username> aios-worker
```

`hf_deploy.sh` automatically:
1. Creates a public Docker Space `username/aios-worker`
2. Pushes the repo to it (first build runs `pip install` + model download)
3. Sets hardware to **CPU Upgrade** (always-on)
4. Loads every key from `hf.secrets.env` into Space secrets

Then open `https://huggingface.co/spaces/<username>/aios-worker` → **Settings →
Diagnostics** to watch the build. The app is live when the **RESTART / /health**
check turns green (first boot takes a few minutes: it ingests 1,479 documents).

> The Space URL becomes `https://<username>-aios-worker.hf.space`.
> Only needed for manual testing — WhatsApp traffic comes through the worker.

### 4.3 LLM: HF Inference Providers (free credits)

No extra deployment needed. The router URL is already in the secrets:
- `LOCAL_LLM_URL=https://router.huggingface.co/v1`
- `LOCAL_LLM_MODEL=openai/gpt-oss-120b`
- `LOCAL_LLM_API_KEY=hf_<your-write-token>`

New accounts get a monthly credit allowance (e.g. ~$0.10 free, ~$2 on the
$5/mo PRO plan). Each WhatsApp answer is a fraction of a cent, so this lasts a
long time. Monitor usage at huggingface.co → **Settings → Billing**.

---

## 5. Cloudflare Worker — the always-on front brain

```bash
mkdir -p deployment/worker && cd deployment/worker
npm init -y
npm i -D wrangler
npx wrangler login

# secrets (never in source)
npx wrangler secret put APP_SECRET            # Meta app secret
npx wrangler secret put SUPABASE_URL          # https://<ref>.supabase.co
npx wrangler secret put SUPABASE_SERVICE_KEY  # service_role key
npx wrangler secret put WHATSAPP_TOKEN        # Meta permanent access token

# plain vars
npx wrangler var put VERIFY_TOKEN <your-token>
npx wrangler var put WHATSAPP_PHONE_NUMBER_ID <id>

# deploy the worker
cp ../../cloudflare-worker.js src/index.js
npx wrangler deploy
```

The worker now answers `/grade`, `/help` and math **instantly**, sends a
`*Got it*` receipt for everything else, and queues the message in Supabase.
`worker.workers.dev` URL (e.g. `https://aios-worker.<you>.workers.dev`) is the
webhook URL you'll give to Meta next.

---

## 6. Meta WhatsApp Cloud API

1. [developers.facebook.com](https://developers.facebook.com) → create an app
   → add **WhatsApp** product.
2. Link a Meta business page / test phone number.
3. **API Setup**:
   - `WHATSAPP_TOKEN` = the temporary token here, or a **permanent** token you
     generate via System User in Business Settings.
   - `WHATSAPP_PHONE_NUMBER_ID` = the phone number ID.
4. **Configuration → Webhook**:
   - Callback URL: `https://<your-worker>.workers.dev/webhook`
   - Verify token: exactly what you set as `VERIFY_TOKEN`
   - Subscribe to **messages**.
5. Send a WhatsApp message to your test number.

---

## 7. End-to-end test

| Step | What happens |
| ---- | ------------ |
| Send `/help` | Worker answers instantly (no queue). |
| Send `/grade value 5.2 10000 93` | Worker computes and replies instantly. |
| Send `What do we know about Kapoeta gold?` | Worker receipts → Space LLM answers from the Kapoeta knowledge base (via Qdrant). |
| Send a photo of a rock | Worker receipts → Space downloads media via the WhatsApp API and runs vision analysis. |
| Send a voice note | Worker receipts → Space transcribes (gTTS/STT) and replies. |

Debug checks:
- **Supabase Table Editor → wa_inbox**: new messages appear as `pending` → then
  `answered` with the `reply_text` column filled.
- **Space Diagnostics / logs**: watch the worker poll rows and answer.
- **Qdrant**: `company_knowledge` should contain 1,479 documents after first boot.

---

## 8. Cost & scale notes

- **Free tier** covers Supabase, Cloudflare worker, Qdrant (1 GB), Serper
  (2,500 searches), and HF router credits.
- **Only real cost** is the Space hardware. Use **CPU Upgrade** for always-on
  (~$21/mo) or **CPU Basic + sleep-on-idle** for near-$0 with ~30s cold start.
- The architecture is horizontal: if you outgrow one Space, you can point the
  worker at a queue consumed by several Spaces, or move to HF Enterprise /
  your own VPS — nothing else changes.
- Secrets live only in HF Space settings and Cloudflare — never in git
  (`hf.secrets.env` is gitignored).
