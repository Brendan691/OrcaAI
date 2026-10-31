"""RAG 问答：统一编排本地检索、联网检索与引用。"""

from openai import OpenAI

from ..core.config import config
from ..domains import get_active_domain
from ..models.document import (
    ChatRequest,
    ChatResponse,
    DocumentTags,
    SearchOutcome,
    SearchResult,
    WebSearchResult,
)
from .candidate_policy import (
    FINAL_EVIDENCE_LIMIT,
    LOCAL_CANDIDATE_LIMIT,
    WEB_CANDIDATE_LIMIT,
    candidate_policy_snapshot,
    diversify_candidates,
    interleave_source_candidates,
)
from .chroma_store import chroma_store
from .care_reranker import care_reranker
from .conflict_prior import assess_conflict_prior
from .embedding_service import embedding_service
from .evidence_selector import EvidenceSelection, evidence_selector
from .hybrid_search import hybrid_search
from .query_intent import query_intent_analyzer
from .retrieval_context import RetrievalContext
from .search_service import search_service


class RAGService:
    def __init__(
        self,
        *,
        embedding=embedding_service,
        knowledge_base=chroma_store,
        web_search=search_service,
        reranker=care_reranker,
        llm_enabled: bool | None = None,
    ):
        self._client = None
        self.embedding = embedding
        self.knowledge_base = knowledge_base
        self.web_search = web_search
        self.reranker = reranker
        if config.has_partial_qwen38_config:
            raise RuntimeError(
                "QWEN38_API_KEY, QWEN38_BASE_URL and QWEN38_MODEL "
                "must be configured together"
            )
        self.llm_enabled = config.has_api_key if llm_enabled is None else llm_enabled
        if config.qwen38_configured:
            self.model = config.QWEN38_MODEL
            self._llm_api_key = config.QWEN38_API_KEY
            self._llm_base_url = config.QWEN38_BASE_URL
        else:
            self.model = config.CHAT_MODEL
            self._llm_api_key = config.DASHSCOPE_API_KEY
            self._llm_base_url = config.DASHSCOPE_BASE_URL
        self.top_k = config.TOP_K
        self.qa_system_prompt = get_active_domain().qa_system_prompt

    @property
    def client(self):
        if self._client is None:
            self._client = OpenAI(
                api_key=self._llm_api_key,
                base_url=self._llm_base_url,
            )
        return self._client

    async def chat(self, request: ChatRequest) -> ChatResponse:
        query_intent = query_intent_analyzer.analyze(request.message)
        query_embedding = self.embedding.embed_text(request.message)
        hits = self.knowledge_base.search(
            query_embedding=query_embedding,
            top_k=max(config.RERANK_CANDIDATES * 2, LOCAL_CANDIDATE_LIMIT * 2),
            doc_filter=request.doc_filter,
        )
        ranking = hybrid_search.rank(
            hits,
            request.message,
            request.tag_filter,
            top_k=LOCAL_CANDIDATE_LIMIT,
        )
        local_candidates = diversify_candidates(
            ranking.results,
            LOCAL_CANDIDATE_LIMIT,
            document_key=lambda result: result.doc_id or result.url or result.title,
        )

        search_outcome = SearchOutcome(status="ok", provider="disabled")
        if request.search_internet:
            search_variants = getattr(self.web_search, "search_variants", None)
            if search_variants is not None:
                search_outcome = await search_variants(
                    query_intent.variants,
                    limit=WEB_CANDIDATE_LIMIT,
                )
            else:
                search_outcome = await self.web_search.search(
                    request.message,
                    limit=WEB_CANDIDATE_LIMIT,
                )

        web_results, _ = evidence_selector.deduplicate_web(
            local_candidates,
            search_outcome.results if request.search_internet else [],
        )
        web_candidates = [
            SearchResult(
                doc_id="",
                chunk_id="",
                title=result.title,
                content=result.snippet,
                url=result.url,
                source_type="web",
                score=result.score or 0.0,
                published_at=result.published_at,
                provider=result.provider,
                query_variant=result.query_variant,
                variant_rule=result.variant_rule,
                variant_rank=result.variant_rank,
            )
            for result in web_results
        ]
        merged = interleave_source_candidates(local_candidates, web_candidates)
        candidates = [candidate.item for candidate in merged]
        if candidates:
            care = await self.reranker.rerank(
                request.message,
                candidates,
                top_k=min(len(candidates), config.RERANK_CANDIDATES),
            )
            ranked_results = list(care.results)
        else:
            ranked_results = []
        conflict_priors = []
        if query_intent.conflict_sensitive and ranked_results:
            rescored = []
            for result in ranked_results:
                assessment = assess_conflict_prior(
                    title=result.title,
                    text=result.content,
                    url=result.url,
                    published_at=result.published_at,
                    base_score=result.score,
                    intent=query_intent,
                )
                rescored.append(
                    result.model_copy(update={"score": round(assessment.final_score, 6)})
                )
                conflict_priors.append(
                    {
                        "title": result.title,
                        "url": result.url,
                        "source_type": result.source_type,
                        **assessment.as_dict(),
                    }
                )
            ranked_results = sorted(
                rescored,
                key=lambda result: result.score,
                reverse=True,
            )
        ranked_results = ranked_results[:FINAL_EVIDENCE_LIMIT]

        web_by_url = {result.url: result for result in web_results}
        local_results = []
        final_web_results = []
        for result in ranked_results:
            if not result.chunk_id and result.url:
                original = web_by_url.get(result.url)
                if original is not None:
                    final_web_results.append(original)
                else:
                    final_web_results.append(
                        WebSearchResult(
                            title=result.title,
                            url=result.url,
                            snippet=result.content,
                            provider=result.provider,
                            score=result.score,
                            published_at=result.published_at,
                            query_variant=result.query_variant,
                            variant_rule=result.variant_rule,
                            variant_rank=result.variant_rank,
                        )
                    )
            else:
                local_results.append(result)
        evidence = EvidenceSelection(
            local_results=local_results,
            web_results=final_web_results,
            local_quota=len(local_results),
            web_quota=len(final_web_results),
            duplicates_removed=0,
        )
        context = RetrievalContext.build(
            local_results=evidence.local_results,
            web_results=evidence.web_results,
        )
        if not context.citations:
            if request.search_internet and search_outcome.status == "failed":
                message = "知识库和互联网搜索均未找到可用内容。"
            else:
                message = "知识库中暂未找到相关内容。请尝试上传相关文档后再提问。"
            return ChatResponse(
                answer=message,
                sources=[],
                confidence=0.0,
                search_status=search_outcome.status if request.search_internet else "disabled",
                search_message=self._search_message(search_outcome),
                query_variants=(
                    search_outcome.query_variants
                    if search_outcome.query_variants
                    else list(query_intent.web_queries)
                ),
                retrieval_policy=candidate_policy_snapshot(),
                conflict_priors=conflict_priors,
            )

        answer = (
            self._generate_answer(request.message, context.prompt)
            if self.llm_enabled
            else context.fallback_answer()
        )
        return ChatResponse(
            answer=answer,
            sources=context.citations,
            confidence=self._confidence(
                local_results,
                bool(search_outcome.results),
                ranking.confidence,
            ),
            search_status=search_outcome.status if request.search_internet else "disabled",
            search_message=self._search_message(search_outcome),
            query_variants=(
                search_outcome.query_variants
                if search_outcome.query_variants
                else list(query_intent.web_queries)
            ),
            retrieval_policy=candidate_policy_snapshot(),
            conflict_priors=conflict_priors,
        )

    @staticmethod
    def _search_message(outcome: SearchOutcome) -> str:
        return "；".join(warning.message for warning in outcome.warnings)

    @staticmethod
    def _confidence(
        results: list[SearchResult],
        has_web_results: bool,
        retrieval_confidence: float | None = None,
    ) -> float:
        if retrieval_confidence is not None and results:
            return round(retrieval_confidence, 2)
        if results:
            value = 1 / (1 + 2.718 ** (-5 * (results[0].score - 0.6)))
            return round(min(value, 1.0), 2)
        return 0.6 if has_web_results else 0.0

    def _generate_answer(self, question: str, context: str) -> str:
        citation_rules = """
引用规则：
- 只能使用检索资料中的事实。
- 使用资料时，必须在相关句末原样复制该资料的 cite_marker，例如 [[1]](C1-example)。
- 不得编造引用 ID，也不得只写裸数字角标。
"""
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": self.qa_system_prompt + citation_rules},
                {
                    "role": "user",
                    "content": f"参考资料：\n{context}\n\n用户问题：{question}\n\n请基于参考资料回答：",
                },
            ],
            temperature=0.3,
            max_tokens=1500,
        )
        return response.choices[0].message.content.strip()


rag_service = RAGService()
