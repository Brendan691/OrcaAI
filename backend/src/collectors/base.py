"""采集器接口(见 ADR-0004)。

一个 Collector 把"某来源的原始输入(URL/文件/未来的小红书分享等)"
转换成标准的 RawDocument。入库管线(切片→向量化→标签→存储)对所有采集器共用。

加一个新平台 = 新增一个实现 Collector 的类 + 在 registry 注册一行,入库管线不动。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable


@dataclass
class RawDocument:
    """采集器的统一产出:一份待入库的原始文档。"""
    title: str
    content: str
    source_url: str = ""
    source_type: str = "web"   # web / wechat / file / xiaohongshu / douyin ...
    extra: dict = field(default_factory=dict)


@runtime_checkable
class Collector(Protocol):
    """采集器协议。任何来源的采集器都实现这两个方法。"""

    #: 来源类型标识,如 "web" / "wechat"
    source_type: str

    def can_handle(self, source: str) -> bool:
        """能否处理这个来源(通常按 URL 特征判断)。"""
        ...

    def collect(self, source: str) -> RawDocument:
        """把来源抓取/解析成 RawDocument。"""
        ...
