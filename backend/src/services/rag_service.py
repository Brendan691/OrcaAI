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
)
from .chroma_store import chroma_store
from .care_reranker import care_reranker
from .embedding_service import embedding_service
from .evidence_selector import evidence_selector
from .hybrid_search import hybrid_search
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
        self.llm_enabled = config.has_api_key if llm_enabled is None else llm_enabled
        self.model = config.CHAT_MODEL
        self.top_k = config.TOP_K
        self.qa_system_prompt = get_active_domain().qa_system_prompt

    @property
    def client(self):
        if self._client is None:
            self._client = OpenAI(
                api_key=config.DASHSCOPE_API_KEY,
                base_url=config.DASHSCOPE_BASE_URL,
            )
        return self._client

    async def chat(self, request: ChatRequest) -> ChatResponse:
        query_embedding = self.embedding.embed_text(request.message)
        hits = self.knowledge_base.search(
            query_embedding=query_embedding,
            top_k=max(self.top_k * 2, config.RERANK_CANDIDATES),
            doc_filter=request.doc_filter,
        )
        ranking = hybrid_search.rank(
            hits,
            request.message,
            request.tag_filter,
            top_k=max(self.top_k, config.RERANK_CANDIDATES),
        )
        care = await self.reranker.rerank(
            request.message,
            ranking.results,
            top_k=self.top_k,
        )
        local_results = care.results

        search_outcome = SearchOutcome(status="ok", provider="disabled")
        if request.search_internet:
            search_outcome = await self.web_search.search(request.message, limit=self.top_k)

        evidence = evidence_selector.select(
            local_results=local_results,
            web_results=search_outcome.results if request.search_internet else [],
            retrieval_confidence=ranking.confidence,
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
