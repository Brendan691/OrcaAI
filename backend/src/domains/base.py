"""领域包接口(见 ADR-0003)。

一个 DomainPack 封装某个行业的全部领域知识。内核只依赖这个接口,
不认识任何具体行业。换一个领域包 = 换一个行业,内核代码不动。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

import yaml


@dataclass(frozen=True)
class TagDimension:
    """一个标签维度,如"业务类型"。"""
    name: str            # 机器名,如 business_type
    display_name: str    # 显示名,如 业务类型
    values: list[str]    # 该维度下的所有标签值


@dataclass(frozen=True)
class ReportType:
    """一种可生成的报告,如"周度航运市场简报"。"""
    id: str
    name: str
    system_prompt: str
    search_queries: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class DomainPack:
    """领域包:某行业知识的完整封装。

    - dimensions: 标签体系(四维等)
    - classification_prompt: 让 LLM 打标签的提示词模板
    - qa_system_prompt: 问答时给 LLM 的系统提示词(定义"你是谁")
    - keyword_rules: {维度名: {标签值: [关键词...]}},LLM 失败时的规则回退
    - report_types: 可生成的报告类型
    """
    name: str
    display_name: str
    dimensions: list[TagDimension]
    classification_prompt: str
    qa_system_prompt: str
    keyword_rules: dict[str, dict[str, list[str]]]
    report_types: dict[str, ReportType]

    def dimensions_as_dict(self) -> dict[str, dict]:
        """给 /api/tags 用的序列化形式。"""
        return {
            d.name: {"display_name": d.display_name, "values": d.values}
            for d in self.dimensions
        }


def load_dimensions_from_yaml(yaml_path: Path) -> list[TagDimension]:
    """从 tags.yaml 读取标签维度。领域包共用的辅助函数。"""
    with open(yaml_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return [
        TagDimension(name=d["name"], display_name=d["display_name"], values=d["values"])
        for d in data.get("dimensions", [])
    ]


# 领域包工厂类型:每个领域的 __init__ 暴露一个 build() 返回 DomainPack
DomainBuilder = Callable[[], DomainPack]
