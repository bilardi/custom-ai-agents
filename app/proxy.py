"""FastAPI proxy that mimics the Ollama API, routing through an engine."""

import json
import os
from collections.abc import AsyncIterator, Callable, Iterator
from typing import TYPE_CHECKING, Any

import requests
from any_agent import AgentConfig, AnyAgent
from any_agent.callbacks import get_default_callbacks
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response, StreamingResponse

from app.ag.chroma_db import ChromaDb
from app.engine.deterministic import DeterministicEngine
from app.engine.tool_agent import ToolAgentEngine, ToolTraceCallback
from app.prompts import load_prompt
from app.router import Router
from app.tools.web_browsing import WebBrowser

if TYPE_CHECKING:
    from app.engine.base import Engine


def _chat_body(model: str, content: str, *, done: bool) -> dict[str, Any]:
    return {"model": model, "message": {"role": "assistant", "content": content}, "done": done}


def _generate_body(model: str, content: str, *, done: bool) -> dict[str, Any]:
    return {"model": model, "response": content, "done": done}


async def _to_async(tokens: AsyncIterator[str] | Iterator[str]) -> AsyncIterator[str]:
    """Normalize a sync or async token stream into an async iterator."""
    if isinstance(tokens, AsyncIterator):
        async for token in tokens:
            yield token
    else:
        for token in tokens:
            yield token


async def _routed_response(
    model: str,
    tokens: AsyncIterator[str] | Iterator[str],
    builder: Callable[..., dict[str, Any]],
    *,
    stream: bool,
) -> Response:
    if not stream:
        content = "".join([token async for token in _to_async(tokens)])
        return JSONResponse(builder(model, content, done=True))

    async def stream_ndjson() -> AsyncIterator[str]:
        async for token in _to_async(tokens):
            yield json.dumps(builder(model, token, done=False)) + "\n"
        yield json.dumps(builder(model, "", done=True)) + "\n"

    return StreamingResponse(stream_ndjson(), media_type="application/x-ndjson")


def make_generate(
    session: Any,  # noqa: ANN401 (injected HTTP client to Ollama)
    model: str,
    ollama_url: str,
    num_ctx: int | None = None,
) -> Callable[[str], Iterator[str]]:
    """Return a callable that streams the Ollama /api/generate response token by token."""

    def generate(prompt: str) -> Iterator[str]:
        body: dict[str, Any] = {"model": model, "prompt": prompt, "stream": True}
        if num_ctx is not None:
            body["options"] = {"num_ctx": num_ctx}
        response = session.post(f"{ollama_url}/api/generate", json=body, stream=True)
        for line in response.iter_lines():
            if line:
                token = json.loads(line).get("response", "")
                if token:
                    yield token

    return generate


def create_app(  # noqa: C901
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
        answer = await router.handle(last_message)
        if answer is not None:
            return await _routed_response(
                model, answer, _chat_body, stream=body.get("stream", True)
            )
        return forward_post("/api/chat", body)

    @app.post("/api/generate")
    async def generate(request: Request) -> Response:
        body = await request.json()
        answer = await router.handle(body.get("prompt", ""))
        if answer is not None:
            return await _routed_response(
                model, answer, _generate_body, stream=body.get("stream", True)
            )
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

    @app.post("/v1/chat/completions")
    async def chat_completions(request: Request) -> Response:
        return forward_post("/v1/chat/completions", await request.json())

    @app.post("/v1/completions")
    async def completions(request: Request) -> Response:
        return forward_post("/v1/completions", await request.json())

    @app.post("/v1/embeddings")
    async def v1_embeddings(request: Request) -> Response:
        return forward_post("/v1/embeddings", await request.json())

    @app.get("/v1/models")
    def v1_models() -> dict[str, Any]:
        return session.get(f"{ollama_url}/v1/models").json()

    return app


def build_app() -> FastAPI:
    """Compose the proxy from environment configuration."""
    model = os.getenv("MODEL", "qwen3")
    embed_model = os.getenv("EMBED_MODEL", "qwen3")
    ollama_url = os.getenv("OLLAMA_URL", "http://localhost:11434")
    mode = os.getenv("ENGINE", "deterministic")
    top_k = int(os.getenv("TOP_K", "3"))
    context_length = os.getenv("CONTEXT_LENGTH")
    num_ctx = int(context_length) if context_length else None
    ag = ChromaDb(embed_model=embed_model, ollama_url=f"{ollama_url}/api/embeddings", top_k=top_k)
    web = WebBrowser()

    engines: dict[str, Engine] = {}
    if mode == "deterministic":
        generate = make_generate(requests, model, ollama_url, num_ctx=num_ctx)
        engines["deterministic"] = DeterministicEngine(ag=ag, web=web, generate=generate)
    elif mode == "tool-agent":
        show_trace = os.getenv("SHOW_TOOL_TRACE", "").lower() in {"1", "true", "yes"}

        async def make_agent() -> AnyAgent:
            return await AnyAgent.create_async(
                "tinyagent",
                AgentConfig(
                    model_id=f"ollama:{model}",
                    api_base=ollama_url,
                    instructions=load_prompt("tool_agent"),
                    tools=[ag.list_topics, ag.retrieve, web.search_web, web.visit_webpage],
                    callbacks=[*get_default_callbacks(), ToolTraceCallback()],
                ),
            )

        engines["tool-agent"] = ToolAgentEngine(agent_factory=make_agent, show_trace=show_trace)

    router = Router(engines=engines, mode=mode)
    return create_app(router=router, model=model, ollama_url=ollama_url)
