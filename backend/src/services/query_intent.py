"""Deterministic maritime query intent analysis shared by API and experiments."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from typing import Iterable


VERSION = "maritime-query-intent-20261021-v1"

SYNONYM_GROUPS: tuple[tuple[str, ...], ...] = (
    ("海员", "船员"),
)

EXPLICIT_FRESHNESS = re.compile(
    r"最新|当前|目前|现在|近期|今年|本年度|截至|现行|现行有效|进展|趋势|"
    r"执行情况|实施情况|落地情况|"
    r"latest|current|recent|today|newest",
    re.IGNORECASE,
)
STATE_QUESTION = re.compile(
    r"是否|是否已经|有没有|能否|会不会|"
    r"(?:低于|高于|超过|纳入|生效|适用|覆盖|达到|满足|需要|存在|属于)"
)
HISTORICAL_YEAR = re.compile(r"(?<!\d)(20\d{2})(?!\d)")


@dataclass(frozen=True)
class QueryVariant:
    text: str
    rule: str
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class QueryIntent:
    original: str
    normalized: str
    freshness_intent: str
    temporal_scope: str
    conflict_sensitive: bool
    synonyms_applied: tuple[tuple[str, str], ...]
    variants: tuple[QueryVariant, ...]
    version: str = VERSION

    @property
    def web_queries(self) -> tuple[str, ...]:
        return tuple(variant.text for variant in self.variants)


def _replace_terms(text: str, terms: Iterable[str], canonical: str) -> tuple[str, list[tuple[str, str]]]:
    normalized = text
    applied: list[tuple[str, str]] = []
    for term in terms:
        if term == canonical or term not in normalized:
            continue
        normalized = normalized.replace(term, canonical)
        applied.append((term, canonical))
    return normalized, applied


def _freshness_state(text: str, current_year: int) -> tuple[str, str]:
    if EXPLICIT_FRESHNESS.search(text):
        return "explicit", "current"
    years = [int(value) for value in HISTORICAL_YEAR.findall(text)]
    if years and all(year <= current_year - 3 for year in years):
        return "none", "historical"
    if STATE_QUESTION.search(text):
        return "implicit", "current"
    return "none", "timeless"


class QueryIntentAnalyzer:
    """Analyze a query without external services or hidden per-query tables."""

    def __init__(
        self,
        synonym_groups: tuple[tuple[str, ...], ...] = SYNONYM_GROUPS,
        version: str = VERSION,
    ):
        self.synonym_groups = synonym_groups
        self.version = version

    def analyze(self, query: str, *, current_year: int | None = None) -> QueryIntent:
        original = query.strip()
        if not original:
            raise ValueError("query must not be empty")
        year = current_year or date.today().year

        normalized, applied = self._normalize_synonyms(original)

        freshness, temporal_scope = _freshness_state(original, year)
        conflict_sensitive = freshness != "none" and temporal_scope == "current"
        reasons = (f"freshness:{freshness}", f"scope:{temporal_scope}")
        variants = [
            QueryVariant(
                text=original,
                rule="original",
                reasons=("preserve-user-query",),
            )
        ]
        variant_texts = {original}
        if normalized != original and normalized not in variant_texts:
            variants.append(
                QueryVariant(
                    text=normalized,
                    rule="maritime-synonym",
                    reasons=tuple(f"{source}->{canonical}" for source, canonical in applied),
                )
            )
            variant_texts.add(normalized)

        if conflict_sensitive:
            recency_query = f"{normalized} 最新年度报告"
            if recency_query not in variant_texts:
                variants.append(
                    QueryVariant(
                        text=recency_query,
                        rule="neutral-recency",
                        reasons=reasons,
                    )
                )

        return QueryIntent(
            original=original,
            normalized=normalized,
            freshness_intent=freshness,
            temporal_scope=temporal_scope,
            conflict_sensitive=conflict_sensitive,
            synonyms_applied=tuple(applied),
            variants=tuple(variants),
            version=self.version,
        )

    def equivalent_terms(self, term: str) -> tuple[str, ...]:
        for group in self.synonym_groups:
            if term in group:
                return group
        return (term,)

    def synonym_variants(self, text: str) -> tuple[str, ...]:
        """Return the original phrase and its canonical maritime synonym form."""
        normalized, _ = self._normalize_synonyms(text)
        return tuple(dict.fromkeys((text, normalized)))

    def _normalize_synonyms(self, text: str) -> tuple[str, list[tuple[str, str]]]:
        normalized = text
        applied: list[tuple[str, str]] = []
        for group in self.synonym_groups:
            canonical = group[-1]
            changed, changes = _replace_terms(normalized, group[:-1], canonical)
            normalized = changed
            applied.extend(changes)
        return normalized, applied


query_intent_analyzer = QueryIntentAnalyzer()
