"""网页采集器 —— 通用网页 + 微信公众号文章专用提取。

- WebCollector:兜底,能处理任意 http(s) 链接(复用 document_processor 的抓取)。
- WechatArticleCollector:专门识别公众号文章链接(mp.weixin.qq.com),
  按公众号页面结构精准提取标题与正文。这是"多平台采集"的第一个专用采集器 demo。
"""
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

from ..services.document_processor import document_processor
from .base import RawDocument

_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


class WebCollector:
    """通用网页采集器(兜底)。"""
    source_type = "web"

    def can_handle(self, source: str) -> bool:
        return source.startswith("http://") or source.startswith("https://")

    def collect(self, source: str) -> RawDocument:
        title, content = document_processor.fetch_webpage(source)
        return RawDocument(title=title, content=content, source_url=source, source_type="web")


class WechatArticleCollector:
    """微信公众号文章采集器(专用提取,见 ADR-0004 / ROADMAP)。

    公众号文章是公开网页,标题在 #activity-name,正文在 #js_content。
    通用抓取也能拿到内容,但专用提取更干净(去掉推荐、赞赏等噪音)。
    """
    source_type = "wechat"

    def can_handle(self, source: str) -> bool:
        try:
            host = urlparse(source).netloc
        except Exception:
            return False
        return "mp.weixin.qq.com" in host

    def collect(self, source: str) -> RawDocument:
        resp = requests.get(source, headers={"User-Agent": _UA}, timeout=30)
        resp.raise_for_status()
        resp.encoding = resp.apparent_encoding
        soup = BeautifulSoup(resp.text, "html.parser")

        title_el = soup.select_one("#activity-name")
        title = title_el.get_text(strip=True) if title_el else (
            soup.title.string.strip() if soup.title and soup.title.string else "公众号文章"
        )
        content_el = soup.select_one("#js_content")
        if content_el:
            for tag in content_el(["script", "style"]):
                tag.decompose()
            content = content_el.get_text(separator="\n", strip=True)
        else:
            # 结构变化时回退到通用抓取
            _, content = document_processor.fetch_webpage(source)

        author_el = soup.select_one("#js_name")
        extra = {"author": author_el.get_text(strip=True)} if author_el else {}
        return RawDocument(
            title=title, content=document_processor._clean_text(content),
            source_url=source, source_type="wechat", extra=extra,
        )
