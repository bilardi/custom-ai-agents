"""Test the Coder agent-as-tool."""

from unittest.mock import MagicMock

from app.agents.coder import Coder


def _agent(outputs):
    calls = {"n": 0}

    async def run_async(_prompt):
        i = calls["n"]
        calls["n"] += 1
        trace = MagicMock()
        trace.final_output = outputs[min(i, len(outputs) - 1)]
        return trace

    agent = MagicMock()
    agent.run_async = run_async
    agent.calls = calls
    return agent


def _factory(agent):
    async def factory():
        return agent

    return factory


async def test_write_code_returns_answer_when_valid():
    agent = _agent(["```python\nx = 1\n```"])
    coder = Coder(agent_factory=_factory(agent))
    out = await coder.write_code("add one", "ctx")
    assert "x = 1" in out
    assert agent.calls["n"] == 1


async def test_write_code_repairs_once_on_syntax_error():
    bad = "```python\ndef f(:\n    pass\n```"
    good = "```python\ndef f():\n    pass\n```"
    agent = _agent([bad, good])
    coder = Coder(agent_factory=_factory(agent))
    out = await coder.write_code("write f", "ctx")
    assert out == good
    assert agent.calls["n"] == 2


async def test_write_code_no_repair_when_no_code_blocks():
    agent = _agent(["just prose, no code here"])
    coder = Coder(agent_factory=_factory(agent))
    await coder.write_code("explain", "ctx")
    assert agent.calls["n"] == 1
