"""Test the Coder agent-as-tool."""

from unittest.mock import MagicMock

from app.agents.coder import Coder
from app.trace import start_trace


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


async def test_write_code_ignores_unexpected_tool_kwargs():
    # ToolBench-tuned local models (e.g. qwen2.5) inject spurious args like this one
    agent = _agent(["```python\nx = 1\n```"])
    coder = Coder(agent_factory=_factory(agent))
    out = await coder.write_code("t", "ctx", toolbench_rapidapi_key="")
    assert "x = 1" in out


class _Reviewer:
    def __init__(self, verdicts):
        self._verdicts = verdicts
        self.calls = 0

    async def review(self, task, code, context=""):
        verdict = self._verdicts[min(self.calls, len(self._verdicts) - 1)]
        self.calls += 1
        return verdict


async def test_write_code_revises_when_reviewer_flags():
    # both answers are syntactically valid; the reviewer flags the first, then approves
    agent = _agent(["```python\nx = 1\n```", "```python\nx = 2\n```"])
    reviewer = _Reviewer(["not grounded in the docs", ""])
    coder = Coder(agent_factory=_factory(agent), reviewer=reviewer)
    await coder.write_code("t", "ctx")
    assert agent.calls["n"] == 2
    assert reviewer.calls == 1


async def test_write_code_no_revise_when_valid_and_reviewer_ok():
    agent = _agent(["```python\nx = 1\n```"])
    reviewer = _Reviewer([""])
    coder = Coder(agent_factory=_factory(agent), reviewer=reviewer)
    await coder.write_code("t", "ctx")
    assert agent.calls["n"] == 1
    assert reviewer.calls == 1


def _drain(queue):
    lines = []
    while not queue.empty():
        lines.append(queue.get_nowait())
    return lines


async def test_write_code_traces_reviewing_and_revising():
    queue = start_trace()
    agent = _agent(["```python\nx = 1\n```", "```python\nx = 2\n```"])
    reviewer = _Reviewer(["fix it", ""])
    coder = Coder(agent_factory=_factory(agent), reviewer=reviewer)
    await coder.write_code("t", "ctx")
    lines = _drain(queue)
    assert "> reviewing code...\n\n" in lines
    assert "> revising code...\n\n" in lines


async def test_write_code_traces_reviewing_without_revising_when_ok():
    queue = start_trace()
    agent = _agent(["```python\nx = 1\n```"])
    reviewer = _Reviewer([""])
    coder = Coder(agent_factory=_factory(agent), reviewer=reviewer)
    await coder.write_code("t", "ctx")
    lines = _drain(queue)
    assert "> reviewing code...\n\n" in lines
    assert "> revising code...\n\n" not in lines
