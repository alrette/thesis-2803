# GraphRAG Text-to-SQL — User Evaluation Deployment

Web workbench for user evaluation of **GraphRAG 1-Stage + Skeleton Few-Shot (`Qwen2.5-Coder-7B-Instruct`)** on curated multi-table **Spider** databases.

- **Frontend (`deploy/frontend/`)**: Vite + React + TypeScript + Tailwind + `@xyflow/react` (interactive ERD with live GraphRAG table highlighting) → deployed free on **Cloudflare Pages**.
- **Backend (`deploy/backend/`)**: Self-contained FastAPI service running local **`BAAI/bge-m3`** + live **`spaCy`** skeleton masking + NetworkX table-graph path tracing + read-only native **SQLite** execution + OpenAI-compatible **Qwen2.5-Coder-7B** API → deployed free on **Hugging Face Spaces (CPU Basic, 16 GB RAM)**.

---

## 1. Prepare the Spider Database Bundle

The backend serves curated native Spider `.sqlite` files from `deploy/backend/data/`.

### Option A — Real Spider databases (recommended for user evaluation)
Run the curation script against your local `spider_data/` folder (ranks dev DBs by table/FK/column richness and bundles the top 6 + sample Spider questions + train skeletons):

```bash
cd thesis-2803/deploy/backend
python scripts/prepare_spider_bundle.py \
  --spider-dir ../../data/spider_data \
  --top-n 6 \
  --precompute-embeddings
```

Or specify exact Spider dev DBs:

```bash
python scripts/prepare_spider_bundle.py \
  --spider-dir ../../data/spider_data \
  --dbs student_transcripts_tracking dog_kennels car_1 world_1 flight_2 concert_singer \
  --precompute-embeddings
```

> `--precompute-embeddings` saves `data/skeletons/train_embeddings.npy` (~14 MB float16) so HF Spaces boots in seconds instead of encoding 7,000 skeletons on startup.

### Option B — Quick starter demo bundle (no Spider download needed)
```bash
cd thesis-2803/deploy/backend
python scripts/create_demo_data.py
```

---

## 2. Configure Fixed Few-Shot `k` & Retrieval Defaults

Open `deploy/backend/app/settings.py`:

```python
DEFAULT_FEW_SHOT_K: int = 3          # change to 0, 1, 3, 5, or 9
DEFAULT_TABLE_THRESHOLD: float = 0.65
DEFAULT_LLM_MODEL: str = "Qwen/Qwen2.5-Coder-7B-Instruct"
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
python -m spacy download en_core_web_sm

# Set your Qwen2.5-Coder-7B API credentials (see .env.example)
set LLM_BASE_URL=https://dashscope-intl.aliyuncs.com/compatible-mode/v1
set LLM_API_KEY=sk-...
set LLM_MODEL=Qwen/Qwen2.5-Coder-7B-Instruct

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
2. Upload/push the contents of `deploy/backend/` (including `Dockerfile`, `requirements.txt`, `README.md`, `app/`, and your generated `data/` folder).
   - If you include `data/skeletons/train_embeddings.npy` (~14 MB), track `*.npy` and `*.sqlite` with Git LFS in the HF Space repo.
3. In the Space's **Settings → Variables and secrets**, set:
   - `LLM_API_KEY` (Secret)
   - `LLM_BASE_URL` (Variable)
   - `LLM_MODEL` = `Qwen/Qwen2.5-Coder-7B-Instruct` (Variable)
   - `CORS_ORIGINS` = `https://<your-project>.pages.dev` (Variable)
   - *(Optional)* `FEW_SHOT_K` = `3` (or `0`)
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
