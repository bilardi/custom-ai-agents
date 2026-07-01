"""Test the WebBrowser tools."""

from unittest.mock import MagicMock

from requests.exceptions import RequestException

from app.tools.web_browsing import WebBrowser


def test_truncate_content_keeps_short_content_unchanged():
    """Content shorter than the limit is returned as is."""
    text = "short content"
    assert WebBrowser._truncate_content(text, 100) == text


def test_truncate_content_truncates_long_content():
    """Content longer than the limit is cut and marked as truncated."""
    text = "a" * 200
    result = WebBrowser._truncate_content(text, 20)
    assert "truncated" in result
    assert result.startswith("a")
    assert result.endswith("a")


def test_search_web_formats_results_as_markdown_links():
    """Each result is rendered as a markdown link followed by its body."""
    fake_ddgs = MagicMock()
    fake_ddgs.text.return_value = [
        {"title": "First", "href": "http://a", "body": "Body A"},
        {"title": "Second", "href": "http://b", "body": "Body B"},
    ]
    browser = WebBrowser(ddgs_factory=lambda: fake_ddgs)
    output = browser.search_web("query")
    assert "[First](http://a)\nBody A" in output
    assert "[Second](http://b)\nBody B" in output


def test_search_web_uses_configured_max_results():
    """The configured max_results is forwarded to the search."""
    fake_ddgs = MagicMock()
    fake_ddgs.text.return_value = []
    browser = WebBrowser(max_results=3, ddgs_factory=lambda: fake_ddgs)
    browser.search_web("query")
    fake_ddgs.text.assert_called_once_with("query", max_results=3)


def test_visit_webpage_returns_markdown_text():
    """The page HTML is converted to markdown text."""
    response = MagicMock()
    response.text = "<h1>Title</h1><p>Paragraph</p>"
    fake_session = MagicMock()
    fake_session.get.return_value = response
    browser = WebBrowser(session=fake_session)
    output = browser.visit_webpage("http://example.com")
    assert "Title" in output
    assert "Paragraph" in output


def test_visit_webpage_returns_error_message_on_request_failure():
    """A request error is reported as a readable message, not an exception."""
    fake_session = MagicMock()
    fake_session.get.side_effect = RequestException("boom")
    browser = WebBrowser(session=fake_session)
    output = browser.visit_webpage("http://example.com")
    assert "Error fetching the webpage" in output
