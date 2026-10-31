"""Shared maritime query intent contract tests."""

from src.services.query_intent import QueryIntentAnalyzer


def test_d07_style_question_preserves_original_and_expands_synonyms():
    intent = QueryIntentAnalyzer().analyze(
        "中国海员心理健康水平是否明显低于常人？",
        current_year=2026,
    )

    assert intent.original == "中国海员心理健康水平是否明显低于常人？"
    assert intent.normalized == "中国船员心理健康水平是否明显低于常人？"
    assert intent.freshness_intent == "implicit"
    assert intent.temporal_scope == "current"
    assert intent.conflict_sensitive is True
    assert [variant.rule for variant in intent.variants] == [
        "original",
        "maritime-synonym",
        "neutral-recency",
    ]
    assert intent.variants[-1].text.endswith("最新年度报告")


def test_explicit_freshness_is_detected_without_synonym_change():
    intent = QueryIntentAnalyzer().analyze("目前碳价是多少？", current_year=2026)

    assert intent.normalized == intent.original
    assert intent.freshness_intent == "explicit"
    assert intent.conflict_sensitive is True
    assert intent.web_queries[-1] == "目前碳价是多少？ 最新年度报告"


def test_progress_question_gets_neutral_recency_variant():
    intent = QueryIntentAnalyzer().analyze(
        "STCW公约全面审查进展到哪一步？",
        current_year=2026,
    )

    assert intent.freshness_intent == "explicit"
    assert intent.conflict_sensitive is True
    assert intent.web_queries[-1].endswith("最新年度报告")


def test_execution_status_question_gets_recency_variant():
    intent = QueryIntentAnalyzer().analyze(
        "FuelEU首个合规年的实际执行情况如何？",
        current_year=2026,
    )

    assert intent.freshness_intent == "explicit"
    assert intent.conflict_sensitive is True
    assert intent.web_queries[-1].endswith("最新年度报告")


def test_historical_year_suppresses_recency_variant():
    intent = QueryIntentAnalyzer().analyze(
        "2010年海员心理健康研究说了什么？",
        current_year=2026,
    )

    assert intent.freshness_intent == "none"
    assert intent.temporal_scope == "historical"
    assert intent.conflict_sensitive is False
    assert [variant.rule for variant in intent.variants] == [
        "original",
        "maritime-synonym",
    ]


def test_timeless_query_has_only_original_variant():
    intent = QueryIntentAnalyzer().analyze("MARPOL附则是什么？", current_year=2026)

    assert intent.normalized == intent.original
    assert intent.freshness_intent == "none"
    assert intent.temporal_scope == "timeless"
    assert intent.web_queries == ("MARPOL附则是什么？",)


def test_analysis_is_deterministic_and_exposes_equivalent_terms():
    analyzer = QueryIntentAnalyzer()
    first = analyzer.analyze("海员心理健康", current_year=2026)
    second = analyzer.analyze("海员心理健康", current_year=2026)

    assert first == second
    assert analyzer.equivalent_terms("海员") == ("海员", "船员")
    assert analyzer.equivalent_terms("船员") == ("海员", "船员")
    assert analyzer.equivalent_terms("港口") == ("港口",)
    assert analyzer.synonym_variants("海员心理健康") == (
        "海员心理健康",
        "船员心理健康",
    )
