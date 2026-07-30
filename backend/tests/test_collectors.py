"""采集器注册表测试 —— 覆盖 ADR-0004。

只测"选择逻辑"(不联网):公众号链接走专用采集器,普通网页走通用采集器。
"""
from src.collectors import get_collector
from src.collectors.web import WebCollector, WechatArticleCollector


def test_wechat_url_selects_wechat_collector():
    c = get_collector("https://mp.weixin.qq.com/s/abc123")
    assert isinstance(c, WechatArticleCollector)
    assert c.source_type == "wechat"


def test_generic_url_selects_web_collector():
    c = get_collector("https://example.com/news/article")
    assert isinstance(c, WebCollector)
    assert c.source_type == "web"


def test_non_url_selects_nothing():
    assert get_collector("这不是一个链接") is None


def test_wechat_collector_can_handle():
    wc = WechatArticleCollector()
    assert wc.can_handle("https://mp.weixin.qq.com/s/xyz")
    assert not wc.can_handle("https://baidu.com")
