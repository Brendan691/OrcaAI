"""混合相似度检索模块 - 核心创新

结合向量相似度、关键词匹配、时间衰减和标签匹配的加权融合模型。
数学系背景的优势体现：优化问题建模。
"""
import math
import re
from collections import Counter
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

import numpy as np

from ..core.config import config
from ..models.document import DocumentTags, SearchResult


class HybridSearch:
    """混合相似度检索器

    核心公式：
    Score = w1 * VectorScore + w2 * KeywordScore + w3 * TimeScore + w4 * TagScore

    其中权重 w1 + w2 + w3 + w4 = 1，可通过网格搜索优化。
    """

    def __init__(self):
        # 权重配置（可调整）
        self.vector_weight = config.VECTOR_WEIGHT
        self.keyword_weight = config.KEYWORD_WEIGHT
        self.time_weight = config.TIME_WEIGHT
        self.tag_weight = config.TAG_WEIGHT

    def compute_vector_score(self, distance: float) -> float:
        """计算向量相似度得分

        Chroma返回的是余弦距离（1 - cosine_similarity），
        需要转换为相似度得分。

        Args:
            distance: Chroma返回的余弦距离

        Returns:
            归一化到[0,1]的相似度得分
        """
        # 余弦相似度 = 1 - 余弦距离
        cosine_sim = 1 - distance
        # 使用sigmoid变换增强区分度
        # 当cosine_sim接近1时，score接近1
        score = 1 / (1 + math.exp(-10 * (cosine_sim - 0.5)))
        return max(0.0, min(1.0, score))

    def compute_keyword_score(self, query: str, content: str) -> float:
        """计算关键词匹配得分（基于TF-IDF思想）

        Args:
            query: 查询文本
            content: 文档内容

        Returns:
            关键词匹配得分 [0,1]
        """
        # 提取查询关键词（去除停用词）
        query_tokens = self._tokenize(query)
        content_tokens = self._tokenize(content)

        if not query_tokens:
            return 0.0

        # 计算匹配的关键词数
        matched = sum(1 for token in query_tokens if token in content_tokens)

        # 计算BM25风格的得分
        k1, b = 1.5, 0.75
        score = 0.0
        content_len = len(content_tokens)
        avg_len = 200  # 假设平均文档长度

        for token in query_tokens:
            freq = content_tokens.count(token)
            if freq > 0:
                # 简化版BM25
                tf_component = freq * (k1 + 1) / (freq + k1 * (1 - b + b * content_len / avg_len))
                score += tf_component

        # 归一化
        max_possible = len(query_tokens) * (k1 + 1)
        normalized_score = min(score / max_possible, 1.0) if max_possible > 0 else 0.0

        return normalized_score

    def compute_time_score(self, created_at: str) -> float:
        """计算时间衰减得分

        新文档得分更高，使用指数衰减函数。

        Args:
            created_at: ISO格式时间字符串

        Returns:
            时间得分 [0,1]
        """
        try:
            doc_time = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
            now = datetime.now()
            days_diff = (now - doc_time).days

            # 半衰期：30天
            half_life = 30
            score = math.exp(-0.693 * days_diff / half_life)
            return max(0.0, min(1.0, score))
        except Exception:
            return 0.5  # 默认中等得分

    def compute_tag_score(
        self,
        query_tags: Optional[DocumentTags],
        doc_tags: Dict[str, List[str]],
    ) -> float:
        """计算标签匹配得分

        Args:
            query_tags: 查询中的标签筛选条件
            doc_tags: 文档的标签

        Returns:
            标签匹配得分 [0,1]
        """
        if not query_tags:
            return 0.5  # 无标签筛选时给中等得分

        matched = 0
        total = 0

        dims = [
            ("business_type", query_tags.business_type),
            ("geographic_region", query_tags.geographic_region),
            ("topic_category", query_tags.topic_category),
            ("event_nature", query_tags.event_nature),
        ]

        for dim_name, query_vals in dims:
            if query_vals:
                total += len(query_vals)
                doc_vals = doc_tags.get(dim_name, [])
                matched += len(set(query_vals) & set(doc_vals))

        if total == 0:
            return 0.5

        return matched / total

    def fuse_scores(
        self,
        vector_score: float,
        keyword_score: float,
        time_score: float,
        tag_score: float,
    ) -> float:
        """融合多个得分

        默认使用加权求和。未来可扩展为更复杂的融合策略。

        Args:
            vector_score: 向量相似度得分
            keyword_score: 关键词匹配得分
            time_score: 时间衰减得分
            tag_score: 标签匹配得分

        Returns:
            融合后的综合得分
        """
        total = (
            self.vector_weight * vector_score +
            self.keyword_weight * keyword_score +
            self.time_weight * time_score +
            self.tag_weight * tag_score
        )
        return total

    def optimize_weights(
        self,
        queries: List[str],
        ground_truth: List[List[str]],
        candidate_pool: List[Dict[str, Any]],
    ) -> Dict[str, float]:
        """通过网格搜索优化权重

        这是论文中的核心实验方法。给定一组查询和期望结果，
        搜索最优权重组合。

        Args:
            queries: 查询列表
            ground_truth: 每个查询对应的正确文档ID列表
            candidate_pool: 候选文档池

        Returns:
            最优权重配置
        """
        best_weights = {
            "vector": self.vector_weight,
            "keyword": self.keyword_weight,
            "time": self.time_weight,
            "tag": self.tag_weight,
        }
        best_score = 0.0

        # 网格搜索（步长0.1）
        for vw in np.arange(0.3, 0.8, 0.1):
            for kw in np.arange(0.0, 0.4, 0.1):
                for tw in np.arange(0.0, 0.3, 0.1):
                    tg = 1.0 - vw - kw - tw
                    if tg < 0:
                        continue

                    # 临时设置权重
                    self.vector_weight = round(vw, 2)
                    self.keyword_weight = round(kw, 2)
                    self.time_weight = round(tw, 2)
                    self.tag_weight = round(tg, 2)

                    # 评估当前权重
                    score = self._evaluate(queries, ground_truth, candidate_pool)

                    if score > best_score:
                        best_score = score
                        best_weights = {
                            "vector": self.vector_weight,
                            "keyword": self.keyword_weight,
                            "time": self.time_weight,
                            "tag": self.tag_weight,
                        }

        # 恢复最优权重
        self.vector_weight = best_weights["vector"]
        self.keyword_weight = best_weights["keyword"]
        self.time_weight = best_weights["time"]
        self.tag_weight = best_weights["tag"]

        return best_weights

    def _evaluate(
        self,
        queries: List[str],
        ground_truth: List[List[str]],
        candidate_pool: List[Dict[str, Any]],
    ) -> float:
        """评估当前权重的性能（NDCG@5）"""
        total_ndcg = 0.0

        for query, truth_ids in zip(queries, ground_truth):
            # 计算每个候选文档的得分
            scored = []
            for doc in candidate_pool:
                vs = doc.get("vector_score", 0.5)
                ks = self.compute_keyword_score(query, doc.get("content", ""))
                ts = self.compute_time_score(doc.get("created_at", ""))
                tgs = self.compute_tag_score(None, doc.get("tags", {}))
                score = self.fuse_scores(vs, ks, ts, tgs)
                scored.append((doc["doc_id"], score))

            # 排序
            scored.sort(key=lambda x: x[1], reverse=True)
            ranked_ids = [doc_id for doc_id, _ in scored[:5]]

            # 计算DCG
            dcg = 0.0
            for i, doc_id in enumerate(ranked_ids):
                rel = 1.0 if doc_id in truth_ids else 0.0
                dcg += rel / math.log2(i + 2)

            # 理想DCG
            ideal_dcg = 0.0
            for i in range(min(len(truth_ids), 5)):
                ideal_dcg += 1.0 / math.log2(i + 2)

            ndcg = dcg / ideal_dcg if ideal_dcg > 0 else 0.0
            total_ndcg += ndcg

        return total_ndcg / len(queries) if queries else 0.0

    # 英文停用词
    _STOPWORDS_EN = {
        "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
        "have", "has", "had", "do", "does", "did", "will", "would", "could",
        "should", "of", "to", "in", "on", "and", "or", "for", "with",
    }
    # 中文单字停用词(bigram 里若两字都是停用词则丢弃)
    _STOPWORDS_ZH = set("的了在是我有和就不人都一上也很到说要去你会着看好这那吗呢吧啊哦嗯")

    @staticmethod
    def _tokenize(text: str) -> List[str]:
        """分词:英文按单词,中文按字符 bigram(二元组)。

        中文不用词典分词(避免引入 jieba 依赖),改用相邻两字组合。
        这样"集装箱运价"→集装/装箱/箱运/运价,能与正文中的相同片段重叠匹配,
        让关键词维度对中文真正生效(此前整段中文被切成一个巨长 token,几乎无法命中)。
        """
        runs = re.findall(r"[一-鿿]+|[a-zA-Z]+", text.lower())
        tokens: List[str] = []
        for run in runs:
            if run[0].isascii():
                # 英文词:过滤停用词和单字母
                if run not in HybridSearch._STOPWORDS_EN and len(run) > 1:
                    tokens.append(run)
            else:
                # 中文:生成字符 bigram
                if len(run) == 1:
                    if run not in HybridSearch._STOPWORDS_ZH:
                        tokens.append(run)
                    continue
                for i in range(len(run) - 1):
                    bigram = run[i:i + 2]
                    # 两字都是停用词才丢弃
                    if not (bigram[0] in HybridSearch._STOPWORDS_ZH
                            and bigram[1] in HybridSearch._STOPWORDS_ZH):
                        tokens.append(bigram)
        return tokens


# 全局实例
hybrid_search = HybridSearch()
