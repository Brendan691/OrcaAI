"""文档处理服务 - URL解析、PDF解析、文本切片"""
import hashlib
import json
import re
from typing import List, Optional
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

from ..core.config import config
from ..models.document import DocumentChunk


class DocumentProcessor:
    """文档处理器"""

    def __init__(self):
        self.chunk_size = config.CHUNK_SIZE
        self.chunk_overlap = config.CHUNK_OVERLAP
        self.chunk_min_length = getattr(config, "CHUNK_MIN_LENGTH", 80)
        self.chunk_max_table = getattr(config, "CHUNK_MAX_TABLE", 1000)
        # 递归分层分隔符优先级（最后一项为空串＝最终兜底硬切）
        self.separators = ["\n\n", "\n", "。", "！", "？", "；", "，", " ", ""]

    def fetch_webpage(self, url: str) -> tuple[str, str]:
        """抓取网页内容

        Args:
            url: 网页URL

        Returns:
            (title, content) 元组
        """
        title, text, _ = self.fetch_webpage_with_metadata(url)
        return title, text

    def fetch_webpage_with_metadata(self, url: str) -> tuple[str, str, dict]:
        """抓取正文，并从结构化字段中提取可核验的来源发布日期。"""
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            )
        }
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        response.encoding = response.apparent_encoding

        soup = BeautifulSoup(response.text, "html.parser")

        # 提取标题
        title = ""
        if soup.title:
            title = soup.title.string.strip() if soup.title.string else ""

        # 移除不需要的元素
        for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
            tag.decompose()

        # 提取正文
        # 优先找 article 或 main 标签
        content_elem = soup.find("article") or soup.find("main")
        if content_elem:
            text = content_elem.get_text(separator="\n", strip=True)
        else:
            # 退而求其次，提取所有段落
            paragraphs = soup.find_all("p")
            text = "\n".join(p.get_text(strip=True) for p in paragraphs)

        # 清理文本
        text = self._clean_text(text)

        return title, text, {"published_at": self._extract_published_at(soup)}

    @staticmethod
    def _extract_published_at(soup: BeautifulSoup) -> str:
        for attrs in (
            {"property": "article:published_time"},
            {"property": "og:published_time"},
            {"name": "date"},
            {"name": "publishdate"},
            {"name": "pubdate"},
        ):
            element = soup.find("meta", attrs=attrs)
            if element and element.get("content"):
                return str(element["content"]).strip()

        time_element = soup.find("time", attrs={"datetime": True})
        if time_element:
            return str(time_element["datetime"]).strip()

        for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
            try:
                payload = json.loads(script.string or script.get_text() or "{}")
            except (TypeError, json.JSONDecodeError):
                continue
            records = payload if isinstance(payload, list) else [payload]
            for record in records:
                if isinstance(record, dict) and record.get("datePublished"):
                    return str(record["datePublished"]).strip()
        return ""

    def process_text(self, content: str, title: str = "") -> tuple[str, List[DocumentChunk]]:
        """处理纯文本内容

        Args:
            content: 文本内容
            title: 标题

        Returns:
            (清理后的全文, 切片列表)
        """
        cleaned = self._clean_text(content)
        chunks = self._split_text(cleaned)
        return cleaned, chunks

    def _clean_text(self, text: str) -> str:
        """清理文本"""
        text = text.replace("\r\n", "\n").replace("\r", "\n")
        # 移除特殊字符但保留中文标点
        text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", text)
        # 合并横向空白，但保留换行作为引用定位依据
        text = re.sub(r"[\t \f\v]+", " ", text)
        text = re.sub(r" *\n *", "\n", text)
        # 移除过多的换行
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()

    def _split_text(self, text: str) -> List[DocumentChunk]:
        """V12 递归分层分块规范（2026-10-15 v3，实验与线上必须一致）：

        1. 分隔符优先级 ["\n\n", "\n", "。", "！", "？", "；", "，", ""]，逐级下探，
           绝不优先硬切字符；
        2. CHUNK_SIZE=600、CHUNK_OVERLAP=100，重叠部分必须是完整句子；
        3. Markdown 表格整表独立成块；表格超过 CHUNK_MAX_TABLE 时，其后续第一个块
           的开头带 `（表格续表，表头为：…）` 提示（存于 prefix_hint，不改坐标）；
        4. 每个切片满足 content == text[start_idx:end_idx]，坐标相对清洗后文本重算。
        """
        spans: list[tuple[int, int, str]] = []
        cursor = 0
        for table_start, table_end in self._table_spans(text):
            if table_start > cursor:
                spans.extend(self._plain_spans(text, cursor, table_start))
            spans.append((table_start, table_end, ""))
            cursor = table_end
        if cursor < len(text):
            spans.extend(self._plain_spans(text, cursor, len(text)))
        for index, (start, end, _hint) in enumerate(spans):
            if text[start:end].lstrip().startswith("|") and (end - start) > self.chunk_max_table:
                if index + 1 < len(spans):
                    header = self._table_header_hint(text, start, end)
                    n_start, n_end, _ = spans[index + 1]
                    spans[index + 1] = (n_start, n_end, f"（表格续表，表头为：{header}）")
        return self._materialize_spans(text, spans)

    @staticmethod
    def _table_header_hint(text: str, start: int, end: int) -> str:
        first_line = text[start:end].split("\n", 1)[0]
        cells = [cell.strip() for cell in first_line.strip().strip("|").split("|")]
        return " | ".join(cell for cell in cells if cell) or "（无表头）"

    def _units(self, text: str, start: int, end: int) -> List[tuple[int, int]]:
        """把 [start,end) 切成原子单元：段落 → 句子 → 硬切。"""
        units: list[tuple[int, int]] = []
        for para_start, para_end in self._paragraph_spans(text, start, end):
            if para_end - para_start <= self.chunk_size:
                units.append((para_start, para_end))
                continue
            for sent_start, sent_end in self._sentence_spans(text, para_start, para_end):
                if sent_end - sent_start <= self.chunk_size:
                    units.append((sent_start, sent_end))
                    continue
                cursor = sent_start
                while cursor < sent_end:
                    step = min(self.chunk_size, sent_end - cursor)
                    units.append((cursor, cursor + step))
                    cursor += step
        return units

    @staticmethod
    def _paragraph_spans(text: str, start: int, end: int) -> List[tuple[int, int]]:
        spans: list[tuple[int, int]] = []
        cursor = start
        while cursor < end:
            nxt = text.find("\n\n", cursor, end)
            stop = end if nxt == -1 else nxt + 2
            segment = text[cursor:stop]
            if segment.strip():
                spans.append((cursor, stop))
            cursor = stop
        return spans

    @staticmethod
    def _sentence_spans(text: str, start: int, end: int) -> List[tuple[int, int]]:
        spans: list[tuple[int, int]] = []
        cursor = start
        for index in range(start, end):
            if text[index] in "。！？；\n":
                if index + 1 > cursor:
                    spans.append((cursor, index + 1))
                cursor = index + 1
        if cursor < end:
            spans.append((cursor, end))
        return spans

    def _plain_spans(self, text: str, start: int, end: int) -> List[tuple[int, int, str]]:
        """正文段：递归分层切分 + 整句重叠。"""
        segments = self._recursive_segments(text, start, end, 0)
        # 段尾吸附：若切点落在非自然边界（如括号内、词中），向后补到最近的分隔符
        snapped: list[tuple[int, int]] = []
        for seg_start, seg_end in segments:
            if seg_end < end:
                limit = min(end, seg_end + 120)
                for pos in range(seg_end, limit):
                    if text[pos] in "。！？；\n":
                        seg_end = pos + 1
                        break
            snapped.append((seg_start, seg_end))
        segments = snapped
        results: list[tuple[int, int, str]] = []
        for index, (seg_start, seg_end) in enumerate(segments):
            if index > 0:
                prev_start, prev_end = segments[index - 1]
                overlap_start = seg_start
                accumulated = 0
                for unit_start, unit_end in reversed(
                    [seg for seg in self._recursive_segments(text, prev_start, prev_end, self.separators.index('。'))]
                ):
                    unit_len = unit_end - unit_start
                    if accumulated >= self.chunk_overlap or accumulated + unit_len > self.chunk_overlap * 2:
                        break
                    if seg_end - unit_start > self.chunk_size:
                        break
                    # 重叠起点必须是自然边界（句末/换行/空格），否则放弃该段重叠
                    if unit_start > 0 and text[unit_start - 1] not in "\n。！？；:： ":
                        break
                    overlap_start = unit_start
                    accumulated += unit_len
                seg_start = overlap_start
            results.append((seg_start, seg_end, ""))
        return results

    def _recursive_segments(
        self, text: str, start: int, end: int, sep_index: int
    ) -> List[tuple[int, int]]:
        """按分隔符优先级递归切分，保证每段 <= chunk_size 或走到最后一级。"""
        if end - start <= self.chunk_size:
            return [(start, end)]
        if sep_index >= len(self.separators) or self.separators[sep_index] == "":
            out: list[tuple[int, int]] = []
            cursor = start
            while cursor < end:
                out.append((cursor, min(end, cursor + self.chunk_size)))
                cursor += self.chunk_size
            return out
        separator = self.separators[sep_index]
        pieces: list[tuple[int, int]] = []
        cursor = start
        while cursor < end:
            found = text.find(separator, cursor, end)
            # 拉丁复合词保护：空格两侧都是拉丁字母时不在此切开（如 Cyber Security）
            if (separator == " " and found != -1 and found > start
                    and found + 1 < end
                    and text[found-1].isascii() and text[found-1].isalpha()
                    and text[found + 1].isascii() and text[found + 1].isalpha()):
                cursor = found + 1
                continue
            if found == -1:
                pieces.append((cursor, end))
                break
            pieces.append((cursor, found + len(separator)))
            cursor = found + len(separator)
        merged: list[tuple[int, int]] = []
        buffer: list[tuple[int, int]] = []
        buffer_len = 0
        for piece_start, piece_end in pieces:
            piece_len = piece_end - piece_start
            if piece_len > self.chunk_size:
                if buffer:
                    merged.append((buffer[0][0], buffer[-1][1]))
                    buffer, buffer_len = [], 0
                merged.extend(self._recursive_segments(text, piece_start, piece_end, sep_index + 1))
            elif buffer_len + piece_len <= self.chunk_size:
                buffer.append((piece_start, piece_end))
                buffer_len += piece_len
            else:
                merged.append((buffer[0][0], buffer[-1][1]))
                buffer, buffer_len = [(piece_start, piece_end)], piece_len
        if buffer:
            merged.append((buffer[0][0], buffer[-1][1]))
        return merged

    def _table_spans_as_chunks(
        self, text: str, start: int, end: int
    ) -> List[tuple[int, int, str]]:
        if end - start <= self.chunk_max_table:
            return [(start, end, "")]
        lines = text[start:end].split("\n")
        header_index = 0
        header_cells = [
            cell.strip()
            for cell in lines[header_index].strip().strip("|").split("|")
        ] if lines else []
        header_hint = "（接上表：" + " | ".join(header_cells) + "）" if header_cells else "（接上表）"
        head_lines = lines[:2] if len(lines) >= 2 else lines[:1]
        head_len = sum(len(line) + 1 for line in head_lines)
        results: list[tuple[int, int, str]] = []
        group_start = start
        group_len = head_len
        cursor = start + head_len
        for line in lines[2:] if len(lines) >= 2 else []:
            line_len = len(line) + 1
            if group_len + line_len > self.chunk_max_table and cursor > group_start:
                results.append((group_start, cursor, "" if group_start == start else header_hint))
                group_start, group_len = cursor, line_len
            else:
                group_len += line_len
            cursor += line_len
        if cursor > group_start:
            results.append((group_start, cursor, "" if group_start == start else header_hint))
        for index, (chunk_start, chunk_end, hint) in enumerate(results):
            if index == 0:
                results[index] = (chunk_start, chunk_end, "")
            else:
                results[index] = (chunk_start, chunk_end, hint or header_hint)
        return results

    @staticmethod
    def _materialize_spans(
        text: str, spans: List[tuple[int, int, str]]
    ) -> List[DocumentChunk]:
        chunks: List[DocumentChunk] = []
        for index, (start, end, hint) in enumerate(spans):
            segment = text[start:end]
            content = segment.strip()
            if not content:
                continue
            leading = len(segment) - len(segment.lstrip())
            actual_start = start + leading
            actual_end = actual_start + len(content)
            end_for_line = max(actual_start, actual_end - 1)
            chunks.append(
                DocumentChunk(
                    chunk_id=f"chunk_{len(chunks)}",
                    content=content,
                    start_idx=actual_start,
                    end_idx=actual_end,
                    line_start=text.count("\n", 0, actual_start) + 1,
                    line_end=text.count("\n", 0, end_for_line) + 1,
                    prefix_hint=hint,
                    flags=[],
                )
            )
        for index, chunk in enumerate(chunks):
            chunk.chunk_id = f"chunk_{index}"
        return chunks

    def _table_spans(self, text: str) -> List[tuple]:
        """返回 Markdown 表格块的字符区间 [start, end)。"""
        spans = []
        if "|" not in text:
            return spans
        lines = text.split("\n")
        line_starts = [0]
        for line in lines[:-1]:
            line_starts.append(line_starts[-1] + len(line) + 1)
        index = 0
        while index < len(lines):
            if lines[index].lstrip().startswith("|"):
                end_line = index
                while end_line < len(lines) and lines[end_line].lstrip().startswith("|"):
                    end_line += 1
                if end_line - index >= 2:
                    start = line_starts[index]
                    if end_line < len(lines):
                        end = line_starts[end_line] - 1
                    else:
                        end = len(text)
                    if end > start:
                        spans.append((start, end))
                index = end_line
            else:
                index += 1
        return spans

    @staticmethod
    def _span_containing(spans: List[tuple], position: int) -> Optional[tuple]:
        for start, end in spans:
            if start < position < end:
                return (start, end)
        return None

    def _raw_chunk_spans(self, text: str) -> List[tuple]:
        spans = self._table_spans(text)
        result: List[tuple] = []
        start = 0
        total = len(text)
        # 硬性上限：每次迭代至少前进 1 个字符，正常情况远低于该上限。
        max_iterations = total + 16
        iterations = 0
        while start < total:
            iterations += 1
            if iterations > max_iterations:
                raise RuntimeError(
                    f"切片边界调整未收敛（text_length={total}, start={start}）"
                )
            end = min(total, start + self.chunk_size)
            flags: List[str] = []
            if end < total:
                # 1) 句子/换行边界吸附（只在窗口后半段生效）
                for separator in ["\n", "。", "？", "！", ". ", "; "]:
                    position = text.rfind(separator, start, end)
                    if position > start + self.chunk_size * 0.5:
                        end = position + len(separator)
                        break
                # 2) 表格处理：优先整表进入同一片；实在放不下才允许拆，且绝不丢字
                span = self._span_containing(spans, end)
                if span is not None:
                    span_start, span_end = span
                    table_length = span_end - span_start
                    if (
                        table_length <= self.chunk_max_table
                        and span_start > start + self.chunk_min_length
                    ):
                        end = span_start            # 整表推到下一片
                        flags.append("table_pushed_next")
                    elif span_end - start <= self.chunk_max_table:
                        end = span_end              # 整表纳入本片
                        flags.append("table_atomic_extended")
                    else:
                        line_break = text.rfind("\n", start, end)
                        if line_break > start:
                            end = line_break + 1    # 退到表格行末
                            flags.append("table_split_at_row")
                        elif end <= start:
                            flags.append("table_row_hard_cut")
                        else:
                            flags.append("table_row_hard_cut")
            if end <= start:
                end = min(total, start + self.chunk_size)
            result.append((start, end, tuple(flags)))
            if end >= total:
                break
            if "table_pushed_next" in flags:
                # 整表推到下一片时不做重叠，否则重叠会把起点拉回表格之前，来回震荡
                next_start = end
            else:
                next_start = end - self.chunk_overlap
                if next_start <= start:
                    next_start = end
            # 起点若落在表格内部，向前吸附到行首；但绝不能越过 end（否则丢内容）
            span = self._span_containing(spans, next_start)
            if span is not None:
                line_break = text.find("\n", next_start)
                if line_break != -1 and line_break + 1 < end:
                    next_start = line_break + 1
            if next_start <= start:
                next_start = end
            start = next_start
        return result

    @staticmethod
    def _materialize_chunks(text: str, raw_spans: List[tuple]) -> List[DocumentChunk]:
        chunks: List[DocumentChunk] = []
        for index, (start, end, flags) in enumerate(raw_spans):
            segment = text[start:end]
            content = segment.strip()
            if not content:
                continue
            leading_trim = len(segment) - len(segment.lstrip())
            actual_start = start + leading_trim
            actual_end = actual_start + len(content)
            end_for_line = max(actual_start, actual_end - 1)
            chunks.append(
                DocumentChunk(
                    chunk_id=f"chunk_{index}",
                    content=content,
                    start_idx=actual_start,
                    end_idx=actual_end,
                    line_start=text.count("\n", 0, actual_start) + 1,
                    line_end=text.count("\n", 0, end_for_line) + 1,
                    flags=list(flags),
                )
            )
        for new_id, chunk in enumerate(chunks):
            chunk.chunk_id = f"chunk_{new_id}"
        return chunks

    def _merge_short_chunks(
        self,
        text: str,
        chunks: List[DocumentChunk],
    ) -> List[DocumentChunk]:
        """把过短的碎片并入相邻切片，保持 content == text[start:end]。"""
        if len(chunks) <= 1:
            return chunks
        merged: List[DocumentChunk] = []
        for chunk in chunks:
            if merged and len(chunk.content) < self.chunk_min_length:
                previous = merged[-1]
                if chunk.end_idx > previous.end_idx:
                    merged[-1] = self._extend_chunk(text, previous, chunk, "merged_short_tail")
                continue
            merged.append(chunk)
        if len(merged) > 1 and len(merged[0].content) < self.chunk_min_length:
            head, second = merged[0], merged[1]
            merged[0] = self._extend_chunk(text, head, second, "merged_short_head")
            del merged[1]
        for new_id, chunk in enumerate(merged):
            chunk.chunk_id = f"chunk_{new_id}"
        return merged

    @staticmethod
    def _extend_chunk(
        text: str,
        first: DocumentChunk,
        second: DocumentChunk,
        flag: str,
    ) -> DocumentChunk:
        end_idx = max(first.end_idx, second.end_idx)
        content = text[first.start_idx:end_idx]
        end_for_line = max(first.start_idx, end_idx - 1)
        return DocumentChunk(
            chunk_id=first.chunk_id,
            content=content,
            start_idx=first.start_idx,
            end_idx=end_idx,
            line_start=text.count("\n", 0, first.start_idx) + 1,
            line_end=text.count("\n", 0, end_for_line) + 1,
            page_number=first.page_number,
            flags=list(dict.fromkeys(list(first.flags) + [flag])),
        )

    def generate_doc_id(self, url: str = "", content: str = "") -> str:
        """生成文档唯一ID"""
        source = url or content[:100]
        return hashlib.md5(source.encode("utf-8")).hexdigest()[:16]


# 全局实例
document_processor = DocumentProcessor()
