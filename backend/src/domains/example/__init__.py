"""示例领域包 —— 证明"换领域包即换行业"(见 ADR-0003)。

这是一个最小骨架:把 ACTIVE_DOMAIN 设为 example 即可切换。
想接入新行业(法律/医药/金融),照此结构填内容即可,内核无需改动。
"""
from ..base import DomainPack, ReportType, TagDimension


def build() -> DomainPack:
    dimensions = [
        TagDimension(
            name="business_type",
            display_name="类型",
            values=["类型A", "类型B", "类型C"],
        ),
        TagDimension(
            name="topic_category",
            display_name="主题",
            values=["主题一", "主题二"],
        ),
    ]
    keyword_rules = {
        d.name: {v: [v] for v in d.values} for d in dimensions
    }
    return DomainPack(
        name="example",
        display_name="示例领域",
        dimensions=dimensions,
        classification_prompt=(
            "请阅读内容并分类。\n"
            "类型：{business_type_list}\n主题：{topic_category_list}\n"
            "内容：{content}\n以 JSON 返回。"
        ),
        qa_system_prompt="你是一个通用知识助手,基于参考资料回答问题,不编造。",
        keyword_rules=keyword_rules,
        report_types={
            "summary": ReportType(
                id="summary", name="内容摘要报告",
                system_prompt="根据参考资料生成一份内容摘要。",
                search_queries=["最新动态"],
            )
        },
    )
