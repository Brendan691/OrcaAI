"""中文检索能力测试 —— 覆盖 ADR-0006(中文 bigram)与 ADR-0007(mock 向量)。

这些测试在无 API Key 时也能跑(conftest 已置空 Key),不触外部服务。
"""
from src.services.hybrid_search import HybridSearch
from src.services.embedding_service import embedding_service


class TestChineseBigramTokenize:
    def test_tokenize_chinese_bigram(self):
        """中文按相邻两字切分为 bigram。"""
        tokens = HybridSearch._tokenize("集装箱运价")
        assert "集装" in tokens
        assert "运价" in tokens

    def test_chinese_keyword_matches(self):
        """含相同中文片段的正文,关键词得分应 > 0(修复前恒为 0)。"""
        score = HybridSearch().compute_keyword_score(
            "集装箱运价", "红海危机导致集装箱运价大幅上涨"
        )
        assert score > 0

    def test_unrelated_chinese_scores_lower(self):
        """无关正文的关键词得分,应低于相关正文。"""
        hs = HybridSearch()
        related = hs.compute_keyword_score("碳排放政策", "IMO发布碳排放政策新规")
        unrelated = hs.compute_keyword_score("碳排放政策", "集装箱船舶绕行好望角")
        assert related > unrelated


class TestMockEmbedding:
    def test_deterministic(self):
        """无 Key 时,相同文本产生相同向量(检索可命中)。"""
        v1 = embedding_service.embed_text("集装箱运价上涨")
        v2 = embedding_service.embed_text("集装箱运价上涨")
        assert v1 == v2

    def test_dimension(self):
        """mock 向量维度与真实模型一致(1024)。"""
        assert len(embedding_service.embed_text("测试")) == embedding_service.dimension

    def test_shared_words_more_similar(self):
        """共享词多的文本,mock 向量更相似(演示时检索有基本意义)。"""
        def cos(a, b):
            return sum(x * y for x, y in zip(a, b))
        base = embedding_service.embed_text("集装箱运价上涨")
        similar = embedding_service.embed_text("集装箱运价下跌")
        different = embedding_service.embed_text("船员招聘培训服务")
        assert cos(base, similar) > cos(base, different)
