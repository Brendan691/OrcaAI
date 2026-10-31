"""Shared candidate-pool limits and document-diversity selection."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Callable, Literal, Sequence, TypeVar


T = TypeVar("T")

LOCAL_CANDIDATE_LIMIT = 10
WEB_CANDIDATE_LIMIT = 10
FINAL_EVIDENCE_LIMIT = 5
MAX_CHUNKS_PER_DOCUMENT = 3
LOCAL_POOL_MULTIPLIER = 3
LOCAL_EVIDENCE_MAX_CHARS = 1800
WEB_EVIDENCE_MAX_CHARS = 5000
POLICY_VERSION = "candidate-policy-20261021-v1"


def diversify_candidates(
    candidates: Sequence[T],
    limit: int,
    *,
    document_key: Callable[[T], str],
    per_document_limit: int = MAX_CHUNKS_PER_DOCUMENT,
) -> list[T]:
    """Select candidates with a per-document cap, then relax only if needed."""
    if limit <= 0:
        return []
    selected: list[T] = []
    overflow: list[T] = []
    counts: Counter[str] = Counter()
    for candidate in candidates:
        key = document_key(candidate)
        if counts[key] < per_document_limit:
            selected.append(candidate)
            counts[key] += 1
            if len(selected) >= limit:
                return selected[:limit]
        else:
            overflow.append(candidate)
    if len(selected) < limit:
        selected.extend(overflow[: limit - len(selected)])
    return selected[:limit]


def candidate_policy_snapshot() -> dict[str, int | str]:
    """Expose the active policy for experiment manifests and diagnostics."""
    return {
        "version": POLICY_VERSION,
        "local_candidate_limit": LOCAL_CANDIDATE_LIMIT,
        "web_candidate_limit": WEB_CANDIDATE_LIMIT,
        "final_evidence_limit": FINAL_EVIDENCE_LIMIT,
        "max_chunks_per_document": MAX_CHUNKS_PER_DOCUMENT,
        "local_pool_multiplier": LOCAL_POOL_MULTIPLIER,
        "local_evidence_max_chars": LOCAL_EVIDENCE_MAX_CHARS,
        "web_evidence_max_chars": WEB_EVIDENCE_MAX_CHARS,
    }


@dataclass(frozen=True)
class SourceCandidate:
    source: Literal["local", "web"]
    item: T


def interleave_source_candidates(
    local: Sequence[T],
    web: Sequence[T],
    *,
    local_limit: int = LOCAL_CANDIDATE_LIMIT,
    web_limit: int = WEB_CANDIDATE_LIMIT,
) -> list[SourceCandidate[T]]:
    """Keep both sources visible before unified reranking."""
    local_items = list(local[:local_limit])
    web_items = list(web[:web_limit])
    merged: list[SourceCandidate[T]] = []
    for index in range(max(len(local_items), len(web_items))):
        if index < len(local_items):
            merged.append(SourceCandidate("local", local_items[index]))
        if index < len(web_items):
            merged.append(SourceCandidate("web", web_items[index]))
    return merged
