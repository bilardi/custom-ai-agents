"""Test the ToolAgentEngine."""

from unittest.mock import MagicMock

from app.engine.tool_agent import ToolAgentEngine, ToolTraceCallback, _describe_tool


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


async def test_handle_runs_agent_and_returns_final_output():
    agent = _agent("AGENT ANSWER")
    engine = ToolAgentEngine(agent_factory=_factory(agent))
    result = await engine.handle("what is dask?")
    assert "".join([chunk async for chunk in result]) == "AGENT ANSWER"


async def test_handle_without_trace_ignores_tool_events():
    cb = ToolTraceCallback()

    def on_run(_message):
        cb.before_tool_execution(MagicMock(), {"name": "list_topics", "arguments": {}})

    agent = _agent("ANSWER", on_run=on_run)
    engine = ToolAgentEngine(agent_factory=_factory(agent), show_trace=False)
    result = await engine.handle("q")
    assert [chunk async for chunk in result] == ["ANSWER"]


async def test_handle_streams_tool_trace_before_final_output():
    cb = ToolTraceCallback()

    def on_run(_message):
        cb.before_tool_execution(MagicMock(), {"name": "list_topics", "arguments": {}})
        cb.before_tool_execution(MagicMock(), {"name": "retrieve", "arguments": {"topic": "dask"}})

    agent = _agent("ANSWER", on_run=on_run)
    engine = ToolAgentEngine(agent_factory=_factory(agent), show_trace=True)
    result = await engine.handle("q")
    chunks = [chunk async for chunk in result]
    assert chunks == [
        "> checking indexed topics...\n\n",
        "> reading local docs on 'dask'...\n\n",
        "ANSWER",
    ]
