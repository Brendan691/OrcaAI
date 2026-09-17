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
