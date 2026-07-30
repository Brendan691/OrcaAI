"""领域包加载器(见 ADR-0003)。

内核通过 get_active_domain() 拿到当前领域包,不直接 import 具体领域。
当前激活哪个领域由 settings.ACTIVE_DOMAIN 决定。
"""
from functools import lru_cache

from ..core.config import settings
from .base import DomainPack


@lru_cache(maxsize=None)
def get_active_domain() -> DomainPack:
    """返回当前激活的领域包(结果缓存,进程内只构建一次)。"""
    return load_domain(settings.ACTIVE_DOMAIN)


def load_domain(name: str) -> DomainPack:
    """按名字加载领域包。加不到时回退到 maritime。"""
    if name == "maritime":
        from .maritime import build
        return build()
    if name == "example":
        from .example import build
        return build()
    # 未知领域:回退到航运,避免启动崩溃
    from .maritime import build
    return build()
