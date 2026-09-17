"""置信度感知的本地/Web证据校正与预算分配。"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from urllib.parse import urlsplit, urlunsplit

from ..models.document import SearchResult, WebSearchResult


@dataclass(frozen=True)
class EvidenceSelection:
    local_results: list[SearchResult]
    web_results: list[WebSearchResult]
    local_quota: int
    web_quota: int
    duplicates_removed: int


class EvidenceSelector:
    def __init__(self, budget: int = 8, max_chunks_per_document: int = 2):
        self.budget = budget
        self.max_chunks_per_document = max_chunks_per_document

    def select(
        self,
        *,
        local_results: list[SearchResult],
        web_results: list[WebSearchResult],
        retrieval_confidence: float,
    ) -> EvidenceSelection:
        local = self._limit_local_repetition(local_results)
        web, duplicates_removed = self._deduplicate_web(local, web_results)

        if not web:
            return EvidenceSelection(
                local_results=local[: self.budget],
                web_results=[],
                local_quota=min(len(local), self.budget),
                web_quota=0,
                duplicates_removed=duplicates_removed,
            )
        if not local:
            return EvidenceSelection(
                local_results=[],
                web_results=web[: self.budget],
                local_quota=0,
                web_quota=min(len(web), self.budget),
                duplicates_removed=duplicates_removed,
            )

        if retrieval_confidence >= 0.75:
            requested_local = min(5, self.budget - 1)
        elif retrieval_confidence >= 0.45:
            requested_local = min(4, self.budget - 1)
        else:
            requested_local = min(2, self.budget - 1)

        selected_local = local[:requested_local]
        selected_web = web[: self.budget - len(selected_local)]
        if len(selected_local) + len(selected_web) < self.budget:
            selected_local = local[: self.budget - len(selected_web)]

        return EvidenceSelection(
            local_results=selected_local,
            web_results=selected_web,
            local_quota=len(selected_local),
            web_quota=len(selected_web),
            duplicates_removed=duplicates_removed,
        )

    def _limit_local_repetition(self, results: list[SearchResult]) -> list[SearchResult]:
        counts: dict[str, int] = {}
        selected = []
        for result in results:
            identity = result.doc_id or result.url or result.title
            if counts.get(identity, 0) >= self.max_chunks_per_document:
                continue
            counts[identity] = counts.get(identity, 0) + 1
            selected.append(result)
        return selected

    def _deduplicate_web(
        self,
        local_results: list[SearchResult],
        web_results: list[WebSearchResult],
    ) -> tuple[list[WebSearchResult], int]:
        seen_urls = {self._canonical_url(item.url) for item in local_results if item.url}
        seen_text = {self._text_key(item.title, item.content) for item in local_results}
        selected = []
        removed = 0
        for result in web_results:
            url_key = self._canonical_url(result.url)
            text_key = self._text_key(result.title, result.snippet)
            if (url_key and url_key in seen_urls) or (text_key and text_key in seen_text):
                removed += 1
                continue
            if url_key:
                seen_urls.add(url_key)
            if text_key:
                seen_text.add(text_key)
            selected.append(result)
        return selected, removed

    @staticmethod
    def _canonical_url(value: str) -> str:
        if not value:
            return ""
        parts = urlsplit(value)
        path = parts.path.rstrip("/") or "/"
        return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), path, "", ""))

    @staticmethod
    def _text_key(title: str, text: str) -> str:
        normalized = unicodedata.normalize("NFKC", f"{title} {text}").lower()
        tokens = re.findall(r"[a-z0-9]+|[一-鿿]", normalized)
        return " ".join(tokens[:32])


evidence_selector = EvidenceSelector()
