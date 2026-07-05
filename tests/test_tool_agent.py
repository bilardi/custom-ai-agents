"""Test the ToolAgentEngine."""

from unittest.mock import AsyncMock, MagicMock

from app.engine.tool_agent import ToolAgentEngine


async def test_handle_runs_agent_and_returns_final_output():
    agent = MagicMock()
    trace = MagicMock()
    trace.final_output = "AGENT ANSWER"
    agent.run_async = AsyncMock(return_value=trace)

    async def factory():
        return agent

    engine = ToolAgentEngine(agent_factory=factory)
    result = await engine.handle("what is dask?")
    assert "".join(result) == "AGENT ANSWER"
    agent.run_async.assert_awaited_once_with("what is dask?")
