"""报告发布日期由程序确定，不能交给模型推断。"""

from datetime import date

from src.services.report_generator import (
    ensure_report_date,
    format_report_date,
    normalize_report_citations,
)


def test_format_report_date_uses_correct_chinese_weekday():
    assert format_report_date(date(2026, 7, 31)) == "2026年7月31日（星期五）"


def test_ensure_report_date_corrects_model_weekday():
    content = "# 《周度航运市场简报》\n\n发布日期：2026年7月31日（星期四）\n\n## 本周运价"

    corrected = ensure_report_date(content, date(2026, 7, 31))

    assert "发布日期：2026年7月31日（星期五）" in corrected
    assert "星期四" not in corrected


def test_ensure_report_date_adds_missing_publication_date():
    corrected = ensure_report_date("## 本周运价", date(2026, 7, 31))

    assert corrected.startswith("**发布日期：2026年7月31日（星期五）**")


def test_normalize_report_citations_assigns_unique_numbers_by_url():
    content = (
        "运价上涨[3](https://example.com/rates)，"
        "港口拥堵[1](https://example.com/ports)，"
        "运价仍高[2](https://example.com/rates)。"
    )

    normalized = normalize_report_citations(content)

    assert normalized == (
        "运价上涨[1](https://example.com/rates)，"
        "港口拥堵[2](https://example.com/ports)，"
        "运价仍高[1](https://example.com/rates)。"
    )
