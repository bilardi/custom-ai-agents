"""Test the coder's snippet checks."""

from app.agents.coder.code_validator import check_code, extract_code_blocks


def test_extract_code_blocks_returns_fenced_python_blocks():
    text = "intro\n```python\nx = 1\n```\nmid\n```python\ny = 2\n```\nend"
    assert extract_code_blocks(text) == ["x = 1", "y = 2"]


def test_extract_code_blocks_returns_empty_when_no_blocks():
    assert extract_code_blocks("just prose, no code") == []


def test_check_code_accepts_valid_syntax():
    report = check_code("x = 1\ny = x + 1")
    assert report.valid
    assert report.kind is None


def test_check_code_rejects_syntax_error():
    report = check_code("def f(:\n    pass")
    assert not report.valid
    assert report.kind == "syntax"
    assert report.issues


def test_check_code_ignores_undefined_names_in_snippet():
    # dd/ddf are undefined in the snippet (F821) but expected in an illustrative example
    report = check_code('ddf = dd.read_csv("x.csv")\nddf.groupby("a").b.mean().compute()')
    assert report.valid


def test_check_code_flags_lint_signal():
    # f-string without placeholders (F541) is a real snippet-safe lint signal
    report = check_code('x = f"no placeholder here"')
    assert not report.valid
    assert report.kind == "lint"
    assert report.issues
