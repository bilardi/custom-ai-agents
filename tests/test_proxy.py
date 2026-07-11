"""Test the FastAPI proxy that mimics the Ollama API."""

import json
from unittest.mock import AsyncMock, MagicMock

from fastapi.testclient import TestClient

from app.proxy import create_app, make_generate


def _client(router, session=None):
    session = session or MagicMock()
    app = create_app(router=router, session=session, model="qwen3", ollama_url="http://ollama")
    return TestClient(app), session


def test_chat_returns_routed_answer_without_calling_ollama():
    router = MagicMock()
    router.handle = AsyncMock(return_value=["ROUTED"])
    client, session = _client(router)
    resp = client.post(
        "/api/chat",
        json={"messages": [{"role": "user", "content": "/dask x"}], "stream": False},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["message"]["content"] == "ROUTED"
    assert body["done"] is True
    router.handle.assert_called_once_with([{"role": "user", "content": "/dask x"}])
    session.post.assert_not_called()


def test_chat_passes_last_n_messages_when_history_is_set():
    router = MagicMock()
    router.handle = AsyncMock(return_value=["ROUTED"])
    app = create_app(
        router=router, session=MagicMock(), model="qwen3", ollama_url="http://ollama", history=2
    )
    client = TestClient(app)
    messages = [
        {"role": "user", "content": "one"},
        {"role": "assistant", "content": "two"},
        {"role": "user", "content": "/dask three"},
    ]
    client.post("/api/chat", json={"messages": messages, "stream": False})
    router.handle.assert_awaited_once_with(messages[-2:])


def test_chat_joins_streamed_tokens_without_extra_spaces():
    router = MagicMock()
    router.handle = AsyncMock(return_value=["The", " good", " answer"])
    client, _ = _client(router)
    resp = client.post(
        "/api/chat",
        json={"messages": [{"role": "user", "content": "/dask x"}], "stream": False},
    )
    assert resp.json()["message"]["content"] == "The good answer"


def test_chat_passes_through_to_ollama_when_not_routed():
    router = MagicMock()
    router.handle = AsyncMock(return_value=None)
    session = MagicMock()
    ollama_resp = MagicMock()
    ollama_resp.content = b'{"message":{"content":"from ollama"}}'
    ollama_resp.status_code = 200
    session.post.return_value = ollama_resp
    client, _ = _client(router, session)
    resp = client.post(
        "/api/chat",
        json={"messages": [{"role": "user", "content": "hi"}], "stream": False},
    )
    assert resp.status_code == 200
    assert resp.json()["message"]["content"] == "from ollama"
    assert session.post.call_args[0][0] == "http://ollama/api/chat"


def test_chat_streaming_returns_ndjson_lines():
    router = MagicMock()
    router.handle = AsyncMock(return_value=["ROUTED"])
    client, _ = _client(router)
    resp = client.post(
        "/api/chat",
        json={"messages": [{"role": "user", "content": "/dask x"}], "stream": True},
    )
    lines = [line for line in resp.text.splitlines() if line.strip()]
    first = json.loads(lines[0])
    last = json.loads(lines[-1])
    assert first["message"]["content"] == "ROUTED"
    assert first["done"] is False
    assert last["done"] is True


def test_generate_returns_routed_answer():
    router = MagicMock()
    router.handle = AsyncMock(return_value=["ROUTED"])
    client, session = _client(router)
    resp = client.post("/api/generate", json={"prompt": "/web news", "stream": False})
    assert resp.json()["response"] == "ROUTED"
    assert resp.json()["done"] is True
    session.post.assert_not_called()


def test_generate_passes_through_when_not_routed():
    router = MagicMock()
    router.handle = AsyncMock(return_value=None)
    session = MagicMock()
    ollama_resp = MagicMock()
    ollama_resp.content = b'{"response":"ollama"}'
    ollama_resp.status_code = 200
    session.post.return_value = ollama_resp
    client, _ = _client(router, session)
    resp = client.post("/api/generate", json={"prompt": "hi", "stream": False})
    assert resp.json()["response"] == "ollama"
    assert session.post.call_args[0][0] == "http://ollama/api/generate"


def test_tags_forwards_to_ollama():
    router = MagicMock()
    session = MagicMock()
    ollama_resp = MagicMock()
    ollama_resp.json.return_value = {"models": []}
    ollama_resp.status_code = 200
    session.get.return_value = ollama_resp
    client, _ = _client(router, session)
    resp = client.get("/api/tags")
    assert resp.json() == {"models": []}
    session.get.assert_called_once_with("http://ollama/api/tags")


def test_embeddings_forwards_to_ollama():
    router = MagicMock()
    session = MagicMock()
    ollama_resp = MagicMock()
    ollama_resp.content = b'{"embedding":[0.1]}'
    ollama_resp.status_code = 200
    session.post.return_value = ollama_resp
    client, _ = _client(router, session)
    resp = client.post("/api/embeddings", json={"model": "qwen3", "prompt": "x"})
    assert resp.json()["embedding"] == [0.1]
    assert session.post.call_args[0][0] == "http://ollama/api/embeddings"


def test_show_forwards_to_ollama():
    router = MagicMock()
    session = MagicMock()
    ollama_resp = MagicMock()
    ollama_resp.content = b'{"model":"qwen3"}'
    ollama_resp.status_code = 200
    session.post.return_value = ollama_resp
    client, _ = _client(router, session)
    resp = client.post("/api/show", json={"name": "qwen3"})
    assert resp.json()["model"] == "qwen3"
    assert session.post.call_args[0][0] == "http://ollama/api/show"


def _forwarding_client(content=b"{}"):
    router = MagicMock()
    session = MagicMock()
    ollama_resp = MagicMock()
    ollama_resp.content = content
    ollama_resp.status_code = 200
    ollama_resp.json.return_value = {"ok": True}
    session.post.return_value = ollama_resp
    session.get.return_value = ollama_resp
    client, _ = _client(router, session)
    return client, session


def test_v1_chat_completions_forwards_to_ollama():
    client, session = _forwarding_client(b'{"choices":[]}')
    resp = client.post("/v1/chat/completions", json={"model": "qwen3", "messages": []})
    assert resp.json()["choices"] == []
    assert session.post.call_args[0][0] == "http://ollama/v1/chat/completions"


def test_v1_completions_forwards_to_ollama():
    client, session = _forwarding_client(b'{"choices":[]}')
    resp = client.post("/v1/completions", json={"model": "qwen3", "prompt": "x"})
    assert resp.json()["choices"] == []
    assert session.post.call_args[0][0] == "http://ollama/v1/completions"


def test_v1_embeddings_forwards_to_ollama():
    client, session = _forwarding_client(b'{"data":[]}')
    resp = client.post("/v1/embeddings", json={"model": "qwen3", "input": "x"})
    assert resp.json()["data"] == []
    assert session.post.call_args[0][0] == "http://ollama/v1/embeddings"


def test_v1_models_forwards_to_ollama():
    client, session = _forwarding_client()
    resp = client.get("/v1/models")
    assert resp.json() == {"ok": True}
    assert session.get.call_args[0][0] == "http://ollama/v1/models"


def _stream_response(lines):
    response = MagicMock()
    response.iter_lines.return_value = lines
    return response


def test_make_generate_streams_tokens():
    session = MagicMock()
    session.post.return_value = _stream_response(
        [
            b'{"response":"Hel","done":false}',
            b'{"response":"lo","done":false}',
            b'{"response":"","done":true}',
        ],
    )
    generate = make_generate(session, "qwen3", "http://ollama")
    assert list(generate("hello")) == ["Hel", "lo"]
    assert session.post.call_args.kwargs["json"]["stream"] is True


def test_make_generate_sets_num_ctx_when_given():
    session = MagicMock()
    session.post.return_value = _stream_response([b'{"response":"a","done":true}'])
    generate = make_generate(session, "qwen3", "http://ollama", num_ctx=4096)
    list(generate("hello"))
    assert session.post.call_args.kwargs["json"]["options"] == {"num_ctx": 4096}
