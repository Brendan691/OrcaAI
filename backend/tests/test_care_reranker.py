"""CARE cross-encoder reranking and fallback behavior."""

import pytest

from src.models.retrieval import SearchResult
from src.services.care_reranker import CareReranker


def result(doc_id: str, score: float) -> SearchResult:
    return SearchResult(
        doc_id=doc_id,
        title=doc_id,
        content=f"content for {doc_id}",
        score=score,
    )


@pytest.mark.asyncio
async def test_care_reranker_uses_cross_encoder_confidence():
    async def requester(query: str, documents: list[str]) -> list[dict]:
        assert query == "SOLAS requirements"
        assert len(documents) == 3
        return [
            {"index": 1, "relevance_score": 0.95},
            {"index": 0, "relevance_score": 0.40},
            {"index": 2, "relevance_score": 0.20},
        ]

    reranker = CareReranker(requester=requester, enabled=True)
    outcome = await reranker.rerank(
        "SOLAS requirements",
        [result("baseline-first", 0.90), result("gte-first", 0.89), result("third", 0.70)],
        top_k=2,
    )

    assert outcome.used is True
    assert outcome.weight > 0.9
    assert [item.doc_id for item in outcome.results] == ["gte-first", "baseline-first"]


@pytest.mark.asyncio
async def test_care_reranker_falls_back_on_invalid_response():
    async def requester(query: str, documents: list[str]) -> list[dict]:
        return [{"index": 0, "relevance_score": 1.0}]

    candidates = [result("first", 0.9), result("second", 0.8)]
    outcome = await CareReranker(requester=requester, enabled=True).rerank(
        "query",
        candidates,
        top_k=2,
    )

    assert outcome.used is False
    assert outcome.results == candidates
    assert outcome.warning.startswith("CARE rerank fallback")


def test_care_weight_trusts_larger_gte_margin():
    low_confidence = CareReranker.adaptive_weight(0.2, 0.01)
    high_confidence = CareReranker.adaptive_weight(0.01, 0.5)

    assert 0.4 <= low_confidence < high_confidence <= 1.0
