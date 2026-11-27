"""
Entry point for a Hugging Face Space with the Gradio SDK (ZeroGPU hardware, free tier).

Serves the same FastAPI API as `app.main` (/health, /api/...) for the Cloudflare Pages
frontend, plus a small status page at "/" so the Space page shows something useful.
Embeddings run on CPU; no request touches the GPU.
"""

from __future__ import annotations

import gradio as gr
import uvicorn

from app.main import app, health

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
        "Endpoints: `GET /health`, `GET /api/databases`, `GET /api/databases/{db_id}`, "
        "`POST /api/generate`, `POST /api/execute`."
    )


with gr.Blocks(title="GraphRAG 1-Stage Text-to-SQL API") as demo:
    gr.Markdown("## GraphRAG 1-Stage Text-to-SQL API")
    status = gr.Markdown("Checking status…")
    gr.Button("Refresh status").click(_status_markdown, outputs=status)
    demo.load(_status_markdown, outputs=status)

# API routes are registered on `app` first, so they take precedence over the Gradio mount at "/".
app = gr.mount_gradio_app(app, demo, path="/")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=7860)
