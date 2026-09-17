"""把本地切片与互联网结果统一成可追溯的检索上下文。"""

import hashlib
import html
import re
import unicodedata
from dataclasses import dataclass

from ..models.document import Citation, SearchResult, WebSearchResult


def _citation_slug(title: str, snippet: str) -> str:
    text = unicodedata.normalize("NFKC", f"{title} {snippet}").lower()
    tokens = re.findall(r"[a-z0-9]+", text)
    if tokens:
        return "-".join(tokens[:3])[:40].strip("-")
    digest = hashlib.sha1(text.encode("utf-8")).hexdigest()[:8]
    return f"source-{digest}"


def _citation_id(index: int, title: str, snippet: str, line_range: str = "") -> str:
    citation_id = f"C{index}-{_citation_slug(title, snippet)}"
    return f"{citation_id}-L{line_range}" if line_range else citation_id


@dataclass(frozen=True)
class RetrievalContext:
    citations: list[Citation]
    prompt: str

    @classmethod
    def build(
        cls,
        *,
        local_results: list[SearchResult],
        web_results: list[WebSearchResult],
    ) -> "RetrievalContext":
        citations: list[Citation] = []

        for result in local_results:
            index = len(citations) + 1
            line_range = ""
            locator_label = ""
            if result.line_start is not None and result.line_end is not None:
                line_range = f"{result.line_start}-{result.line_end}"
                locator_label = f"第 {line_range} 行"
            citation_id = _citation_id(index, result.title, result.content, line_range)
            citations.append(
                Citation(
                    id=citation_id,
                    index=index,
                    cite_marker=f"[[{index}]]({citation_id})",
                    source_type="knowledge",
                    title=result.title,
                    snippet=result.content,
                    url=result.url,
                    doc_id=result.doc_id,
                    chunk_id=result.chunk_id,
                    chunk_index=result.chunk_index,
                    start_idx=result.start_idx,
                    end_idx=result.end_idx,
                    line_start=result.line_start,
                    line_end=result.line_end,
                    locator_label=locator_label,
                    score=result.score,
                )
            )

        for result in web_results:
            index = len(citations) + 1
            citation_id = _citation_id(index, result.title, result.snippet)
            citations.append(
                Citation(
                    id=citation_id,
                    index=index,
                    cite_marker=f"[[{index}]]({citation_id})",
                    source_type="web",
                    title=result.title,
                    snippet=result.snippet,
                    url=result.url,
                    provider=result.provider,
                    score=result.score,
                )
            )

        prompt_parts = []
        for citation in citations:
            attrs = [
                f'id="{html.escape(citation.id)}"',
                f'cite_marker="{html.escape(citation.cite_marker)}"',
                f'source="{citation.source_type}"',
                f'title="{html.escape(citation.title)}"',
            ]
            if citation.url:
                attrs.append(f'url="{html.escape(citation.url)}"')
            if citation.locator_label:
                attrs.append(f'locator="{html.escape(citation.locator_label)}"')
            prompt_parts.append(
                f"<cite {' '.join(attrs)}>\n"
                f"<snippet>{html.escape(citation.snippet)}</snippet>\n"
                "</cite>"
            )

        prompt = "<retrievals>\n" + "\n\n".join(prompt_parts) + "\n</retrievals>"
        return cls(citations=citations, prompt=prompt)

    def fallback_answer(self) -> str:
        if not self.citations:
            return "未找到相关资料。"
        lines = ["【未配置 LLM，以下为检索到的相关资料】", ""]
        for citation in self.citations:
            lines.append(
                f"{citation.index}. {citation.title}：{citation.snippet} "
                f"{citation.cite_marker}"
            )
        return "\n".join(lines)
