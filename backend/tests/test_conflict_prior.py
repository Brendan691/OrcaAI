"""Conflict authority/freshness prior tests."""

from src.services.conflict_prior import assess_conflict_prior, extract_year
from src.services.query_intent import QueryIntentAnalyzer


def test_new_annual_report_outranks_old_academic_paper():
    intent = QueryIntentAnalyzer().analyze(
        "中国海员心理健康水平是否明显低于常人？",
        current_year=2026,
    )
    old = assess_conflict_prior(
        title="中国海员心理健康状况及其影响因素",
        text="2010年研究。海员心理健康水平明显低于常模。",
        url="https://skxb.jsu.edu.cn/paper.pdf",
        published_at=None,
        base_score=0.99,
        intent=intent,
        current_year=2026,
    )
    report = assess_conflict_prior(
        title="2024年度中国船员心理健康报告：4.9%的船员存在心理风险",
        text="心理风险4.9%，异常0.4%，低于常模8%/2%。",
        url="http://psy.china.com.cn/2024-11/27/content_1.htm",
        published_at="2024-11-27",
        base_score=0.82,
        intent=intent,
        current_year=2026,
    )

    assert report.year == 2024
    assert report.authority_score > old.authority_score
    assert report.recency_score > old.recency_score
    assert report.final_score > old.final_score


def test_prior_is_not_applied_to_historical_questions():
    intent = QueryIntentAnalyzer().analyze(
        "2010年海员心理健康研究说了什么？",
        current_year=2026,
    )
    assessment = assess_conflict_prior(
        title="2024年度报告",
        text="最新数据",
        url="https://example.com/report",
        published_at="2024-01-01",
        base_score=0.8,
        intent=intent,
        current_year=2026,
    )

    assert assessment.applied is False
    assert assessment.final_score == 0.8


def test_missing_date_is_not_treated_as_current():
    intent = QueryIntentAnalyzer().analyze("当前船舶碳价是多少？", current_year=2026)
    assessment = assess_conflict_prior(
        title="Carbon pricing",
        text="No timestamp.",
        url="https://example.com/note",
        published_at=None,
        base_score=0.7,
        intent=intent,
        current_year=2026,
    )

    assert assessment.year is None
    assert assessment.recency_score == 0.4
    assert "missing-year" in assessment.reasons


def test_year_prefers_published_metadata_then_content():
    assert extract_year("Old study", "published 2010", published_at="2024-11-27") == 2024
    assert extract_year("Old study", "published 2010", published_at=None) == 2010
    assert extract_year(
        "2024年度报告",
        "到2030年覆盖率将提高",
        published_at=None,
    ) == 2024


def test_world_bank_chinese_mirror_is_treated_as_authoritative_report():
    intent = QueryIntentAnalyzer().analyze(
        "全球碳定价机制数量和覆盖率是多少？",
        current_year=2026,
    )
    assessment = assess_conflict_prior(
        title="《2026年碳定价的发展现状与未来趋势》",
        text="全球已实施碳定价政策87项，覆盖率约29%。",
        url="https://www.shihang.org/zh/news/press-release/2026/05/19/report",
        published_at=None,
        base_score=0.6,
        intent=intent,
        current_year=2026,
    )

    assert assessment.year == 2026
    assert assessment.authority_score == 1.0
    assert "official-host" in assessment.reasons
    assert "annual-report-title" in assessment.reasons
