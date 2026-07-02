"""FastAPI proxy that mimics the Ollama API, routing through an engine."""

import json
from collections.abc import Callable, Iterator
from typing import Any

import requests
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response, StreamingResponse

from app.router import Router


def _chat_body(model: str, content: str, *, done: bool) -> dict[str, Any]:
    return {"model": model, "message": {"role": "assistant", "content": content}, "done": done}


def _generate_body(model: str, content: str, *, done: bool) -> dict[str, Any]:
    return {"model": model, "response": content, "done": done}


def _routed_response(
    model: str,
    answer: str,
    builder: Callable[..., dict[str, Any]],
    *,
    stream: bool,
) -> Response:
    if not stream:
        return JSONResponse(builder(model, answer, done=True))

    def stream_ndjson() -> Iterator[str]:
        yield json.dumps(builder(model, answer, done=False)) + "\n"
        yield json.dumps(builder(model, "", done=True)) + "\n"

    return StreamingResponse(stream_ndjson(), media_type="application/x-ndjson")


def create_app(
    router: Router,
    session: Any = requests,  # noqa: ANN401 (injected HTTP client to Ollama)
    model: str = "qwen3",
    ollama_url: str = "http://localhost:11434",
) -> FastAPI:
    """Build the proxy app wired to a router and an Ollama HTTP client."""
    app = FastAPI()

    def forward_post(path: str, body: dict[str, Any]) -> Response:
        upstream = session.post(f"{ollama_url}{path}", json=body)
        return Response(
            content=upstream.content,
            status_code=upstream.status_code,
            media_type="application/json",
        )

    @app.post("/api/chat")
    async def chat(request: Request) -> Response:
        body = await request.json()
        messages = body.get("messages", [])
        last_message = messages[-1]["content"] if messages else ""
        answer = router.handle(last_message)
        if answer is not None:
            return _routed_response(model, answer, _chat_body, stream=body.get("stream", True))
        return forward_post("/api/chat", body)

    @app.post("/api/generate")
    async def generate(request: Request) -> Response:
        body = await request.json()
        answer = router.handle(body.get("prompt", ""))
        if answer is not None:
            return _routed_response(model, answer, _generate_body, stream=body.get("stream", True))
        return forward_post("/api/generate", body)

    @app.post("/api/embeddings")
    async def embeddings(request: Request) -> Response:
        return forward_post("/api/embeddings", await request.json())

    @app.post("/api/show")
    async def show(request: Request) -> Response:
        return forward_post("/api/show", await request.json())

    @app.get("/api/tags")
    def tags() -> dict[str, Any]:
        return session.get(f"{ollama_url}/api/tags").json()

    return app
