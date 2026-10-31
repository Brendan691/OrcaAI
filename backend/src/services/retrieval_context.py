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
                f'cite_marker="{html.escape(citation.cite_marker)}" time_note="{html.escape(evidence_time_note(getattr(citation, "year", None)))}"',
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


def _year_of(value) -> int | None:
    """安全解析年份；脏值一律视为未知（不抛异常）。"""
    if value is None:
        return None
    try:
        return int(str(value)[:4])
    except (TypeError, ValueError):
        return None


def time_weight_for(year, target_year, window: int = 2) -> float:
    """软约束时间权重（严禁硬过滤）。

    year == target       -> 1.5
    |Δ| <= 1             -> 1.2
    |Δ| <= window(默认2)  -> 1.0
    超出 window          -> 0.6（降权但保留）
    year 缺失(None)      -> 0.8（降权但保留）
    """
    if target_year is None:
        return 1.0
    value = _year_of(year)
    if value is None:
        return 0.8
    delta = abs(value - int(target_year))
    if delta == 0:
        return 1.5
    if delta <= 1:
        return 1.2
    if delta <= int(window):
        return 1.0
    return 0.6


def _get_score(hit) -> float:
    return float(getattr(hit, "score", 0.0) if not isinstance(hit, dict) else hit.get("score", 0.0))


def _set(hit, name, value) -> None:
    if isinstance(hit, dict):
        hit[name] = value
    else:
        setattr(hit, name, value)


def apply_time_boost(hits: list, target_year, window: int = 2) -> list:
    """把时间权重乘到检索得分上并重排；不丢弃任何文档。"""
    boosted = []
    for hit in hits:
        weight = time_weight_for(getattr(hit, "year", None) if not isinstance(hit, dict) else hit.get("year"), target_year, window)
        _set(hit, "time_weight_applied", weight)
        _set(hit, "temporal_fallback", weight == 0.8)
        _set(hit, "score", _get_score(hit) * weight)
        boosted.append(hit)
    return sorted(boosted, key=_get_score, reverse=True)


def ensure_time_coverage(ranked: list, target_year, top_k: int, window: int = 2) -> list:
    """先保证"有年且在容忍窗口内"的文档进 Top-K；不足时才用缺年文档补齐。"""
    if target_year is None:
        return list(ranked[:top_k])
    in_window, outside, unknown = [], [], []
    for hit in ranked:
        value = _year_of(getattr(hit, "year", None) if not isinstance(hit, dict) else hit.get("year"))
        if value is None:
            unknown.append(hit)
        elif abs(value - int(target_year)) <= int(window):
            in_window.append(hit)
        else:
            outside.append(hit)
    out = (in_window + outside)[:top_k]
    if len(out) < top_k:
        for hit in unknown:
            if len(out) >= top_k:
                break
            out.append(hit)
    return out


def filter_by_year(hits: list, year, keep_unknown: bool = True, window: int = 2) -> list:
    """兼容旧调用：软约束重排 + Top-K 覆盖保障（绝不硬过滤）。

    keep_unknown 保留参数仅为兼容；缺时间文档始终保留（降权 + 后置）。
    """
    del keep_unknown
    return apply_time_boost(list(hits), year, window)


def evidence_time_note(year) -> str:
    """生成阶段的时间提示：缺时间必须显式声明，防止模型脑补年份。"""
    value = _year_of(year)
    if value is None:
        return "此证据未标注发布时间"
    return f"该证据发布时间：{value} 年"


def filter_by_year_legacy(*_args, **_kwargs):
    raise NotImplementedError("硬过滤版本已废弃：时间条件必须使用软约束（apply_time_boost）")
