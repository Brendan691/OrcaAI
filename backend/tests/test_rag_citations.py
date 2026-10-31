"""RAG 问答必须返回与回答角标绑定的来源。"""

import pytest

from src.models.document import ChatRequest, SearchOutcome, WebSearchResult
from src.services.rag_service import RAGService


class FakeEmbedding:
    def embed_text(self, text: str) -> list[float]:
        return [1.0, 0.0]


class EmptyKnowledgeBase:
    def search(self, **kwargs) -> list[dict]:
        return []


class HostedSearch:
    async def search(self, query: str, limit: int = 5) -> SearchOutcome:
        return SearchOutcome(
            status="ok",
            provider="tavily",
            results=[
                WebSearchResult(
                    title="Shipping market",
                    url="https://example.com/shipping",
                    snippet="Container rates increased this week.",
                    provider="tavily",
                )
            ],
        )


class VariantSearch:
    def __init__(self):
        self.variants = []

    async def search_variants(self, variants, limit: int = 5) -> SearchOutcome:
        self.variants = [variant.rule for variant in variants]
        return SearchOutcome(
            status="ok",
            provider="tavily",
            query_variants=[variant.text for variant in variants],
            results=[
                WebSearchResult(
                    title="2024 annual report",
                    url="https://example.com/report",
                    snippet="4.9 percent risk and 0.4 percent abnormal.",
                    provider="tavily",
                    variant_rule="neutral-recency",
                    variant_rank=2,
                )
            ],
        )


@pytest.mark.asyncio
async def test_web_only_chat_returns_clickable_citation_without_llm():
    service = RAGService(
        embedding=FakeEmbedding(),
        knowledge_base=EmptyKnowledgeBase(),
        web_search=HostedSearch(),
        llm_enabled=False,
    )

    response = await service.chat(
        ChatRequest(message="本周集装箱运价如何", search_internet=True)
    )

    assert len(response.sources) == 1
    assert response.sources[0].source_type == "web"
    assert response.sources[0].url == "https://example.com/shipping"
    assert response.sources[0].cite_marker in response.answer
    assert response.search_status == "ok"


@pytest.mark.asyncio
async def test_chat_does_not_search_web_when_toggle_is_disabled():
    class UnexpectedSearch:
        async def search(self, query: str, limit: int = 5) -> SearchOutcome:
            raise AssertionError("web search should not run")

    service = RAGService(
        embedding=FakeEmbedding(),
        knowledge_base=EmptyKnowledgeBase(),
        web_search=UnexpectedSearch(),
        llm_enabled=False,
    )

    response = await service.chat(ChatRequest(message="没有联网"))

    assert response.sources == []
    assert response.search_status == "disabled"


@pytest.mark.asyncio
async def test_web_only_chat_uses_audited_query_variants():
    web = VariantSearch()
    service = RAGService(
        embedding=FakeEmbedding(),
        knowledge_base=EmptyKnowledgeBase(),
        web_search=web,
        llm_enabled=False,
    )

    response = await service.chat(
        ChatRequest(
            message="中国海员心理健康水平是否明显低于常人？",
            search_internet=True,
        )
    )

    assert web.variants == ["original", "maritime-synonym", "neutral-recency"]
    assert response.sources[0].url == "https://example.com/report"
    assert response.search_status == "ok"
