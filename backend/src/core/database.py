"""SQLAlchemy 异步数据库引擎 + session 工厂

本地默认用 SQLite,生产可通过 DATABASE_URL 切换到 Postgres(见 ADR-0002)。
两种数据库的引擎参数不同,这里按 URL 自动区分。
"""
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import StaticPool

from .config import PROJECT_ROOT, settings


def _normalize_sqlite_url(url: str) -> str:
    """把 SQLite 的相对路径改写成基于项目根的绝对路径。

    这样无论从 backend/ 启动后端,还是从别处跑测试,都指向同一个 .db 文件。
    并确保数据库文件所在目录存在(SQLite 不会自动建目录)。
    """
    marker = ":///./"
    if url.startswith("sqlite") and marker in url:
        rel = url.split(marker, 1)[1]
        abs_path = (PROJECT_ROOT / rel).resolve()
        abs_path.parent.mkdir(parents=True, exist_ok=True)
        return url.split(marker, 1)[0] + ":///" + str(abs_path)
    return url


DATABASE_URL = _normalize_sqlite_url(settings.DATABASE_URL)
_is_sqlite = DATABASE_URL.startswith("sqlite")

# SQLite 与 Postgres 的引擎参数不同:
# - SQLite 是单文件,连接池参数(pool_size 等)不适用,需 check_same_thread=False
# - Postgres 才需要连接池
if _is_sqlite:
    engine = create_async_engine(
        DATABASE_URL,
        echo=settings.APP_DEBUG,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
else:
    engine = create_async_engine(
        DATABASE_URL, echo=settings.APP_DEBUG, pool_size=20, max_overflow=10
    )

async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncSession:
    async with async_session() as session:
        try:
            yield session
        finally:
            await session.close()


async def init_db():
    """创建所有表(开发环境用;生产用 Alembic 迁移)。

    必须先 import 所有 ORM 模型,让它们注册到 Base.metadata,否则不会建表。
    """
    from ..models import user, team, document  # noqa: F401  触发模型注册

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
