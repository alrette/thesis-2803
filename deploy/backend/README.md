---
title: GraphRAG 1-Stage Text-to-SQL API
emoji: 🕸️
colorFrom: indigo
colorTo: green
sdk: docker
app_port: 7860
pinned: false
---

# GraphRAG 1-Stage + Skeleton Few-Shot API

FastAPI backend powering the GraphRAG Text-to-SQL user evaluation workbench.

## Required Hugging Face Space Secrets

Add these under **Settings → Variables and secrets**:

- `LLM_API_KEY` — Cloudflare API Token with Workers AI permission
- `LLM_BASE_URL` — `https://api.cloudflare.com/client/v4/accounts/<ACCOUNT_ID>/ai/v1`
- `LLM_MODEL` — `@cf/qwen/qwen2.5-coder-32b-instruct`
- `CORS_ORIGINS` — Your Cloudflare Pages URL (e.g. `https://your-project.pages.dev`)

Optional overrides (fixed defaults live in `app/settings.py`):
- `FEW_SHOT_K` (default `0`, matching the final thesis run; set `1` / `3` / `5` / `9` to enable skeleton few-shot)
- `LLM_API_MODE` (default `chat`; Cloudflare Workers AI OpenAI-compatible API supports `/chat/completions`, not `/completions`)
- `TABLE_SIMILARITY_THRESHOLD` (default `0.65`)
- `RATE_LIMIT_PER_MINUTE` (default `30`, per IP)
- `GLOBAL_GENERATE_PER_MINUTE` (default `60`, global `/api/generate` cap)
- `GLOBAL_GENERATE_PER_DAY` (default `500`, global daily `/api/generate` cap)
