"""AI 内容生成服务 —— 基于知识库生成领域报告。

报告类型来自当前领域包(见 ADR-0003):内核只按 ReportType(系统提示词 + 检索 query)
干活,不认识"周报/风险预警"等航运概念。
联网增强属可选能力(见 ROADMAP),默认仅用知识库内容生成。
"""
from datetime import datetime

from openai import OpenAI

from ..core.config import settings
from ..domains import get_active_domain
from .embedding_service import embedding_service
from .chroma_store import chroma_store


class ReportGenerator:
    """领域报告自动生成器。"""

    def __init__(self):
        self._client = None
        self.model = settings.CHAT_MODEL
        self.report_types = get_active_domain().report_types

    # 兼容旧调用:api/generate.py 用 report_generator.REPORT_TYPES 列举类型
    @property
    def REPORT_TYPES(self):
        return {rid: {"name": rt.name} for rid, rt in self.report_types.items()}

    @property
    def client(self):
        if self._client is None:
            self._client = OpenAI(
                api_key=settings.DASHSCOPE_API_KEY,
                base_url=settings.DASHSCOPE_BASE_URL,
            )
        return self._client

    async def generate(self, report_type: str, time_range: str = "week") -> dict:
        """生成报告。基于知识库检索到的内容,让 LLM 撰写。"""
        rt = self.report_types.get(report_type)
        if not rt:
            return {"success": False, "title": "", "content": f"不支持的报告类型: {report_type}", "sources": []}

        # 从知识库检索相关内容作为素材
        knowledge_context = ""
        sources = []
        if settings.has_api_key:
            for query in rt.search_queries[:3]:
                try:
                    q_emb = embedding_service.embed_text(query)
                    hits = chroma_store.search(query_embedding=q_emb, top_k=3)
                    for h in hits:
                        knowledge_context += f"- {h['title']}: {h['content'][:300]}...\n"
                        if h.get("title"):
                            sources.append({"title": h["title"], "url": h.get("url", "")})
                except Exception:
                    pass

        if not knowledge_context:
            knowledge_context = "(知识库暂无相关素材,请先收藏一些相关文档)"

        content_resp = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": rt.system_prompt},
                {"role": "user", "content": f"参考资料：\n{knowledge_context}\n\n请生成报告："},
            ],
            temperature=0.3,
            max_tokens=3000,
        )
        content = content_resp.choices[0].message.content.strip()

        return {
            "success": True,
            "title": rt.name,
            "content": content,
            "sources": sources[:5],
            "generated_at": datetime.now().isoformat(),
        }


report_generator = ReportGenerator()
