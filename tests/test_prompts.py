"""Test the prompt loader."""

from app.prompts import load_prompt


def test_load_prompt_reads_markdown_file(tmp_path):
    (tmp_path / "greeting.md").write_text("Use {context} for {question}\n", encoding="utf-8")
    assert load_prompt("greeting", base=tmp_path) == "Use {context} for {question}"


def test_load_prompt_strips_surrounding_whitespace(tmp_path):
    (tmp_path / "agent.md").write_text("\n  instructions  \n", encoding="utf-8")
    assert load_prompt("agent", base=tmp_path) == "instructions"
