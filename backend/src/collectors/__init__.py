"""采集器注册表(见 ADR-0004)。

按注册顺序选择第一个 can_handle 命中的采集器 —— 专用采集器排在通用之前。
未来新增小红书/抖音采集器:实现 Collector,在 _REGISTRY 前部注册一行即可。
"""
from .base import Collector, RawDocument
from .web import WebCollector, WechatArticleCollector

# 顺序有意义:专用在前,通用兜底在后
_REGISTRY: list[Collector] = [
    WechatArticleCollector(),   # 公众号文章(专用)
    WebCollector(),             # 任意网页(兜底)
    # 未来:XiaohongshuCollector(), DouyinCollector() ...
]


def get_collector(source: str) -> Collector | None:
    """按来源选择合适的采集器,选不到返回 None。"""
    for c in _REGISTRY:
        if c.can_handle(source):
            return c
    return None


def collect(source: str) -> RawDocument:
    """采集入口:选采集器并产出 RawDocument。选不到则抛错。"""
    c = get_collector(source)
    if c is None:
        raise ValueError(f"没有可处理该来源的采集器: {source}")
    return c.collect(source)


__all__ = ["collect", "get_collector", "Collector", "RawDocument"]
