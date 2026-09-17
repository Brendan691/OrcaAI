"""AI 内容生成服务 —— 基于知识库生成领域报告。

报告类型来自当前领域包(见 ADR-0003):内核只按 ReportType(系统提示词 + 检索 query)
干活,不认识"周报/风险预警"等航运概念。
联网增强属可选能力(见 ROADMAP),默认仅用知识库内容生成。
"""
import re
from datetime import date, datetime

from openai import OpenAI

from ..core.config import settings
from ..domains import get_active_domain
from .embedding_service import embedding_service
from .chroma_store import chroma_store


WEEKDAYS_ZH = ("一", "二", "三", "四", "五", "六", "日")
PUBLICATION_DATE_RE = re.compile(
    r"(?m)^[ \t]*(?:\*\*)?发布日期\s*[:：].*?(?:\*\*)?[ \t]*$"
)
MARKDOWN_CITATION_RE = re.compile(
    r"\[(?:\d+)\]\((https?://[^\s)]+)(\s+\"[^\"]*\")?\)"
)


def format_report_date(value: date) -> str:
    return f"{value.year}年{value.month}月{value.day}日（星期{WEEKDAYS_ZH[value.weekday()]}）"


def ensure_report_date(content: str, value: date) -> str:
    publication_line = f"**发布日期：{format_report_date(value)}**"
    if PUBLICATION_DATE_RE.search(content):
        return PUBLICATION_DATE_RE.sub(publication_line, content, count=1)
    return f"{publication_line}\n\n{content}"


def normalize_report_citations(content: str) -> str:
    citation_numbers: dict[str, int] = {}

    def replace(match: re.Match[str]) -> str:
        url = match.group(1)
        title = match.group(2) or ""
        number = citation_numbers.setdefault(url, len(citation_numbers) + 1)
        return f"[{number}]({url}{title})"

    return MARKDOWN_CITATION_RE.sub(replace, content)


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

    async def generate(self, report_type: str, time_range: str = "week", search_internet: bool = False) -> dict:
        """生成报告。基于知识库检索到的内容,让 LLM 撰写。

        Args:
            report_type: 报告类型 ID
            time_range: 时间范围
            search_internet: 是否联网搜索补充素材(当知识库素材不足时)
        """
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

        # 如果知识库素材不足且用户要求联网,补充互联网搜索结果
        internet_context = ""
        if search_internet:
            try:
                from .search_service import search_service
                internet_source_index = 1
                for query in rt.search_queries[:3]:
                    outcome = await search_service.search(query, limit=5)
                    for result in outcome.results[:3]:
                        internet_context += (
                            f"[{internet_source_index}] {result.title}\n"
                            f"    URL: {result.url}\n"
                            f"    {result.snippet}\n"
                        )
                        sources.append({"title": result.title, "url": result.url})
                        internet_source_index += 1
            except Exception:
                pass

        # 组合上下文,明确告诉 LLM 今天是几号、禁止用训练数据
        current_date = date.today()
        report_date = format_report_date(current_date)
        if not knowledge_context and not internet_context:
            full_context = "(暂无参考资料)"
        else:
            full_context = knowledge_context
            if internet_context:
                full_context += f"\n【互联网搜索结果(实时)】:\n{internet_context}"

        content_resp = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": rt.system_prompt},
                {"role": "user", "content": (
                    f"今天是 {report_date}。日期和星期已由系统计算,不得修改。\n\n"
                    f"参考资料：\n{full_context}\n\n"
                    f"请生成报告。重要提醒：\n"
                    f"1. 只能基于以上参考资料撰写,不要使用你的训练数据\n"
                    f"2. 如果参考资料不足,请明确标注「素材不足,建议开启联网搜索或先收藏相关文档」\n"
                    f"3. 数据要标注来源:\n"
                    f"   - 每条关键数据用上标引用,格式 [1](真实URL), [2](真实URL), …\n"
                    f"   - URL 必须从上方参考资料中提取,不得编造 URL\n"
                    f"   例如: 红海运价暴涨300%[1](https://真实新闻URL)\n"
                    f"4. 不要在报告末尾写「参考来源」列表(前端会自动生成)——只需在正文用 [1](URL) [2](URL) 标注即可\n"
                    f"5. 如输出发布日期,必须原样写为「发布日期：{report_date}」"
                )},
            ],
            temperature=0.3,
            max_tokens=3000,
        )
        content = normalize_report_citations(
            ensure_report_date(
                content_resp.choices[0].message.content.strip(), current_date
            )
        )

        return {
            "success": True,
            "title": rt.name,
            "content": content,
            "sources": sources[:8],  # 最多显示 8 个来源(本地+互联网)
            "generated_at": datetime.now().isoformat(),
        }


report_generator = ReportGenerator()
