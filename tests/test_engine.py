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
    generate = MagicMock(return_value="ANSWER")
    return DeterministicEngine(ag=ag, web=web, generate=generate), ag, web, generate


def test_handle_uses_rag_when_tag_is_a_topic():
    engine, ag, web, generate = _engine(topics=["dask"], chunks=["chunk one", "chunk two"])
    result = engine.handle("/dask how to parallelize a groupby")
    assert result == "ANSWER"
    ag.retrieve.assert_called_once()
    prompt = generate.call_args[0][0]
    assert "chunk one" in prompt
    assert "chunk two" in prompt
    web.search_web.assert_not_called()


def test_handle_searches_web_on_web_tag():
    engine, ag, web, generate = _engine(topics=["dask"], search="SEARCH RESULTS")
    result = engine.handle("/web latest python release")
    assert result == "ANSWER"
    web.search_web.assert_called_once()
    query = web.search_web.call_args[0][0]
    assert "/web" not in query
    assert "SEARCH RESULTS" in generate.call_args[0][0]


def test_handle_visits_url_when_message_has_url():
    engine, ag, web, generate = _engine(page="PAGE TEXT")
    result = engine.handle("summarize https://example.com/post")
    assert result == "ANSWER"
    web.visit_webpage.assert_called_once_with("https://example.com/post")
    assert "PAGE TEXT" in generate.call_args[0][0]


def test_handle_passes_through_plain_message():
    engine, ag, web, generate = _engine(topics=["dask"])
    assert engine.handle("who wrote The Betrothed?") is None
    generate.assert_not_called()


def test_handle_passes_through_unknown_tag():
    engine, ag, web, generate = _engine(topics=["dask"])
    assert engine.handle("/pandas give me a snippet") is None
    generate.assert_not_called()
