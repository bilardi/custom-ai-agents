"""Fixtures for the benchmark tests (opt-in, need a running Ollama)."""

import os
from collections.abc import Callable

import pytest

from scripts.benchmark.helpers import installed_models, ollama_reachable


@pytest.fixture
def ollama_url() -> str:
    return os.getenv("OLLAMA_URL", "http://localhost:11434")


@pytest.fixture
def bench_runs() -> int:
    return int(os.getenv("BENCH_RUNS", "5"))


@pytest.fixture(autouse=True)
def _require_ollama(ollama_url: str) -> None:
    if not ollama_reachable(ollama_url):
        pytest.skip(f"Ollama not reachable at {ollama_url}")


@pytest.fixture
def require_model(ollama_url: str) -> Callable[[str], None]:
    installed = installed_models(ollama_url)

    def _require(model: str) -> None:
        if model not in installed:
            pytest.skip(f"model {model!r} not installed on {ollama_url}")

    return _require
