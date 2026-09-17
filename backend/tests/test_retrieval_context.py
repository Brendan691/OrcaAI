"""检索上下文与引用回溯测试。"""

from src.models.document import DocumentTags, SearchResult, WebSearchResult
from src.services.retrieval_context import RetrievalContext


def test_retrieval_context_builds_stable_local_and_web_citations():
    local = SearchResult(
        doc_id="doc-1",
        chunk_id="doc-1_chunk_2",
        chunk_index=2,
        title="港口运营报告",
        content="第二季度港口吞吐量同比增长。",
        url="/api/files/report.pdf/raw",
        source_type="file",
        start_idx=20,
        end_idx=35,
        line_start=3,
        line_end=4,
        score=0.91,
        tags=DocumentTags(),
    )
    web = WebSearchResult(
        title="IMO Latest News",
        url="https://www.imo.org/news",
        snippet="The IMO published a new circular.",
        provider="tavily",
        score=0.82,
    )

    context = RetrievalContext.build(local_results=[local], web_results=[web])

    assert len(context.citations) == 2
    assert context.citations[0].id.startswith("C1-")
    assert context.citations[0].id.endswith("-L3-4")
    assert context.citations[0].chunk_id == "doc-1_chunk_2"
    assert context.citations[0].locator_label == "第 3-4 行"
    assert context.citations[1].id.startswith("C2-")
    assert context.citations[1].source_type == "web"
    assert context.citations[1].provider == "tavily"
    assert context.citations[0].cite_marker in context.prompt
    assert context.citations[1].cite_marker in context.prompt


def test_fallback_answer_uses_exact_citation_markers():
    web = WebSearchResult(
        title="UNCTAD Shipping Update",
        url="https://unctad.org/shipping",
        snippet="Freight rates continued to change.",
        provider="tavily",
    )
    context = RetrievalContext.build(local_results=[], web_results=[web])

    answer = context.fallback_answer()

    assert context.citations[0].cite_marker in answer
    assert "Freight rates continued to change." in answer
