"""混合相似度检索模块 - 核心创新

结合向量相似度、关键词匹配、时间衰减和标签匹配的加权融合模型。
数学系背景的优势体现：优化问题建模。
"""
import math
import re
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

import numpy as np

from ..core.config import config
from ..models.retrieval import DocumentTags, SearchResult


@dataclass(frozen=True)
class QueryProfile:
    """查询意图与当前候选集共同决定的排序策略。"""

    lexical_intent: float
    freshness_intent: float
    complexity: float
    weights: Dict[str, float]
    reliability: Dict[str, float]
    diversity_weight: float


@dataclass(frozen=True)
class RankingDecision:
    """排序结果及其可审计诊断信息。"""

    results: List[SearchResult]
    profile: QueryProfile
    confidence: float


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
            now = datetime.now(doc_time.tzinfo)
            days_diff = max(0, (now - doc_time).days)

            # 半衰期：30天
            half_life = 30
            score = math.exp(-0.693 * days_diff / half_life)
            return max(0.0, min(1.0, score))
        except Exception:
            return 0.5  # 默认中等得分

    @staticmethod
    def has_valid_timestamp(value: str) -> bool:
        if not value:
            return False
        try:
            datetime.fromisoformat(value.replace("Z", "+00:00"))
            return True
        except (TypeError, ValueError):
            return False

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

    def rank(
        self,
        hits: List[Dict[str, Any]],
        query: str,
        tag_filter: Optional[DocumentTags] = None,
        top_k: int = 5,
        diversify: bool = True,
    ) -> RankingDecision:
        """自适应地融合候选信号，并选择低冗余证据。

        时间信号只读取来源发布日期 ``published_at``。入库时间不代表内容
        新旧，因此不会被当作时效证据。
        """
        if not hits or top_k <= 0:
            profile = self._build_query_profile(query, tag_filter, [])
            return RankingDecision(results=[], profile=profile, confidence=0.0)

        prepared: List[Dict[str, Any]] = []
        for index, hit in enumerate(hits):
            published_at = str(hit.get("published_at") or "")
            tags = hit.get("tags", {})
            prepared.append({
                "index": index,
                "hit": hit,
                "vector": self.compute_vector_score(hit.get("distance", 0.5)),
                "lexical": self.compute_keyword_score(query, hit.get("content", "")),
                "temporal": self.compute_time_score(published_at),
                "temporal_valid": self.has_valid_timestamp(published_at),
                "tag": self.compute_tag_score(tag_filter, tags),
            })

        return self.rank_scored_candidates(
            prepared,
            query,
            tag_filter=tag_filter,
            top_k=top_k,
            diversify=diversify,
        )

    def rank_scored_candidates(
        self,
        prepared: List[Dict[str, Any]],
        query: str,
        tag_filter: Optional[DocumentTags] = None,
        top_k: int = 5,
        diversify: bool = True,
        adaptive: bool = True,
        missingness_gate: bool = True,
        rank_fusion_weight: float = 0.25,
    ) -> RankingDecision:
        """排序已计算四路信号的候选，供生产检索与离线实验共享。"""
        if not prepared or top_k <= 0:
            profile = self._build_query_profile(
                query, tag_filter, [], adaptive=adaptive, missingness_gate=missingness_gate,
            )
            return RankingDecision(results=[], profile=profile, confidence=0.0)

        profile = self._build_query_profile(
            query,
            tag_filter,
            prepared,
            adaptive=adaptive,
            missingness_gate=missingness_gate,
        )
        rank_scores = self._weighted_rrf(prepared, profile.weights)
        scored: List[SearchResult] = []
        for item in prepared:
            hit = item["hit"]
            calibrated = sum(
                profile.weights[name] * item[name]
                for name in ("vector", "lexical", "temporal", "tag")
            )
            fusion_weight = min(1.0, max(0.0, rank_fusion_weight))
            fused = (1.0 - fusion_weight) * calibrated + fusion_weight * rank_scores[item["index"]]
            tags = hit.get("tags", {})
            scored.append(
                SearchResult(
                    doc_id=hit.get("doc_id", ""),
                    chunk_id=hit.get("chunk_id", ""),
                    chunk_index=hit.get("chunk_index"),
                    title=hit.get("title", ""),
                    content=hit.get("content", ""),
                    url=hit.get("url", ""),
                    source_type=hit.get("source_type", ""),
                    start_idx=hit.get("start_idx"),
                    end_idx=hit.get("end_idx"),
                    line_start=hit.get("line_start"),
                    line_end=hit.get("line_end"),
                    score=round(fused, 4),
                    vector_score=round(item["vector"], 4),
                    keyword_score=round(item["lexical"], 4),
                    time_score=round(item["temporal"], 4) if item["temporal_valid"] else 0.0,
                    tag_score=round(item["tag"], 4) if profile.weights["tag"] else 0.0,
                    tags=DocumentTags(
                        business_type=tags.get("business_type", []),
                        geographic_region=tags.get("geographic_region", []),
                        topic_category=tags.get("topic_category", []),
                        event_nature=tags.get("event_nature", []),
                    ),
                )
            )

        scored.sort(key=lambda result: result.score, reverse=True)
        selected = self._select_diverse(scored, top_k, profile.diversity_weight) if diversify else scored[:top_k]
        return RankingDecision(
            results=selected,
            profile=profile,
            confidence=self._retrieval_confidence(scored, profile),
        )

    def _build_query_profile(
        self,
        query: str,
        tag_filter: Optional[DocumentTags],
        prepared: List[Dict[str, Any]],
        adaptive: bool = True,
        missingness_gate: bool = True,
    ) -> QueryProfile:
        lower = query.lower()
        cue_count = (
            len(re.findall(r"\b[A-Z]{2,}(?:[- ][A-Z0-9]+)*\b", query))
            + len(re.findall(r"\d+(?:[.-]\d+)*", query))
            + len(re.findall(r"[\"'“”‘’][^\"'“”‘’]+[\"'“”‘’]", query))
        )
        semantic_cues = re.findall(
            r"\b(?:why|how|impact|compare|relationship|challenge|effect)\b|为什么|如何|影响|比较|关系|原因|挑战",
            lower,
        )
        lexical_intent = min(1.0, max(0.0, 0.25 + 0.16 * cue_count - 0.08 * len(semantic_cues)))
        freshness_intent = 1.0 if re.search(
            r"\b(?:latest|recent|current|today|this week|newest|202[4-9])\b|最新|近期|当前|今天|本周|刚刚|新规",
            lower,
        ) else 0.0
        complexity_cues = re.findall(
            r"\b(?:and|versus|vs|compare|across|between|because|while)\b|以及|并且|比较|分别|之间|原因|同时|综合",
            lower,
        )
        complexity = min(1.0, len(complexity_cues) / 2.0)

        temporal_coverage = (
            sum(1 for item in prepared if item.get("temporal_valid")) / len(prepared)
            if prepared else 0.0
        )
        tag_requested = bool(tag_filter and any((
            tag_filter.business_type,
            tag_filter.geographic_region,
            tag_filter.topic_category,
            tag_filter.event_nature,
        )))
        reliability = {
            "vector": 1.0,
            "lexical": 1.0,
            "temporal": temporal_coverage if missingness_gate else 1.0,
            "tag": 1.0 if tag_requested else 0.0,
        }
        if adaptive:
            raw_weights = {
                "vector": self.vector_weight * (1.25 - 0.45 * lexical_intent),
                "lexical": self.keyword_weight * (1.0 + 1.8 * lexical_intent),
                "temporal": self.time_weight * (0.15 + 2.85 * freshness_intent),
                "tag": self.tag_weight * (2.5 if tag_requested else 0.0),
            }
        else:
            raw_weights = {
                "vector": self.vector_weight,
                "lexical": self.keyword_weight,
                "temporal": self.time_weight,
                "tag": self.tag_weight if tag_requested else 0.0,
            }
        gated = {name: raw_weights[name] * reliability[name] for name in raw_weights}
        total = sum(gated.values())
        weights = (
            {name: value / total for name, value in gated.items()}
            if total > 0 else {"vector": 0.5, "lexical": 0.5, "temporal": 0.0, "tag": 0.0}
        )
        return QueryProfile(
            lexical_intent=round(lexical_intent, 4),
            freshness_intent=freshness_intent,
            complexity=round(complexity, 4),
            weights={name: round(value, 6) for name, value in weights.items()},
            reliability={name: round(value, 6) for name, value in reliability.items()},
            diversity_weight=round(0.12 + 0.16 * complexity, 4),
        )

    @staticmethod
    def _weighted_rrf(
        prepared: List[Dict[str, Any]],
        weights: Dict[str, float],
        rank_constant: int = 60,
    ) -> Dict[int, float]:
        fused = {item["index"]: 0.0 for item in prepared}
        max_score = sum(weight / (rank_constant + 1) for weight in weights.values())
        for signal, weight in weights.items():
            if weight <= 0:
                continue
            eligible = [
                item for item in prepared
                if signal != "temporal" or item.get("temporal_valid")
            ]
            eligible.sort(key=lambda item: (item[signal], -item["index"]), reverse=True)
            for rank, item in enumerate(eligible, start=1):
                fused[item["index"]] += weight / (rank_constant + rank)
        if max_score > 0:
            fused = {index: min(1.0, value / max_score) for index, value in fused.items()}
        return fused

    def _select_diverse(
        self,
        ranked: List[SearchResult],
        top_k: int,
        diversity_weight: float,
    ) -> List[SearchResult]:
        if len(ranked) <= 1:
            return ranked[:top_k]
        selected = [ranked[0]]
        remaining = ranked[1:]
        while remaining and len(selected) < top_k:
            best = max(
                remaining,
                key=lambda candidate: self._diversity_objective(
                    candidate, selected, diversity_weight,
                ),
            )
            selected.append(best)
            remaining.remove(best)
        return selected

    def _diversity_objective(
        self,
        candidate: SearchResult,
        selected: List[SearchResult],
        diversity_weight: float,
    ) -> float:
        candidate_tokens = set(self._tokenize(candidate.content))
        max_similarity = 0.0
        same_document = False
        for existing in selected:
            existing_tokens = set(self._tokenize(existing.content))
            union = candidate_tokens | existing_tokens
            similarity = len(candidate_tokens & existing_tokens) / len(union) if union else 0.0
            max_similarity = max(max_similarity, similarity)
            same_document = same_document or bool(candidate.doc_id and candidate.doc_id == existing.doc_id)
        redundancy_penalty = 0.08 if same_document else 0.0
        return (
            (1.0 - diversity_weight) * candidate.score
            + diversity_weight * (1.0 - max_similarity)
            - redundancy_penalty
        )

    @staticmethod
    def _retrieval_confidence(ranked: List[SearchResult], profile: QueryProfile) -> float:
        if not ranked:
            return 0.0
        top = ranked[0].score
        margin = top - ranked[1].score if len(ranked) > 1 else top
        reliability = sum(
            profile.weights[name] * profile.reliability[name]
            for name in profile.weights
        )
        confidence = 0.65 * top + 0.2 * min(1.0, max(0.0, margin) / 0.15) + 0.15 * reliability
        return round(min(1.0, max(0.0, confidence)), 4)

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
