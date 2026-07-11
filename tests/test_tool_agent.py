"""Test the ToolAgentEngine."""

from unittest.mock import MagicMock

from app.engine.tool_agent import (
    ToolAgentEngine,
    ToolTraceCallback,
    _describe_tool,
    _is_malformed,
    _to_prompt,
)


def _msg(text):
    return [{"role": "user", "content": text}]


def test_describe_tool_covers_write_code_and_fallback():
    assert _describe_tool("write_code", {}) == "> writing code...\n\n"
    assert _describe_tool("unknown", {}).startswith("> running unknown")


def _agent(final_output, on_run=None):
    trace = MagicMock()
    trace.final_output = final_output

    async def run_async(message):
        if on_run is not None:
            on_run(message)
        return trace

    agent = MagicMock()
    agent.run_async = run_async
    return agent


def _factory(agent):
    async def factory():
        return agent

    return factory


def test_is_malformed_detects_leaked_tool_calls():
    assert _is_malformed("<|python_tag|>write_code(task='x')")
    assert _is_malformed('{"name": "write_code", "parameters": {}}')
    assert _is_malformed("here is write_code(task='x')")
    assert not _is_malformed("```python\nx = 1\n```")


def _sequence_agent(outputs):
    calls = {"n": 0}

    async def run_async(_message):
        i = calls["n"]
        calls["n"] += 1
        trace = MagicMock()
        trace.final_output = outputs[min(i, len(outputs) - 1)]
        return trace

    agent = MagicMock()
    agent.run_async = run_async
    agent.calls = calls
    return agent


async def test_answer_retries_once_on_malformed_output():
    agent = _sequence_agent(["<|python_tag|>write_code(task='x')", "clean answer"])
    engine = ToolAgentEngine(agent_factory=_factory(agent))
    result = await engine.handle(_msg("q"))
    assert "".join([chunk async for chunk in result]) == "clean answer"
    assert agent.calls["n"] == 2


async def test_answer_no_retry_when_clean():
    agent = _sequence_agent(["clean answer"])
    engine = ToolAgentEngine(agent_factory=_factory(agent))
    result = await engine.handle(_msg("q"))
    assert "".join([chunk async for chunk in result]) == "clean answer"
    assert agent.calls["n"] == 1


async def test_handle_runs_agent_and_returns_final_output():
    agent = _agent("AGENT ANSWER")
    engine = ToolAgentEngine(agent_factory=_factory(agent))
    result = await engine.handle(_msg("what is dask?"))
    assert "".join([chunk async for chunk in result]) == "AGENT ANSWER"


async def test_handle_without_trace_ignores_tool_events():
    cb = ToolTraceCallback()

    def on_run(_message):
        cb.before_tool_execution(MagicMock(), {"name": "list_topics", "arguments": {}})

    agent = _agent("ANSWER", on_run=on_run)
    engine = ToolAgentEngine(agent_factory=_factory(agent), show_trace=False)
    result = await engine.handle(_msg("q"))
    assert [chunk async for chunk in result] == ["ANSWER"]


async def test_handle_streams_tool_trace_before_final_output():
    cb = ToolTraceCallback()

    def on_run(_message):
        cb.before_tool_execution(MagicMock(), {"name": "list_topics", "arguments": {}})
        cb.before_tool_execution(MagicMock(), {"name": "retrieve", "arguments": {"topic": "dask"}})

    agent = _agent("ANSWER", on_run=on_run)
    engine = ToolAgentEngine(agent_factory=_factory(agent), show_trace=True)
    result = await engine.handle(_msg("q"))
    chunks = [chunk async for chunk in result]
    assert chunks == [
        "> checking indexed topics...\n\n",
        "> reading local docs on 'dask'...\n\n",
        "ANSWER",
    ]


def test_to_prompt_passes_single_message_through():
    assert _to_prompt([{"role": "user", "content": "hello"}]) == "hello"


def test_to_prompt_renders_multi_message_transcript():
    messages = [
        {"role": "user", "content": "first"},
        {"role": "assistant", "content": "reply"},
        {"role": "user", "content": "second"},
    ]
    assert _to_prompt(messages) == "user: first\nassistant: reply\nuser: second"
