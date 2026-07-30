"""航运领域包(见 ADR-0003)。

把标签(tags.yaml)、提示词(prompts.py)、关键词(keywords.py)、
报告模板(reports.py)组装成一个 DomainPack。
"""
from pathlib import Path

from ..base import DomainPack, load_dimensions_from_yaml
from . import keywords, prompts, reports

_TAGS_YAML = Path(__file__).parent / "tags.yaml"


def build() -> DomainPack:
    dimensions = load_dimensions_from_yaml(_TAGS_YAML)
    return DomainPack(
        name="maritime",
        display_name="海事航运",
        dimensions=dimensions,
        classification_prompt=prompts.CLASSIFICATION_PROMPT,
        qa_system_prompt=prompts.QA_SYSTEM_PROMPT,
        keyword_rules=keywords.build_keyword_rules(dimensions),
        report_types=reports.REPORT_TYPES,
    )
