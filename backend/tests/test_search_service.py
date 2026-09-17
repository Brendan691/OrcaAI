"""联网搜索 Provider 与降级语义测试。"""

import httpx
import pytest

from src.models.document import WebSearchResult
from src.services.search_service import (
    SearchGateway,
    SearchProviderError,
    TavilySearchAdapter,
)


class FailingAdapter:
    name = "primary"

    async def search(self, query: str, limit: int) -> list[WebSearchResult]:
        raise SearchProviderError("provider_timeout", "托管搜索超时")


class WorkingAdapter:
    name = "fallback"

    async def search(self, query: str, limit: int) -> list[WebSearchResult]:
        return [
            WebSearchResult(
                title="Result",
                url="https://example.com/result",
                snippet="Relevant snippet",
                provider=self.name,
            )
        ]


@pytest.mark.asyncio
async def test_gateway_reports_degraded_state_when_fallback_is_used():
    gateway = SearchGateway(primary=FailingAdapter(), fallback=WorkingAdapter())

    outcome = await gateway.search("shipping", limit=3)

    assert outcome.status == "degraded"
    assert outcome.provider == "fallback"
    assert len(outcome.results) == 1
    assert outcome.warnings[0].code == "provider_timeout"


@pytest.mark.asyncio
async def test_gateway_reports_failure_instead_of_fake_empty_results():
    gateway = SearchGateway(primary=FailingAdapter(), fallback=None)

    outcome = await gateway.search("shipping", limit=3)

    assert outcome.status == "failed"
    assert outcome.results == []
    assert outcome.warnings[0].message == "托管搜索超时"


@pytest.mark.asyncio
async def test_tavily_adapter_maps_hosted_response_to_search_results():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/search"
        return httpx.Response(
            200,
            json={
                "results": [
                    {
                        "title": "Maritime update",
                        "url": "https://example.com/maritime",
                        "content": "Latest shipping market update.",
                        "score": 0.88,
                        "published_date": "2026-07-30",
                    }
                ]
            },
        )

    adapter = TavilySearchAdapter(
        api_key="test-key",
        transport=httpx.MockTransport(handler),
    )

    results = await adapter.search("shipping market", limit=5)

    assert results == [
        WebSearchResult(
            title="Maritime update",
            url="https://example.com/maritime",
            snippet="Latest shipping market update.",
            provider="tavily",
            score=0.88,
            published_at="2026-07-30",
        )
    ]
