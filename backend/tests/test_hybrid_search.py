"""测试混合相似度检索 - 核心创新模块"""
import pytest
import math
from datetime import datetime, timedelta
from src.services.hybrid_search import HybridSearch
from src.models.document import DocumentTags


class TestHybridSearch:

    def setup_method(self):
        self.hs = HybridSearch()

    def test_vector_score_perfect_match(self):
        """向量距离 0 → 相似度应接近 1"""
        score = self.hs.compute_vector_score(0.0)
        assert score > 0.9

    def test_vector_score_low_match(self):
        """向量距离 1 → 相似度应较低"""
        score = self.hs.compute_vector_score(1.0)
        assert score < 0.5

    def test_vector_score_range(self):
        """向量分数始终在 [0, 1]"""
        for dist in [-0.1, 0.0, 0.5, 1.0, 2.0]:
            score = self.hs.compute_vector_score(dist)
            assert 0.0 <= score <= 1.0, f"dist={dist} → score={score}"

    def test_keyword_score_exact_match(self):
        """完全匹配应得分较高（英文可正常分词）"""
        score = self.hs.compute_keyword_score("container shipping freight rate", "container shipping freight rate analysis report 2024")
        assert score > 0.2

    def test_keyword_score_no_match(self):
        """完全不匹配应得分接近 0"""
        score = self.hs.compute_keyword_score("集装箱", "散货运价分析")
        assert score < 0.3

    def test_keyword_score_range(self):
        """关键词分数在 [0, 1]"""
        score = self.hs.compute_keyword_score("航运集装箱港口", "关于航运集装箱港口的分析")
        assert 0.0 <= score <= 1.0

    def test_time_score_recent(self):
        """昨天的时间得分应按近 1"""
        from datetime import datetime, timedelta
        yesterday = (datetime.now() - timedelta(days=1)).isoformat()
        score = self.hs.compute_time_score(yesterday)
        assert score > 0.9

    def test_time_score_old(self):
        """一年前的时间得分应较低"""
        from datetime import datetime, timedelta
        long_ago = (datetime.now() - timedelta(days=365)).isoformat()
        score = self.hs.compute_time_score(long_ago)
        assert score < 0.1

    def test_time_score_range(self):
        """时间分数在 [0, 1]"""
        from datetime import datetime, timedelta
        for days in [0, 7, 30, 90, 365]:
            date = (datetime.now() - timedelta(days=days)).isoformat()
            score = self.hs.compute_time_score(date)
            assert 0.0 <= score <= 1.0, f"days={days} → score={score}"

    def test_time_score_invalid(self):
        """无效时间格式 → 默认 0.5"""
        score = self.hs.compute_time_score("invalid-date")
        assert score == 0.5

    def test_tag_score_exact_match(self):
        """标签完全匹配"""
        query_tags = DocumentTags(business_type=["集装箱运输"], geographic_region=["远东"])
        doc_tags = {"business_type": ["集装箱运输"], "geographic_region": ["远东"]}
        score = self.hs.compute_tag_score(query_tags, doc_tags)
        assert score == 1.0

    def test_tag_score_no_match(self):
        """标签完全不匹配"""
        query_tags = DocumentTags(business_type=["集装箱运输"])
        doc_tags = {"business_type": ["散货运输"]}
        score = self.hs.compute_tag_score(query_tags, doc_tags)
        assert score == 0.0

    def test_tag_score_no_filter(self):
        """无筛选条件 → 默认 0.5"""
        score = self.hs.compute_tag_score(None, {"business_type": ["集装箱运输"]})
        assert score == 0.5

    def test_fuse_scores_weighted_sum(self):
        """融合得分计算"""
        result = self.hs.fuse_scores(0.9, 0.5, 0.8, 1.0)
        expected = 0.6 * 0.9 + 0.2 * 0.5 + 0.1 * 0.8 + 0.1 * 1.0
        assert abs(result - expected) < 0.001

    def test_fuse_scores_range(self):
        """融合得分在 [0, 1]"""
        result = self.hs.fuse_scores(1.0, 1.0, 1.0, 1.0)
        assert 0.0 <= result <= 1.0

    def test_weights_sum_to_one(self):
        """默认权重之和应为 1"""
        total = (self.hs.vector_weight + self.hs.keyword_weight +
                 self.hs.time_weight + self.hs.tag_weight)
        assert abs(total - 1.0) < 0.001

    def test_adaptive_rank_disables_missing_temporal_signal(self):
        decision = self.hs.rank(
            [
                {"doc_id": "a", "content": "latest container rate", "distance": 0.1, "tags": {}},
                {"doc_id": "b", "content": "container market", "distance": 0.2, "tags": {}},
            ],
            "latest container rate",
        )

        assert decision.profile.freshness_intent == 1.0
        assert decision.profile.reliability["temporal"] == 0.0
        assert decision.profile.weights["temporal"] == 0.0

    def test_adaptive_rank_uses_source_date_for_freshness_query(self):
        decision = self.hs.rank(
            [
                {
                    "doc_id": "recent",
                    "content": "container rate outlook",
                    "distance": 0.2,
                    "published_at": datetime.now().isoformat(),
                    "tags": {},
                },
                {
                    "doc_id": "old",
                    "content": "container rate outlook",
                    "distance": 0.2,
                    "published_at": (datetime.now() - timedelta(days=365)).isoformat(),
                    "tags": {},
                },
            ],
            "latest container rate outlook",
        )

        assert decision.profile.weights["temporal"] > 0.1
        assert decision.results[0].doc_id == "recent"

    def test_exact_query_increases_lexical_share(self):
        exact = self.hs.rank(
            [{"doc_id": "a", "content": "SOLAS XI-2", "distance": 0.1, "tags": {}}],
            "SOLAS XI-2 requirements 2024",
        )
        semantic = self.hs.rank(
            [{"doc_id": "a", "content": "port security rules", "distance": 0.1, "tags": {}}],
            "How do port security rules affect implementation challenges?",
        )

        assert exact.profile.weights["lexical"] > semantic.profile.weights["lexical"]
        assert exact.profile.weights["vector"] < semantic.profile.weights["vector"]

    def test_tag_signal_is_gated_by_explicit_filter(self):
        hits = [{"doc_id": "a", "content": "port", "distance": 0.1, "tags": {"topic_category": ["港口"]}}]
        without_filter = self.hs.rank(hits, "port")
        with_filter = self.hs.rank(
            hits,
            "port",
            DocumentTags(topic_category=["港口"]),
        )

        assert without_filter.profile.weights["tag"] == 0.0
        assert with_filter.profile.weights["tag"] > 0.0

    def test_diverse_selection_avoids_adjacent_duplicate_chunks(self):
        hits = [
            {"doc_id": "same", "chunk_id": "1", "content": "集装箱运价持续上涨 港口拥堵", "distance": 0.01, "tags": {}},
            {"doc_id": "same", "chunk_id": "2", "content": "集装箱运价持续上涨 港口拥堵严重", "distance": 0.02, "tags": {}},
            {"doc_id": "other", "chunk_id": "3", "content": "红海绕航导致运输周期延长", "distance": 0.03, "tags": {}},
        ]

        decision = self.hs.rank(hits, "集装箱运价上涨和红海绕航", top_k=2)

        assert {result.doc_id for result in decision.results} == {"same", "other"}

    @staticmethod
    def test_tokenize_chinese():
        """中文分词：提取连续中文字符作为词"""
        tokens = HybridSearch._tokenize("集装箱 运价 走势 分析")
        assert len(tokens) > 0

    @staticmethod
    def test_tokenize_filter_stopwords():
        """停用词过滤：常见停用词应被过滤"""
        tokens = HybridSearch._tokenize("的 了 在 是 我")
        assert len(tokens) == 0  # 单字停用词，被 len>1 过滤
