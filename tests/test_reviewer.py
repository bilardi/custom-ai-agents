"""Test the Reviewer agent."""

from unittest.mock import MagicMock

from app.agents.reviewer import Reviewer


def _agent(output):
    async def run_async(_prompt):
        trace = MagicMock()
        trace.final_output = output
        return trace

    agent = MagicMock()
    agent.run_async = run_async
    return agent


def _factory(agent):
    async def factory():
        return agent

    return factory


async def test_review_returns_empty_when_ok():
    reviewer = Reviewer(agent_factory=_factory(_agent("  OK  ")))
    assert await reviewer.review("task", "code", "ctx") == ""


async def test_review_returns_critique_when_issues():
    reviewer = Reviewer(agent_factory=_factory(_agent("the API x.foo does not exist in the docs")))
    assert await reviewer.review("task", "code") == "the API x.foo does not exist in the docs"
