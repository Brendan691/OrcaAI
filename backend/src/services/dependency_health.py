"""本地 sidecar 依赖健康探测。

线上检索依赖两个本地 sidecar：编码(8765)与重排(8766)。

- 编码不可用时检索会直接失败（`embedding_service` 不静默降级）。
- 重排不可用时 CARE 会回退 AEF（`used=False`），检索仍可用。

因此在启动和 `/health` 中显式暴露两者状态，避免"首个请求才发现 sidecar 没起"。
只探测回环地址；远程托管端点不在启动时主动打点。
"""
from __future__ import annotations

import logging
from urllib.parse import urlsplit, urlunsplit

import httpx

from ..core.config import config

logger = logging.getLogger("orcaai.dependencies")

PROBE_TIMEOUT_SECONDS = 1.5
_LOOPBACK_HOSTS = {"127.0.0.1", "localhost", "::1"}


def _is_loopback(url: str) -> bool:
    try:
        return (urlsplit(url).hostname or "") in _LOOPBACK_HOSTS
    except ValueError:
        return False


def _health_url(endpoint: str) -> str:
    parts = urlsplit(endpoint)
    return urlunsplit((parts.scheme, parts.netloc, "/health", "", ""))


def _probe(name: str, endpoint: str, *, required: bool) -> dict:
    url = _health_url(endpoint)
    try:
        response = httpx.get(url, timeout=PROBE_TIMEOUT_SECONDS)
        response.raise_for_status()
        payload = response.json()
    except Exception as exc:  # noqa: BLE001 - 探测失败原因需要原样上报
        return {
            "name": name,
            "status": "down",
            "required": required,
            "url": url,
            "detail": f"{type(exc).__name__}: {exc}",
        }
    return {
        "name": name,
        "status": "ok",
        "required": required,
        "url": url,
        "detail": payload.get("version") or payload.get("status") or "ok",
    }


def probe_dependencies() -> dict:
    """探测当前配置下真正需要的 sidecar，返回可直接序列化的状态。"""
    services: dict[str, dict] = {}

    if config.EMBEDDING_BACKEND == "local":
        services["embedding"] = _probe(
            "embedding", config.EMBEDDING_ENDPOINT, required=True
        )
    else:
        services["embedding"] = {
            "name": "embedding",
            "status": "skipped",
            "required": False,
            "detail": f"backend={config.EMBEDDING_BACKEND}",
        }

    if config.RERANK_ENABLED and _is_loopback(config.DASHSCOPE_RERANK_ENDPOINT):
        services["rerank"] = _probe(
            "rerank", config.DASHSCOPE_RERANK_ENDPOINT, required=False
        )
    else:
        services["rerank"] = {
            "name": "rerank",
            "status": "skipped",
            "required": False,
            "detail": "remote endpoint or rerank disabled",
        }

    ready = all(
        service["status"] == "ok"
        for service in services.values()
        if service["required"]
    )
    return {"ready": ready, "services": services}


def log_startup_report() -> dict:
    """启动时打印一次依赖状态。不抛错：编码不可用留给首个请求暴露。"""
    report = probe_dependencies()
    summary = ", ".join(
        f"{name}={service['status']}"
        for name, service in report["services"].items()
    )
    print(f"[startup] dependencies ready={report['ready']} ({summary})", flush=True)
    for service in report["services"].values():
        if service["status"] == "ok":
            logger.info(
                "sidecar %s 可用 (%s)", service["name"], service["detail"]
            )
        elif service["status"] == "down":
            log = logger.error if service["required"] else logger.warning
            log(
                "sidecar %s 不可用 (%s): %s",
                service["name"],
                service["url"],
                service["detail"],
            )
    if not report["ready"]:
        logger.error(
            "必需依赖未就绪：编码 sidecar 不可用时检索会直接失败，"
            "请先启动约定端口上的 sidecar"
        )
    return report
