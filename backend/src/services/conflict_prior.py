"""Auditable authority/freshness prior for time-sensitive conflict questions."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from urllib.parse import urlsplit

from .query_intent import QueryIntent


VERSION = "conflict-prior-20261021-v1"
OFFICIAL_HOST_SUFFIXES = (
    ".gov",
    ".gov.cn",
    ".un.org",
    ".imo.org",
    ".worldbank.org",
    ".shihang.org",
    ".europa.eu",
)
PUBLIC_REPORT_HOSTS = (
    "china.com.cn",
    "people.com.cn",
    "xinhuanet.com",
    "news.cn",
)
YEAR = re.compile(r"(?<!\d)(19\d{2}|20\d{2})(?!\d)")


@dataclass(frozen=True)
class ConflictPrior:
    applied: bool
    base_score: float
    prior_score: float
    final_score: float
    year: int | None
    authority_score: float
    recency_score: float
    reasons: tuple[str, ...]
    version: str = VERSION

    def as_dict(self) -> dict:
        return {
            "applied": self.applied,
            "base_score": round(self.base_score, 6),
            "prior_score": round(self.prior_score, 6),
            "final_score": round(self.final_score, 6),
            "year": self.year,
            "authority_score": round(self.authority_score, 6),
            "recency_score": round(self.recency_score, 6),
            "reasons": list(self.reasons),
            "version": self.version,
        }


def _host(url: str) -> str:
    try:
        return (urlsplit(url).hostname or "").lower()
    except ValueError:
        return ""


def _authority(title: str, url: str) -> tuple[float, list[str]]:
    host = _host(url)
    reasons: list[str] = []
    score = 0.35
    if host.endswith(OFFICIAL_HOST_SUFFIXES):
        score = 0.9
        reasons.append("official-host")
    elif any(host.endswith(item) or host == item for item in PUBLIC_REPORT_HOSTS):
        score = 0.72
        reasons.append("public-report-host")
    if re.search(
        r"年度报告|年度.{0,8}报告|年报|发展现状与未来趋势|annual report",
        title,
        re.IGNORECASE,
    ):
        score = min(1.0, score + 0.18)
        reasons.append("annual-report-title")
    return score, reasons


def extract_year(
    title: str,
    text: str,
    url: str = "",
    published_at: str | None = None,
) -> int | None:
    if published_at:
        match = YEAR.search(str(published_at))
        if match:
            return int(match.group(1))
    for source in (title, url, text[:600]):
        match = YEAR.search(source)
        if match:
            return int(match.group(1))
    return None


def _recency(year: int | None, current_year: int) -> tuple[float, list[str]]:
    if year is None:
        return 0.4, ["missing-year"]
    age = max(0, current_year - year)
    if age <= 2:
        return 1.0, ["current-within-2y"]
    if age <= 4:
        return 0.8, ["current-within-4y"]
    if age <= 8:
        return 0.55, ["moderately-stale"]
    if age <= 15:
        return 0.25, ["stale"]
    return 0.05, ["very-stale"]


def assess_conflict_prior(
    *,
    title: str,
    text: str,
    url: str,
    published_at: str | None,
    base_score: float,
    intent: QueryIntent,
    current_year: int | None = None,
) -> ConflictPrior:
    """Apply only when the query analyzer marked this as a current conflict."""
    if not intent.conflict_sensitive:
        return ConflictPrior(
            applied=False,
            base_score=base_score,
            prior_score=0.5,
            final_score=base_score,
            year=None,
            authority_score=0.5,
            recency_score=0.5,
            reasons=("intent-not-current-conflict",),
        )
    year = extract_year(title, text, url, published_at)
    authority, authority_reasons = _authority(title, url)
    recency, recency_reasons = _recency(
        year,
        current_year or date.today().year,
    )
    prior = 0.55 * authority + 0.45 * recency
    final = 0.4 * base_score + 0.6 * prior
    return ConflictPrior(
        applied=True,
        base_score=base_score,
        prior_score=prior,
        final_score=final,
        year=year,
        authority_score=authority,
        recency_score=recency,
        reasons=tuple((*authority_reasons, *recency_reasons)),
    )
