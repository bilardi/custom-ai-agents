"""Test the DeterministicEngine message rules."""

from unittest.mock import MagicMock

from app.engine.deterministic import DeterministicEngine


def _engine(topics=None, search="web results", page="page text", chunks=None):
    ag = MagicMock()
    ag.list_topics.return_value = topics or []
    ag.retrieve.return_value = chunks or []
    web = MagicMock()
    web.search_web.return_value = search
    web.visit_webpage.return_value = page
    generate = MagicMock(return_value=["ANSWER"])
    return DeterministicEngine(ag=ag, web=web, generate=generate), ag, web, generate


def _msg(text):
    return [{"role": "user", "content": text}]


async def test_handle_uses_rag_when_tag_is_a_topic():
    engine, ag, web, generate = _engine(topics=["dask"], chunks=["chunk one", "chunk two"])
    result = await engine.handle(_msg("/dask how to parallelize a groupby"))
    assert "".join(result) == "ANSWER"
    ag.retrieve.assert_called_once()
    prompt = generate.call_args[0][0]
    assert "chunk one" in prompt
    assert "chunk two" in prompt
    web.search_web.assert_not_called()


async def test_handle_searches_web_on_web_tag():
    engine, ag, web, generate = _engine(topics=["dask"], search="SEARCH RESULTS")
    result = await engine.handle(_msg("/web latest python release"))
    assert "".join(result) == "ANSWER"
    web.search_web.assert_called_once()
    query = web.search_web.call_args[0][0]
    assert "/web" not in query
    assert "SEARCH RESULTS" in generate.call_args[0][0]


async def test_handle_visits_url_when_message_has_url():
    engine, ag, web, generate = _engine(page="PAGE TEXT")
    result = await engine.handle(_msg("summarize https://example.com/post"))
    assert "".join(result) == "ANSWER"
    web.visit_webpage.assert_called_once_with("https://example.com/post")
    assert "PAGE TEXT" in generate.call_args[0][0]


async def test_handle_streams_all_tokens_in_order():
    engine, _ag, _web, generate = _engine(topics=["dask"], chunks=["c"])
    generate.return_value = ["THE", " GOOD", " ANSWER"]
    assert list(await engine.handle(_msg("/dask x"))) == ["THE", " GOOD", " ANSWER"]


async def test_handle_routes_on_last_message_ignoring_history():
    engine, ag, _web, generate = _engine(topics=["dask"], chunks=["c"])
    messages = [
        {"role": "user", "content": "hello"},
        {"role": "assistant", "content": "hi"},
        {"role": "user", "content": "/dask x"},
    ]
    assert "".join(await engine.handle(messages)) == "ANSWER"
    ag.retrieve.assert_called_once()


async def test_handle_passes_through_plain_message():
    engine, ag, web, generate = _engine(topics=["dask"])
    assert await engine.handle(_msg("who wrote The Betrothed?")) is None
    generate.assert_not_called()


async def test_handle_passes_through_unknown_tag():
    engine, ag, web, generate = _engine(topics=["dask"])
    assert await engine.handle(_msg("/pandas give me a snippet")) is None
    generate.assert_not_called()
