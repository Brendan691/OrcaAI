"""Candidate diversity policy tests."""

from src.services.candidate_policy import (
    MAX_CHUNKS_PER_DOCUMENT,
    diversify_candidates,
    interleave_source_candidates,
)


def item(doc_id: str, rank: int) -> dict:
    return {"doc_id": doc_id, "rank": rank}


def test_one_document_cannot_monopolize_candidate_pool():
    candidates = [item("old", rank) for rank in range(20)]
    candidates.extend(item("new", rank) for rank in range(20, 24))
    candidates.extend(item("other1", rank) for rank in range(24, 28))
    candidates.extend(item("other2", rank) for rank in range(28, 32))

    selected = diversify_candidates(
        candidates,
        10,
        document_key=lambda row: row["doc_id"],
    )

    assert [row["doc_id"] for row in selected].count("old") == MAX_CHUNKS_PER_DOCUMENT
    assert any(row["doc_id"] == "new" for row in selected)
    assert len(selected) == 10


def test_overflow_is_used_only_when_not_enough_documents_exist():
    candidates = [item("only", rank) for rank in range(8)]

    selected = diversify_candidates(
        candidates,
        5,
        document_key=lambda row: row["doc_id"],
    )

    assert [row["rank"] for row in selected] == [0, 1, 2, 3, 4]


def test_candidate_limit_and_ordering_are_preserved():
    candidates = [
        item("a", 0),
        item("a", 1),
        item("a", 2),
        item("b", 3),
        item("a", 4),
    ]

    selected = diversify_candidates(
        candidates,
        3,
        document_key=lambda row: row["doc_id"],
    )

    assert [(row["doc_id"], row["rank"]) for row in selected] == [
        ("a", 0),
        ("a", 1),
        ("a", 2),
    ]


def test_dual_source_candidates_keep_both_sources_before_rerank():
    local = [item("local", rank) for rank in range(12)]
    web = [item("web", rank) for rank in range(12)]

    merged = interleave_source_candidates(local, web)

    assert len(merged) == 20
    assert [row.source for row in merged[:4]] == ["local", "web", "local", "web"]
    assert merged[18].source == "local"
    assert merged[19].source == "web"
