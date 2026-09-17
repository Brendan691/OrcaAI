"""可替换的联网搜索 Provider 与统一失败语义。"""

from typing import Protocol
from urllib.parse import quote

import httpx
from bs4 import BeautifulSoup

from ..core.config import settings
from ..models.document import SearchOutcome, SearchWarning, WebSearchResult


class SearchProviderError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


class SearchAdapter(Protocol):
    name: str

    async def search(self, query: str, limit: int) -> list[WebSearchResult]: ...


class TavilySearchAdapter:
    name = "tavily"

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.tavily.com",
        transport: httpx.AsyncBaseTransport | None = None,
    ):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.transport = transport

    async def search(self, query: str, limit: int) -> list[WebSearchResult]:
        if not self.api_key:
            raise SearchProviderError("missing_api_key", "未配置 TAVILY_API_KEY")
        try:
            async with httpx.AsyncClient(
                base_url=self.base_url,
                timeout=settings.WEB_SEARCH_TIMEOUT,
                transport=self.transport,
            ) as client:
                response = await client.post(
                    "/search",
                    json={
                        "api_key": self.api_key,
                        "query": query,
                        "topic": "general",
                        "search_depth": "advanced",
                        "max_results": limit,
                        "include_answer": False,
                        "include_raw_content": False,
                    },
                )
                response.raise_for_status()
                payload = response.json()
        except httpx.TimeoutException as exc:
            raise SearchProviderError("provider_timeout", "Tavily 搜索超时") from exc
        except (httpx.HTTPError, ValueError) as exc:
            raise SearchProviderError("provider_error", f"Tavily 搜索失败: {exc}") from exc

        return [
            WebSearchResult(
                title=item.get("title", "").strip(),
                url=item.get("url", "").strip(),
                snippet=item.get("content", "").strip()[:1000],
                provider=self.name,
                score=item.get("score"),
                published_at=item.get("published_date"),
            )
            for item in payload.get("results", [])[:limit]
            if item.get("title") and item.get("url")
        ]


class BingHtmlSearchAdapter:
    name = "bing"

    async def search(self, query: str, limit: int) -> list[WebSearchResult]:
        url = f"https://cn.bing.com/search?q={quote(query.strip())}&count={max(limit * 3, 10)}"
        try:
            async with httpx.AsyncClient(timeout=settings.WEB_SEARCH_TIMEOUT) as client:
                response = await client.get(
                    url,
                    headers={
                        "User-Agent": "Mozilla/5.0 AppleWebKit/537.36 Chrome/120 Safari/537.36",
                        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.7",
                    },
                    follow_redirects=True,
                )
                response.raise_for_status()
        except httpx.TimeoutException as exc:
            raise SearchProviderError("fallback_timeout", "Bing 降级搜索超时") from exc
        except httpx.HTTPError as exc:
            raise SearchProviderError("fallback_error", f"Bing 降级搜索失败: {exc}") from exc

        soup = BeautifulSoup(response.text, "html.parser")
        results: list[WebSearchResult] = []
        for block in soup.select("li.b_algo"):
            link = block.select_one("h2 a") or block.select_one("a[href]")
            if not link or not link.get("href"):
                continue
            title = link.get_text(" ", strip=True)
            snippet_node = block.select_one("p")
            snippet = snippet_node.get_text(" ", strip=True) if snippet_node else ""
            if title:
                results.append(
                    WebSearchResult(
                        title=title[:200],
                        url=str(link["href"]),
                        snippet=snippet[:1000],
                        provider=self.name,
                    )
                )
            if len(results) >= limit:
                break
        if not results:
            raise SearchProviderError("fallback_parse_error", "Bing 返回内容无法解析")
        return results


class SearchGateway:
    def __init__(self, primary: SearchAdapter, fallback: SearchAdapter | None = None):
        self.primary = primary
        self.fallback = fallback

    async def search(self, query: str, limit: int = 5) -> SearchOutcome:
        warnings: list[SearchWarning] = []
        try:
            results = await self.primary.search(query, limit)
            if results:
                return SearchOutcome(status="ok", provider=self.primary.name, results=results)
            warnings.append(
                SearchWarning(
                    code="empty_results",
                    message=f"{self.primary.name} 未返回结果",
                    provider=self.primary.name,
                )
            )
        except SearchProviderError as exc:
            warnings.append(
                SearchWarning(code=exc.code, message=exc.message, provider=self.primary.name)
            )

        if self.fallback is not None:
            try:
                results = await self.fallback.search(query, limit)
                if results:
                    return SearchOutcome(
                        status="degraded",
                        provider=self.fallback.name,
                        results=results,
                        warnings=warnings,
                    )
            except SearchProviderError as exc:
                warnings.append(
                    SearchWarning(code=exc.code, message=exc.message, provider=self.fallback.name)
                )

        return SearchOutcome(status="failed", warnings=warnings)


search_service = SearchGateway(
    primary=TavilySearchAdapter(
        api_key=settings.TAVILY_API_KEY,
        base_url=settings.TAVILY_BASE_URL,
    ),
    fallback=BingHtmlSearchAdapter() if settings.WEB_SEARCH_FALLBACK else None,
)
