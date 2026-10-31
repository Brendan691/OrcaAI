"""CARE: confidence-adaptive cross-encoder evidence reranking."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Awaitable, Callable

import httpx

from ..core.config import config
from ..models.retrieval import SearchResult


RerankRequester = Callable[[str, list[str]], Awaitable[list[dict]]]


@dataclass(frozen=True)
class CareRerankOutcome:
    results: list[SearchResult]
    used: bool
    weight: float
    warning: str = ""


class CareReranker:
    def __init__(
        self,
        *,
        requester: RerankRequester | None = None,
        enabled: bool | None = None,
    ):
        self.requester = requester
        self.enabled = config.RERANK_ENABLED if enabled is None else enabled

    async def rerank(
        self,
        query: str,
        candidates: list[SearchResult],
        *,
        top_k: int,
    ) -> CareRerankOutcome:
        if top_k <= 0:
            return CareRerankOutcome(results=[], used=False, weight=0.0)
        if (
            not self.enabled
            or (self.requester is None and not config.has_dashscope_api_key)
            or len(candidates) < 2
        ):
            return CareRerankOutcome(results=candidates[:top_k], used=False, weight=0.0)

        selected = candidates[: config.RERANK_CANDIDATES]
        documents = [
            f"Title: {item.title}\nExcerpt: {item.content[:config.RERANK_MAX_CHARACTERS]}"
            for item in selected
        ]
        try:
            response = (
                await self.requester(query, documents)
                if self.requester is not None
                else await self._request(query, documents)
            )
            ordered = self._validate_response(response, len(selected))
        except (httpx.HTTPError, KeyError, TypeError, ValueError, IndexError) as exc:
            return CareRerankOutcome(
                results=candidates[:top_k],
                used=False,
                weight=0.0,
                warning=f"CARE rerank fallback: {type(exc).__name__}",
            )

        baseline_margin = max(0.0, selected[0].score - selected[1].score)
        gte_margin = max(0.0, ordered[0]["relevance_score"] - ordered[1]["relevance_score"])
        top1_agreement = float(
            selected[0].doc_id == selected[ordered[0]["index"]].doc_id
        )
        weight = self.adaptive_weight(
            baseline_margin,
            gte_margin,
            top1_agreement=top1_agreement,
        )
        baseline_rr = {index: 1.0 / rank for rank, index in enumerate(range(len(selected)), start=1)}
        gte_rr = {item["index"]: 1.0 / rank for rank, item in enumerate(ordered, start=1)}
        gte_score = {item["index"]: item["relevance_score"] for item in ordered}
        rescored = []
        for index, candidate in enumerate(selected):
            score = (
                (1.0 - weight) * baseline_rr[index]
                + weight * (0.4 * gte_rr[index] + 0.6 * gte_score[index])
            )
            rescored.append(candidate.model_copy(update={"score": round(score, 4)}))
        rescored.sort(key=lambda item: item.score, reverse=True)
        rescored.extend(candidates[len(selected):])
        return CareRerankOutcome(
            results=rescored[:top_k],
            used=True,
            weight=round(weight, 4),
        )

    @staticmethod
    def adaptive_weight(
        baseline_margin: float,
        gte_margin: float,
        *,
        top1_agreement: float = 0.0,
    ) -> float:
        baseline_z = (
            baseline_margin - config.CARE_MARGIN_A_MEAN
        ) / config.CARE_MARGIN_A_SCALE
        gte_z = (
            gte_margin - config.CARE_MARGIN_G_MEAN
        ) / config.CARE_MARGIN_G_SCALE
        agreement_z = (
            top1_agreement - config.CARE_AGREEMENT_MEAN
        ) / config.CARE_AGREEMENT_SCALE
        logit = (
            config.CARE_GATE_INTERCEPT
            + config.CARE_GATE_BASELINE_MARGIN * baseline_z
            + config.CARE_GATE_GTE_MARGIN * gte_z
            + config.CARE_GATE_TOP1_AGREEMENT * agreement_z
        )
        return 1.0 / (1.0 + math.exp(-max(-30.0, min(30.0, logit))))

    @staticmethod
    def _validate_response(response: list[dict], candidate_count: int) -> list[dict]:
        if len(response) != candidate_count:
            raise ValueError("incomplete rerank response")
        indices = [int(item["index"]) for item in response]
        if sorted(indices) != list(range(candidate_count)):
            raise ValueError("rerank response indices are invalid")
        return [
            {
                "index": int(item["index"]),
                "relevance_score": min(1.0, max(0.0, float(item["relevance_score"]))),
            }
            for item in response
        ]

    async def _request(self, query: str, documents: list[str]) -> list[dict]:
        async with httpx.AsyncClient(timeout=config.RERANK_TIMEOUT_SECONDS) as client:
            response = await client.post(
                config.DASHSCOPE_RERANK_ENDPOINT,
                headers={
                    "Authorization": f"Bearer {config.DASHSCOPE_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": config.RERANK_MODEL,
                    "input": {"query": query, "documents": documents},
                    "parameters": {"top_n": len(documents), "return_documents": False},
                },
            )
            response.raise_for_status()
            payload = response.json()
            return (payload.get("output") or {}).get("results", [])


care_reranker = CareReranker()
