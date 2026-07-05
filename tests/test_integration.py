"""Integration tests that hit a running Ollama.

Opt-in: deselected by default, run with `uv run pytest -m integration`.
Expects Ollama reachable at OLLAMA_URL (default http://127.0.0.1:11435).

The app is driven through httpx's ASGITransport (not starlette's TestClient) so
it runs on the test event loop in the main thread, mirroring uvicorn: a single
loop keeps the agent's async client valid, and OpenSSL initializes on the main
thread instead of a portal worker thread.
"""

import os

import pytest
from httpx import ASGITransport, AsyncClient

from app.proxy import build_app

pytestmark = pytest.mark.integration

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://127.0.0.1:11435")


def _app(engine, *, show_trace=False):
    os.environ["ENGINE"] = engine
    os.environ["OLLAMA_URL"] = OLLAMA_URL
    os.environ["MODEL"] = os.environ.get("MODEL", "qwen2.5")
    os.environ["EMBED_MODEL"] = os.environ.get("EMBED_MODEL", "nomic-embed-text")
    os.environ["CONTEXT_LENGTH"] = os.environ.get("CONTEXT_LENGTH", "4096")
    os.environ["SHOW_TOOL_TRACE"] = "true" if show_trace else "false"
    return build_app()


async def test_tool_agent_answers_via_real_ollama():
    transport = ASGITransport(app=_app("tool-agent"))
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/api/chat",
            json={
                "messages": [{"role": "user", "content": "in dask, how to parallelize a groupby?"}],
                "stream": False,
            },
        )
    assert resp.status_code == 200
    assert resp.json()["message"]["content"]


async def test_tool_agent_streams_tool_trace_when_enabled():
    transport = ASGITransport(app=_app("tool-agent", show_trace=True))
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/api/chat",
            json={
                "messages": [{"role": "user", "content": "in dask, how to parallelize a groupby?"}],
                "stream": False,
            },
        )
    assert resp.status_code == 200
    content = resp.json()["message"]["content"]
    assert "> " in content
    assert content.strip()
