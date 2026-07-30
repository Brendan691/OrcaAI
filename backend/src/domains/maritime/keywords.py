"""航运领域的关键词规则。

当 LLM 不可用(没有 API Key 或调用失败)时,规则引擎用这些关键词做兜底分类。
只列出有同义词/简称的标签;未列出的标签用其名字本身做关键词。
"""

# {标签值: [额外关键词/同义词]}
# 分类器会自动把"标签值本身"也作为关键词,这里只补充同义词。
SYNONYMS: dict[str, list[str]] = {
    "集装箱运输": ["集装箱", "箱运", "container"],
    "散货运输": ["散货", "bulk"],
    "油轮运输": ["油轮", "油船", "原油", "tanker"],
    "运价波动": ["运价", "运费", "费率", "price"],
    "港口拥堵": ["拥堵", "堵塞", "congestion"],
    "碳排放政策": ["碳排放", "碳中和", "绿色航运", "低碳", "碳税"],
    "船舶碰撞": ["碰撞", "撞船", "collision"],
    "罢工影响": ["罢工", "停工", "strike"],
    "法规更新": ["法规", "法律", "新规", "regulation"],
    "远东": ["中国", "日本", "韩国", "东亚"],
    "中国沿海": ["上海", "宁波", "深圳", "广州", "天津", "青岛", "大连", "厦门"],
    "欧洲": ["欧盟", "EU", "Europe"],
    "北美东海岸": ["美国", "加拿大", "北美", "USA"],
}


def build_keyword_rules(dimensions) -> dict[str, dict[str, list[str]]]:
    """为每个维度的每个标签构建关键词列表。

    规则:标签值本身 + SYNONYMS 里登记的同义词。
    """
    rules: dict[str, dict[str, list[str]]] = {}
    for dim in dimensions:
        rules[dim.name] = {}
        for value in dim.values:
            keywords = [value]
            keywords.extend(SYNONYMS.get(value, []))
            rules[dim.name][value] = keywords
    return rules
