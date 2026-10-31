"""联网搜索 Provider 与降级语义测试。"""

import httpx
import pytest

from src.models.document import WebSearchResult
from src.services.search_service import (
    SearchGateway,
    SearchProviderError,
    TavilySearchAdapter,
)
from src.services.query_intent import QueryIntentAnalyzer


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


@pytest.mark.asyncio
async def test_multi_query_search_preserves_traces_and_deduplicates_urls():
    class VariantAdapter:
        name = "variant"

        async def search(self, query: str, limit: int) -> list[WebSearchResult]:
            if query.endswith("最新年度报告"):
                return [
                    WebSearchResult(
                        title="2024 annual report",
                        url="https://example.com/report?utm=1",
                        snippet="4.9 percent risk",
                        provider="variant",
                        score=0.9,
                    ),
                    WebSearchResult(
                        title="Duplicate",
                        url="https://example.com/old#section",
                        snippet="duplicate",
                        provider="variant",
                        score=0.5,
                    ),
                ]
            return [
                WebSearchResult(
                    title="Old study",
                    url="https://example.com/old",
                    snippet="old conclusion",
                    provider="variant",
                    score=0.8,
                )
            ]

    intent = QueryIntentAnalyzer().analyze(
        "中国海员心理健康水平是否明显低于常人？",
        current_year=2026,
    )
    outcome = await SearchGateway(primary=VariantAdapter()).search_variants(
        intent.variants,
        limit=10,
    )

    assert outcome.status == "ok"
    assert outcome.query_variants == list(intent.web_queries)
    assert [trace.result_count for trace in outcome.variant_traces] == [1, 1, 2]
    assert {item.url for item in outcome.results} == {
        "https://example.com/old",
        "https://example.com/report?utm=1",
    }
    report = next(item for item in outcome.results if "annual" in item.title)
    assert report.variant_rule == "neutral-recency"
    assert report.variant_rank == 1
    assert outcome.results.index(report) < 4
