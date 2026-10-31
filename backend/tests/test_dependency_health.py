"""本地 sidecar 依赖健康探测。"""

import httpx

from src.core.config import config
from src.services import dependency_health as health


class _Response:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


def test_health_url_and_loopback_detection():
    assert (
        health._health_url("http://127.0.0.1:8765/embed")
        == "http://127.0.0.1:8765/health"
    )
    assert health._is_loopback("http://localhost:8766/rerank")
    assert health._is_loopback("http://[::1]:8766/rerank")
    assert not health._is_loopback("https://dashscope.aliyuncs.com/api/v1")


def test_local_backends_report_ready(monkeypatch):
    monkeypatch.setattr(config, "EMBEDDING_BACKEND", "local")
    monkeypatch.setattr(config, "EMBEDDING_ENDPOINT", "http://127.0.0.1:8765/embed")
    monkeypatch.setattr(config, "RERANK_ENABLED", True)
    monkeypatch.setattr(
        config, "DASHSCOPE_RERANK_ENDPOINT", "http://127.0.0.1:8766/rerank"
    )
    monkeypatch.setattr(
        health.httpx,
        "get",
        lambda url, timeout: _Response({"status": "ok", "version": "v1"}),
    )

    report = health.probe_dependencies()

    assert report["ready"] is True
    assert report["services"]["embedding"]["status"] == "ok"
    assert report["services"]["embedding"]["detail"] == "v1"
    assert report["services"]["rerank"]["status"] == "ok"


def test_missing_embedding_sidecar_marks_not_ready(monkeypatch):
    monkeypatch.setattr(config, "EMBEDDING_BACKEND", "local")
    monkeypatch.setattr(config, "EMBEDDING_ENDPOINT", "http://127.0.0.1:9099/embed")
    monkeypatch.setattr(config, "RERANK_ENABLED", False)

    def _fail(url, timeout):
        raise httpx.ConnectError("connection refused")

    monkeypatch.setattr(health.httpx, "get", _fail)

    report = health.probe_dependencies()

    assert report["ready"] is False
    assert report["services"]["embedding"]["status"] == "down"
    assert report["services"]["embedding"]["required"] is True
    assert "ConnectError" in report["services"]["embedding"]["detail"]


def test_rerank_down_does_not_block_readiness(monkeypatch):
    """重排不可用时 CARE 会回退 AEF，不应把整体判为未就绪。"""
    monkeypatch.setattr(config, "EMBEDDING_BACKEND", "local")
    monkeypatch.setattr(config, "EMBEDDING_ENDPOINT", "http://127.0.0.1:8765/embed")
    monkeypatch.setattr(config, "RERANK_ENABLED", True)
    monkeypatch.setattr(
        config, "DASHSCOPE_RERANK_ENDPOINT", "http://127.0.0.1:9099/rerank"
    )

    def _get(url, timeout):
        if url.endswith(":8765/health"):
            return _Response({"status": "ok"})
        raise httpx.ConnectError("connection refused")

    monkeypatch.setattr(health.httpx, "get", _get)

    report = health.probe_dependencies()

    assert report["ready"] is True
    assert report["services"]["rerank"]["status"] == "down"
    assert report["services"]["rerank"]["required"] is False


def test_remote_or_disabled_backends_are_skipped(monkeypatch):
    monkeypatch.setattr(config, "EMBEDDING_BACKEND", "dashscope")
    monkeypatch.setattr(config, "RERANK_ENABLED", True)
    monkeypatch.setattr(
        config,
        "DASHSCOPE_RERANK_ENDPOINT",
        "https://dashscope.aliyuncs.com/api/v1/services/rerank/text-rerank/text-rerank",
    )

    def _unexpected(*args, **kwargs):
        raise AssertionError("远程端点不应在健康探测中被访问")

    monkeypatch.setattr(health.httpx, "get", _unexpected)

    report = health.probe_dependencies()

    assert report["ready"] is True
    assert report["services"]["embedding"]["status"] == "skipped"
    assert report["services"]["rerank"]["status"] == "skipped"
