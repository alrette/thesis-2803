# GraphRAG Text-to-SQL — User Evaluation Deployment

Web workbench for user evaluation of **GraphRAG 1-Stage** (with optional Skeleton Few-Shot, default `k = 0`) using **Qwen2.5-Coder-32B-Instruct** on **Cloudflare Workers AI** over curated multi-table **Spider** databases.

- **Frontend (`deploy/frontend/`)**: Vite + React + TypeScript + Tailwind + `@xyflow/react` (interactive ERD with live GraphRAG table highlighting) → deployed free on **Cloudflare Pages**.
- **Backend (`deploy/backend/`)**: Self-contained FastAPI service running local **`BAAI/bge-m3`** + NetworkX table-graph path tracing + optional live **`spaCy`** skeleton masking (only loaded when `FEW_SHOT_K > 0`) + read-only native **SQLite** execution + **Cloudflare Workers AI** (`@cf/qwen/qwen2.5-coder-32b-instruct`) → deployed free on **Hugging Face Spaces (CPU Basic, 16 GB RAM)**.

---

## Perbedaan dengan Eksperimen Skripsi

- **Eksperimen skripsi:** memakai `Qwen2.5-Coder` **3B / 7B / 14B** lokal terkuantisasi **4-bit NF4** dengan prompt mentah (tanpa chat template, mode completion, stop di ```` ``` ````).
- **Web demo evaluasi pengguna ini:** memakai **`Qwen2.5-Coder-32B-Instruct`** (`@cf/qwen/qwen2.5-coder-32b-instruct`) melalui **Cloudflare Workers AI** (presisi dikelola provider, mode `chat` via `/v1/chat/completions` dengan `stop=["```"]` karena endpoint OpenAI-compatible Cloudflare tidak menyediakan `/v1/completions`), karena provider serverless untuk varian 7B sudah deprecated.
- **Yang tetap sama:** retrieval **GraphRAG 1-Stage** (`BAAI/bge-m3`, n-gram 1–2 `edge` stopword, threshold tabel `0.65`, FK shortest-path tracing, DDL penuh tabel terpilih), template prompt, SQL cleaner, dan few-shot default **`k = 0`** (masking skeleton tetap siap dipakai jika `FEW_SHOT_K > 0`).

---

## 1. Prepare the Spider Database Bundle

The backend serves curated native Spider `.sqlite` files from `deploy/backend/data/`.

### Option A — Real Spider databases (recommended for user evaluation)
Run the curation script against your local `spider_data/` folder (ranks dev DBs by table/FK/column richness and bundles the top 6 + sample Spider questions):

```bash
cd thesis-2803/deploy/backend
python scripts/prepare_spider_bundle.py \
  --spider-dir ../../data/spider_data \
  --top-n 6
```

Or specify exact Spider dev DBs:

```bash
python scripts/prepare_spider_bundle.py \
  --spider-dir ../../data/spider_data \
  --dbs student_transcripts_tracking dog_kennels car_1 world_1 flight_2 concert_singer
```

> If you plan to enable few-shot (`FEW_SHOT_K > 0`), add `--precompute-embeddings` to save `data/skeletons/train_embeddings.npy` (~14 MB float16) so HF Spaces boots in seconds. With the default `FEW_SHOT_K = 0`, neither `train_embeddings.npy` nor spaCy is loaded at startup.

### Option B — Quick starter demo bundle (no Spider download needed)
```bash
cd thesis-2803/deploy/backend
python scripts/create_demo_data.py
```

---

## 2. Configure Fixed Few-Shot `k` & Retrieval Defaults

Open `deploy/backend/app/settings.py`:

```python
DEFAULT_FEW_SHOT_K: int = 0          # default 0 (final thesis run); change to 1, 3, 5, or 9 if needed
DEFAULT_TABLE_THRESHOLD: float = 0.65
DEFAULT_LLM_MODEL: str = "@cf/qwen/qwen2.5-coder-32b-instruct"
```

All three can also be overridden via environment variables / Hugging Face Space Secrets without editing code.

---

## 3. Run Locally

### Backend
```bash
cd thesis-2803/deploy/backend
python -m venv .venv
# Windows: .venv\Scripts\activate  |  macOS/Linux: source .venv/bin/activate
pip install torch --index-url https://download.pytorch.org/whl/cpu
pip install -r requirements.txt
# Only needed if FEW_SHOT_K > 0:
python -m spacy download en_core_web_sm

# Configure Cloudflare Workers AI in deploy/backend/.env (see .env.example):
#   LLM_BASE_URL=https://api.cloudflare.com/client/v4/accounts/<ACCOUNT_ID>/ai/v1
#   LLM_API_KEY=<your-cloudflare-workers-ai-token>
#   LLM_MODEL=@cf/qwen/qwen2.5-coder-32b-instruct
#   LLM_API_MODE=chat

uvicorn app.main:app --host 0.0.0.0 --port 7860 --reload
```

### Frontend
```bash
cd thesis-2803/deploy/frontend
npm install
npm run dev
```
Open `http://localhost:5173`. (Defaults to `VITE_API_BASE_URL=http://localhost:7860`.)

---

## 4. Deploy Backend to Hugging Face Spaces (Free CPU)

1. Create a new Space on Hugging Face:
   - **SDK**: `Docker`
   - **Hardware**: `CPU basic · 2 vCPU · 16 GB` (Free)
2. Upload/push the contents of `deploy/backend/` (including `Dockerfile`, `requirements.txt`, `README.md`, `app/`, and your generated `data/` folder — **never** upload `.env` or `.venv/`).
   - Track `*.sqlite` (and `*.npy` if using `FEW_SHOT_K > 0`) with Git LFS in the HF Space repo.
3. In the Space's **Settings → Variables and secrets**, set:
   - **Secret:** `LLM_API_KEY` = `<your-cloudflare-workers-ai-token>`
   - **Variables:**
     - `LLM_BASE_URL` = `https://api.cloudflare.com/client/v4/accounts/<ACCOUNT_ID>/ai/v1`
     - `LLM_MODEL` = `@cf/qwen/qwen2.5-coder-32b-instruct`
     - `LLM_API_MODE` = `chat`
     - `CORS_ORIGINS` = `https://<your-project>.pages.dev`
     - *(Optional)* `FEW_SHOT_K` = `0`, `GLOBAL_GENERATE_PER_MINUTE` = `60`, `GLOBAL_GENERATE_PER_DAY` = `500`
4. Verify `https://<your-user>-<your-space>.hf.space/health` returns `"ready": true` and `"llm_configured": true`.

> **Tip:** Free HF Spaces sleep after 48 hours of inactivity (~20–30s cold wake). Hit `/health` once right before starting a user-evaluation session.

---

## 5. Deploy Frontend to Cloudflare Pages (Free)

1. In Cloudflare Dashboard → **Workers & Pages → Create → Pages → Connect to Git** (select this repository).
2. Configure build settings:
   - **Root directory**: `deploy/frontend`
   - **Build command**: `npm run build`
   - **Build output directory**: `dist`
3. Add environment variable:
   - `VITE_API_BASE_URL` = `https://<your-user>-<your-space>.hf.space`
4. Deploy — then add the generated `https://<your-project>.pages.dev` URL to `CORS_ORIGINS` in your HF Space settings.
