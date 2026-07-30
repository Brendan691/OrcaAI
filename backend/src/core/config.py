"""全局配置 — 参照 OmniBox 环境变量模式，集中管理所有服务配置"""
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_ENV_PATHS = [
    Path(__file__).parent.parent.parent.parent / ".env",
    Path(__file__).parent.parent.parent / ".env",
]
for env_path in _ENV_PATHS:
    if env_path.exists():
        load_dotenv(env_path)
        break
else:
    load_dotenv()

PROJECT_ROOT = Path(__file__).parent.parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", case_sensitive=True, extra="ignore"
    )

    # ── AI 服务 (通义千问) ──
    DASHSCOPE_API_KEY: str = ""
    DASHSCOPE_BASE_URL: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    EMBEDDING_MODEL: str = "text-embedding-v3"
    CHAT_MODEL: str = "qwen-max"

    # ── 数据库(本地默认 SQLite;生产切 Postgres,见 ADR-0002)──
    DATABASE_URL: str = "sqlite+aiosqlite:///./data/orca.db"
    DATABASE_URL_SYNC: str = "sqlite:///./data/orca.db"

    # ── JWT ──
    JWT_SECRET: str = "change-me-to-a-random-secret-string"
    JWT_EXPIRE_MINUTES: int = 43200  # 30 days

    # ── 文件存储(本地默认;生产切 MinIO/S3,见 ADR-0002)──
    STORAGE_BACKEND: str = "local"  # local | minio
    FILE_STORAGE_DIR: str = str(PROJECT_ROOT / "data" / "files")
    S3_ACCESS_KEY_ID: str = "orcaaiadmin"
    S3_SECRET_ACCESS_KEY: str = "orcaaiadmin"
    S3_ENDPOINT: str = "localhost:9000"
    S3_BUCKET: str = "orcaai-files"
    S3_SECURE: bool = False

    # ── 全文搜索 (MeiliSearch) ──
    MEILI_HOST: str = "http://localhost:7700"
    MEILI_API_KEY: str = "orcaai-meili-key"

    # ── 联网搜索 (SearXNG) ──
    SEARXNG_BASE_URL: str = "http://localhost:8888"

    # ── 微信 ──
    WECHAT_APP_ID: str = ""
    WECHAT_APP_SECRET: str = ""
    WECHAT_TOKEN: str = ""
    WECHAT_ENCODING_AES_KEY: str = ""

    # ── 应用 ──
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8000
    APP_DEBUG: bool = False
    ALLOWED_ORIGINS: str = "http://localhost:3000,http://localhost:8501,chrome-extension://*"

    # ── 数据目录(SQLite / Chroma / 文件 都放这里,方便备份与 gitignore)──
    DATA_DIR: str = str(PROJECT_ROOT / "data")

    # ── 领域包(见 ADR-0003)──
    ACTIVE_DOMAIN: str = "maritime"

    # ── Chroma ──
    CHROMA_PERSIST_DIR: str = str(PROJECT_ROOT / "data" / "chroma")

    # ── 日志 ──
    LOG_LEVEL: str = "INFO"
    LOG_JSON: bool = False

    # ── 限流 ──
    RATE_LIMIT_PER_MINUTE: int = 60

    # ── 文档处理 ──
    CHUNK_SIZE: int = 1024
    CHUNK_OVERLAP: int = 128
    TOP_K: int = 5

    # ── 混合搜索权重 ──
    VECTOR_WEIGHT: float = 0.6
    KEYWORD_WEIGHT: float = 0.2
    TIME_WEIGHT: float = 0.1
    TAG_WEIGHT: float = 0.1

    # ── 上传限制 ──
    MAX_UPLOAD_SIZE_MB: int = 50

    @field_validator("APP_PORT", "RATE_LIMIT_PER_MINUTE", "CHUNK_SIZE", "CHUNK_OVERLAP", "TOP_K", mode="before")
    @classmethod
    def validate_int(cls, v):
        try:
            return int(v)
        except (TypeError, ValueError):
            return v

    @property
    def allowed_origins_list(self) -> list[str]:
        return [o.strip() for o in self.ALLOWED_ORIGINS.split(",") if o.strip()]

    @property
    def cors_origins(self) -> list[str]:
        origins = self.allowed_origins_list
        if self.APP_DEBUG:
            origins.append("*")
        return origins

    @property
    def has_api_key(self) -> bool:
        return bool(self.DASHSCOPE_API_KEY and self.DASHSCOPE_API_KEY not in (
            "your_dashscope_api_key_here", "sk-your-api-key", ""
        ))

    @property
    def s3_endpoint_url(self) -> str:
        scheme = "https" if self.S3_SECURE else "http"
        return f"{scheme}://{self.S3_ENDPOINT}"


settings = Settings()
config = settings  # backward compat
