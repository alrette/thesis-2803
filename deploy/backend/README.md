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

- `LLM_API_KEY` — API key for your OpenAI-compatible Qwen2.5-Coder-7B provider
- `LLM_BASE_URL` — Provider OpenAI-compatible base URL (e.g. DashScope / HF Router / SiliconFlow / DeepInfra)
- `LLM_MODEL` — e.g. `Qwen/Qwen2.5-Coder-7B-Instruct`
- `CORS_ORIGINS` — Your Cloudflare Pages URL (e.g. `https://your-project.pages.dev`)

Optional overrides (fixed defaults live in `app/settings.py`):
- `FEW_SHOT_K` (default `3`, set `0` to disable few-shot)
- `LLM_API_MODE` (`chat` default, or `completion`)
- `TABLE_SIMILARITY_THRESHOLD` (default `0.65`)
