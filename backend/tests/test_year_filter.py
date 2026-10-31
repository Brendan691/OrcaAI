"""时间元数据软约束过滤的回归测试（对应静默丢弃缺陷）。"""
from src.services.retrieval_context import (
    apply_time_boost, ensure_time_coverage, time_weight_for, evidence_time_note,
)


class Hit:
    def __init__(self, doc_id, year, score):
        self.doc_id, self.year, self.score = doc_id, year, score


def test_weights_follow_spec():
    assert time_weight_for(2023, 2023) == 1.5
    assert time_weight_for(2022, 2023) == 1.2
    assert time_weight_for(2021, 2023) == 1.0
    assert time_weight_for(2025, 2023) == 1.0
    assert time_weight_for(2019, 2023) == 0.6
    assert time_weight_for(None, 2023) == 0.8
    assert time_weight_for(2023, None) == 1.0


def test_no_hard_filter_and_unknown_never_displaces_known():
    # 缺年文档原始得分最高，重排后必须落到有年文档之后
    hits = [Hit("d2021", 2021, 0.75), Hit("d2025", 2025, 0.74), Hit("dNone", None, 0.90)]
    ranked = apply_time_boost(hits, 2023)
    assert [h.doc_id for h in ranked] == ["d2021", "d2025", "dNone"]
    assert ranked[-1].temporal_fallback is True
    assert len(ranked) == 3, "不得丢弃任何文档"


def test_coverage_prefers_known_years_then_fills_with_unknown():
    hits = [Hit("d2021", 2021, 0.75), Hit("d2025", 2025, 0.74), Hit("dNone", None, 0.90)]
    ranked = apply_time_boost(hits, 2023)
    top3 = ensure_time_coverage(ranked, 2023, top_k=3)
    assert [h.doc_id for h in top3] == ["d2021", "d2025", "dNone"]
    # Top-K 不足时用缺年补齐
    hits2 = [Hit("a", 2021, 0.5), Hit("b", None, 0.4), Hit("c", None, 0.3)]
    top3b = ensure_time_coverage(apply_time_boost(hits2, 2023), 2023, top_k=3)
    assert len(top3b) == 3 and top3b[0].doc_id == "a"


def test_query_without_year_keeps_order():
    hits = [Hit("a", 2021, 0.5), Hit("b", None, 0.4)]
    ranked = apply_time_boost(hits, None)
    assert [h.doc_id for h in ranked] == ["a", "b"]


def test_evidence_note_flags_missing_time():
    assert evidence_time_note(None) == "此证据未标注发布时间"
    assert evidence_time_note(2023) == "该证据发布时间：2023 年"
