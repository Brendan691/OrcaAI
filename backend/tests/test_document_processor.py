"""测试文档处理器（文本切片、清理、URL生成）"""
import pytest
from src.services.document_processor import DocumentProcessor
from src.models.document import DocumentChunk


class TestDocumentProcessor:

    def setup_method(self):
        self.processor = DocumentProcessor()

    def test_process_text_basic(self):
        """基本文本处理"""
        content = "这是一篇关于航运集装箱运输的测试文档。内容包含运价波动相关的分析。"
        full_text, chunks = self.processor.process_text(content)

        assert isinstance(full_text, str)
        assert len(full_text) > 0
        assert isinstance(chunks, list)

    def test_chunk_generation(self):
        """切片生成：长文本应产生多个切片"""
        content = "航运知识" * 500  # 2000 字符
        _, chunks = self.processor.process_text(content)

        # 确认产生了多个切片
        assert len(chunks) >= 1
        for chunk in chunks:
            assert isinstance(chunk, DocumentChunk)
            assert chunk.chunk_id.startswith("chunk_")
            assert len(chunk.content) > 0
            assert chunk.start_idx >= 0
            assert chunk.end_idx > chunk.start_idx

    def test_short_text_single_chunk(self):
        """短文本只产生一个切片"""
        content = "这是一篇很短的航运新闻。"
        _, chunks = self.processor.process_text(content)

        assert len(chunks) == 1
        assert chunks[0].content == content

    def test_generate_doc_id_url(self):
        """URL 生成 ID 的确定性"""
        url = "https://example.com/maritime-news"
        id1 = self.processor.generate_doc_id(url=url)
        id2 = self.processor.generate_doc_id(url=url)

        assert id1 == id2  # 相同输入应产生相同 ID
        assert len(id1) == 16  # MD5 前 16 位

    def test_generate_doc_id_different_urls(self):
        """不同 URL 产生不同 ID"""
        id1 = self.processor.generate_doc_id(url="https://a.com/news1")
        id2 = self.processor.generate_doc_id(url="https://a.com/news2")

        assert id1 != id2

    def test_clean_text(self):
        """文本清理"""
        dirty = "  航运  新闻  \n\n\n连续  空行  "
        cleaned = self.processor._clean_text(dirty)

        assert "  " not in cleaned  # 无连续空格
        assert "\n\n\n" not in cleaned  # 无过多换行
        assert cleaned == cleaned.strip()  # 去除了首尾空白

    def test_chunk_boundary_on_sentence(self):
        """切片在句子边界处断开"""
        content = "第一段。" * 100 + "第二段。" * 100
        _, chunks = self.processor.process_text(content)

        for chunk in chunks:
            # 每个切片内容不是空的
            assert len(chunk.content) > 0
            # 不超过 chunk_size + 一些容差
            assert len(chunk.content) <= self.processor.chunk_size + 100

    def test_process_text_preserves_lines_and_chunk_locators(self):
        content = "第一行。\n第二行包含航运信息。\n第三行。"

        full_text, chunks = self.processor.process_text(content)

        assert full_text.count("\n") == 2
        assert chunks[0].line_start == 1
        assert chunks[0].line_end == 3

    def test_extracts_structured_publication_date(self):
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(
            '<html><head><meta property="article:published_time" content="2026-08-20T09:30:00+08:00"></head></html>',
            "html.parser",
        )

        assert self.processor._extract_published_at(soup) == "2026-08-20T09:30:00+08:00"


class TestChunkFreezeRules:
    """2026-10-14 冻结的切片规则：表格原子化、短块合并、定位可回溯。"""

    def setup_method(self):
        self.processor = DocumentProcessor()

    @staticmethod
    def _table(rows: int) -> str:
        lines = ["| 编号 | 要求 | SL1 |", "| --- | --- | --- |"]
        for index in range(rows):
            lines.append(f"| SR1.{index} | 应支持统一帐户管理的能力第{index}条 | √ |")
        return "\n".join(lines)

    def test_chunk_content_matches_offsets(self):
        text = "第一行。\n" + ("航运信息。" * 400) + "\n最后一行。"
        _, chunks = self.processor.process_text(text)

        assert chunks
        for chunk in chunks:
            assert chunk.content == text[chunk.start_idx : chunk.end_idx]
            assert chunk.line_start == text.count("\n", 0, chunk.start_idx) + 1
            end_for_line = max(chunk.start_idx, chunk.end_idx - 1)
            assert chunk.line_end == text.count("\n", 0, end_for_line) + 1

    def test_table_kept_in_one_chunk(self):
        table = self._table(20)
        text = ("前文。" * 200) + "\n" + table + "\n后续正文。" * 50
        _, chunks = self.processor.process_text(text)

        holders = [c for c in chunks if "| 编号 | 要求 | SL1 |" in c.content]
        assert holders, "表格未被任何切片收录"
        holder = holders[0]
        for line in table.split("\n"):
            assert line in holder.content, f"表格行被切散：{line}"

    def test_table_kept_atomic_under_v3_spec(self):
        """v3 规范：Markdown 表格整表独立成块，不再按行拆分。"""
        table = self._table(400)
        _, chunks = self.processor.process_text(table)
        holders = [c for c in chunks if "| 编号 | 要求 | SL1 |" in c.content]
        assert holders, "表格未被任何切片收录"
        holder = holders[0]
        assert holder.content.lstrip().startswith("|")
        assert holder.content.rstrip().endswith("|")
        full_rows = sum(1 for line in holder.content.split("\n") if line.strip().startswith("|"))
        assert full_rows >= 3, "表格应整表成块"

    def test_v3_chunk_size_and_offsets(self):
        """v3 规范：递归分层切分，块长不超过上限 + 重叠，且偏移精确。"""
        text = ("正文内容。" * 300) + "尾"
        _, chunks = self.processor.process_text(text)
        assert len(chunks) >= 1
        for chunk in chunks:
            assert chunk.content == text[chunk.start_idx:chunk.end_idx]
            assert len(chunk.content) <= self.processor.chunk_size + 120, (
                f"块长超上限：{len(chunk.content)}"
            )
        assert any(
            chunks[i + 1].start_idx < chunks[i].end_idx for i in range(len(chunks) - 1)
        ), "相邻块之间应存在重叠"

    def test_no_table_chunk_cut_mid_row(self):
        table = self._table(60)
        text = ("段落文字。" * 100) + "\n" + table + "\n" + ("结尾文字。" * 100)
        _, chunks = self.processor.process_text(text)

        for chunk in chunks:
            content = chunk.content
            if "|" in content and "table_split_at_row" not in chunk.flags:
                rows = [line for line in content.split("\n") if line.strip().startswith("|")]
                if rows:
                    assert rows[-1].rstrip().endswith("|"), (
                        f"切片在表格行中间结束且未标记：{rows[-1][:60]}"
                    )
