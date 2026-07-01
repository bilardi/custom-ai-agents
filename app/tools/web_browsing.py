"""Web browsing tools: search the web and read a page as markdown."""

import re
from collections.abc import Callable
from typing import Any, Protocol

import requests
from duckduckgo_search import DDGS
from markdownify import markdownify
from requests.exceptions import RequestException


class _Fetcher(Protocol):
    def get(self, url: str, *, timeout: int) -> requests.Response: ...


class WebBrowser:
    """Live web actions: search the web and read a page as markdown."""

    def __init__(
        self,
        timeout: int = 30,
        max_length: int = 10000,
        max_results: int = 10,
        session: _Fetcher | None = None,
        ddgs_factory: Callable[[], Any] = DDGS,
    ) -> None:
        """Build a browser with request defaults and injectable clients."""
        self.timeout = timeout
        self.max_length = max_length
        self.max_results = max_results
        self.session: _Fetcher = session or requests.Session()
        self.ddgs_factory = ddgs_factory

    def search_web(self, query: str) -> str:
        """Perform a duckduckgo web search and return the top results.

        Args:
            query: The search query to perform.

        Returns:
            The top search results as markdown links.

        """
        ddgs = self.ddgs_factory()
        results = ddgs.text(query, max_results=self.max_results)
        return "\n".join(
            f"[{result['title']}]({result['href']})\n{result['body']}" for result in results
        )

    def visit_webpage(self, url: str) -> str:
        """Visit a webpage and read its content as a markdown string.

        Args:
            url: The url of the webpage to visit.

        Returns:
            The page content as markdown, or an error message on failure.

        """
        try:
            response = self.session.get(url, timeout=self.timeout)
            response.raise_for_status()

            markdown_content = markdownify(response.text).strip()
            markdown_content = re.sub(r"\n{2,}", "\n", markdown_content)

            if self.max_length == -1:
                return markdown_content
            return self._truncate_content(markdown_content, self.max_length)
        except RequestException as e:
            return f"Error fetching the webpage: {e!s}"
        except Exception as e:  # noqa: BLE001
            return f"An unexpected error occurred: {e!s}"

    @staticmethod
    def _truncate_content(content: str, max_length: int) -> str:
        if len(content) <= max_length:
            return content
        return (
            content[: max_length // 2]
            + f"\n..._This content has been truncated to stay below {max_length} characters_...\n"
            + content[-max_length // 2 :]
        )
