"""标签分类服务 —— LLM 优先 + 规则引擎兜底。

领域无关:所有航运知识(标签、提示词、关键词)都来自当前领域包(见 ADR-0003),
本文件只负责"怎么分类"的通用逻辑,不含任何行业专有内容。
"""
import json
import re

from openai import OpenAI

from ..core.config import config
from ..domains import get_active_domain
from ..models.document import DocumentTags


class TagClassifier:
    """按当前领域包的维度,给文档打标签。"""

    def __init__(self):
        self.model = config.CHAT_MODEL
        self._client = None
        self.domain = get_active_domain()
        # 维度名 -> 该维度所有标签值(供解析与校验)
        self.dimensions = self.domain.dimensions_as_dict()
        self.keyword_rules = self.domain.keyword_rules

    @property
    def client(self):
        """延迟创建 LLM 客户端,避免无 API Key 时 import 失败。"""
        if self._client is None:
            self._client = OpenAI(
                api_key=config.DASHSCOPE_API_KEY,
                base_url=config.DASHSCOPE_BASE_URL,
            )
        return self._client

    def classify(self, content: str, use_llm: bool = True) -> DocumentTags:
        """分类入口:优先 LLM,失败或无 Key 时回退规则引擎。"""
        if use_llm and config.has_api_key:
            try:
                return self.classify_with_llm(content)
            except Exception as e:
                print(f"LLM 分类失败,回退规则引擎: {e}")
                return self.classify_with_rules(content)
        return self.classify_with_rules(content)

    def classify_with_llm(self, content: str) -> DocumentTags:
        """用 LLM 从各维度分类,解析 JSON 结果。"""
        prompt = self.domain.classification_prompt.format(
            business_type_list="\n".join(f"  - {v}" for v in self.dimensions.get("business_type", {}).get("values", [])),
            geographic_region_list="\n".join(f"  - {v}" for v in self.dimensions.get("geographic_region", {}).get("values", [])),
            topic_category_list="\n".join(f"  - {v}" for v in self.dimensions.get("topic_category", {}).get("values", [])),
            event_nature_list="\n".join(f"  - {v}" for v in self.dimensions.get("event_nature", {}).get("values", [])),
            content=content[:2000],
        )
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": "你是一个专业的分类专家。请严格按照JSON格式输出。"},
                {"role": "user", "content": prompt},
            ],
            temperature=0.1,
            max_tokens=500,
        )
        result_text = response.choices[0].message.content
        try:
            m = re.search(r"\{.*\}", result_text, re.DOTALL)
            if m:
                result_text = m.group()
            result = json.loads(result_text)
            return DocumentTags(
                business_type=result.get("business_type", []),
                geographic_region=result.get("geographic_region", []),
                topic_category=result.get("topic_category", []),
                event_nature=result.get("event_nature", []),
                confidence=result.get("confidence", 0.0),
            )
        except Exception as e:
            print(f"LLM 结果解析失败,回退规则引擎: {e}")
            return self.classify_with_rules(content)

    def classify_with_rules(self, content: str) -> DocumentTags:
        """规则引擎:关键词命中即打标,每维度最多 3 个。"""
        content_lower = content.lower()
        tags = DocumentTags()
        matched_by_dim: dict[str, list[str]] = {}

        for dim_name, tag_rules in self.keyword_rules.items():
            matched = []
            for tag_value, keywords in tag_rules.items():
                if any(kw.lower() in content_lower for kw in keywords):
                    matched.append(tag_value)
            matched_by_dim[dim_name] = matched[:3]

        tags.business_type = matched_by_dim.get("business_type", [])
        tags.geographic_region = matched_by_dim.get("geographic_region", [])
        tags.topic_category = matched_by_dim.get("topic_category", [])
        tags.event_nature = matched_by_dim.get("event_nature", [])

        total = sum(len(v) for v in matched_by_dim.values())
        tags.confidence = min(total / 8, 1.0)
        return tags


# 全局实例
tag_classifier = TagClassifier()
