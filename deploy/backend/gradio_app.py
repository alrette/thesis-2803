"""
Entry point for a Hugging Face Space with the Gradio SDK (ZeroGPU hardware, free tier).

Serves the same FastAPI API as `app.main` (/health, /api/...) for the Cloudflare Pages
frontend, plus a small status page at "/" so the Space page shows something useful.
Embeddings run on CPU; no request touches the GPU.
"""

from __future__ import annotations

import threading
from contextlib import asynccontextmanager

import gradio as gr
from fastapi.routing import APIRoute, APIRouter

import app.main as api
from app.main import app as api_app
from app.main import health

try:
    import spaces  # preinstalled on ZeroGPU; optional when running locally

    @spaces.GPU
    def _zerogpu_placeholder() -> None:
        """ZeroGPU Spaces must declare a GPU function at startup; this one is never called, so no GPU quota is used."""

except ImportError:
    pass


def _status_markdown() -> str:
    h = health()
    if h.get("ready"):
        state = "Ready" if h.get("llm_configured") else "Ready, but LLM_API_KEY is not set"
    else:
        state = f"Not ready: {h.get('error') or 'starting up'}"
    return (
        f"**Status:** {state}\n\n"
        f"- Databases: {h.get('database_count')}\n"
        f"- Embedding model: `{h.get('embedding_model')}`\n"
        f"- LLM: `{h.get('llm_model')}` ({h.get('llm_api_mode')} mode)\n"
        f"- Few-shot k: {h.get('few_shot_k')}, table threshold: {h.get('table_threshold')}\n\n"
        "This Space is the API behind the Text-to-SQL Workbench frontend. "
        "Frontend API base URL: `https://<space>.hf.space/gradio_api/sql` "
        "(`/health`, `/api/databases`, `/api/databases/{db_id}`, `/api/generate`, `/api/execute`)."
    )


with gr.Blocks(title="GraphRAG 1-Stage Text-to-SQL API") as demo:
    gr.Markdown("## GraphRAG 1-Stage Text-to-SQL API")
    status = gr.Markdown("Checking status…")
    gr.Button("Refresh status").click(_status_markdown, outputs=status)
    demo.load(_status_markdown, outputs=status)


@asynccontextmanager
async def background_startup(_app):
    """Load bge-m3 in a thread: a blocking load outlasts Gradio's startup wait ("Cannot find empty port").
    Until it finishes, /health says ready=false and the API answers 503 "Service is starting up"."""
    api.state = api.AppState(api.get_settings())
    threading.Thread(target=api.state.load, name="backend-load", daemon=True).start()
    yield


# Spaces start the Gradio server on port 7860 themselves, so the API rides on Gradio's app instead of
# running its own uvicorn: our routes, CORS middleware and startup (lifespan) go in through app_kwargs.
API_ROUTES = [r for r in api_app.routes if isinstance(r, APIRoute) and (r.path == "/health" or r.path.startswith("/api/"))]

# On Spaces a Gradio SSR server sits in front and forwards only /gradio_api/* to Python, so the frontend
# uses API base URL https://<space>.hf.space/gradio_api/sql; the unprefixed routes remain for local runs.
API_PREFIX = "/gradio_api/sql"
_prefixed = APIRouter(prefix=API_PREFIX)
for _route in API_ROUTES:
    _prefixed.add_api_route(_route.path, _route.endpoint, methods=list(_route.methods), response_model=_route.response_model)

if __name__ == "__main__":
    demo.launch(
        app_kwargs={
            "routes": API_ROUTES + list(_prefixed.routes),
            "middleware": list(api_app.user_middleware),
            "lifespan": background_startup,
        }
    )
