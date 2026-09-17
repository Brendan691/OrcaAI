"""置信度感知的双源证据校正测试。"""

from src.models.document import DocumentTags, SearchResult, WebSearchResult
from src.services.evidence_selector import EvidenceSelector


def local(doc_id: str, score: float, url: str = "") -> SearchResult:
    return SearchResult(
        doc_id=doc_id,
        chunk_id=f"{doc_id}-{score}",
        title=f"Local {doc_id}",
        content=f"Evidence {doc_id} {score}",
        url=url,
        score=score,
        tags=DocumentTags(),
    )


def web(index: int, url: str = "") -> WebSearchResult:
    return WebSearchResult(
        title=f"Web {index}",
        url=url or f"https://example.com/{index}",
        snippet=f"Web evidence {index}",
        provider="tavily",
        score=1.0 - index / 100,
    )


def test_low_local_confidence_allocates_more_budget_to_web():
    selector = EvidenceSelector(budget=8)
    selection = selector.select(
        local_results=[local(str(index), 0.3) for index in range(6)],
        web_results=[web(index) for index in range(6)],
        retrieval_confidence=0.2,
    )

    assert selection.local_quota == 2
    assert selection.web_quota == 6


def test_high_local_confidence_preserves_more_local_evidence():
    selector = EvidenceSelector(budget=8)
    selection = selector.select(
        local_results=[local(str(index), 0.9) for index in range(6)],
        web_results=[web(index) for index in range(6)],
        retrieval_confidence=0.9,
    )

    assert selection.local_quota == 5
    assert selection.web_quota == 3


def test_cross_source_duplicate_url_prefers_local_locator():
    selector = EvidenceSelector()
    shared = "https://example.com/report?tracking=1"
    selection = selector.select(
        local_results=[local("report", 0.9, shared)],
        web_results=[web(1, "https://example.com/report#section")],
        retrieval_confidence=0.9,
    )

    assert selection.duplicates_removed == 1
    assert selection.web_results == []
    assert selection.local_results[0].doc_id == "report"


def test_limits_adjacent_chunks_from_one_document():
    selector = EvidenceSelector(budget=5, max_chunks_per_document=2)
    selection = selector.select(
        local_results=[local("same", 0.9), local("same", 0.8), local("same", 0.7), local("other", 0.6)],
        web_results=[],
        retrieval_confidence=0.9,
    )

    assert [item.doc_id for item in selection.local_results] == ["same", "same", "other"]
