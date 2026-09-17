"""文档数据模型 — 扩展支持用户/团队/文件"""
import uuid
from datetime import datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, Field
from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..core.database import Base
from .retrieval import DocumentTags, SearchResult


# ── Pydantic schemas ──

class DocumentChunk(BaseModel):
    chunk_id: str = Field(..., description="切片唯一ID")
    content: str = Field(..., description="切片内容")
    start_idx: int = Field(..., description="在原文档中的起始位置")
    end_idx: int = Field(..., description="在原文档中的结束位置")
    line_start: int = Field(..., description="在原文档中的起始行")
    line_end: int = Field(..., description="在原文档中的结束行")
    page_number: Optional[int] = Field(default=None, description="原始文件页码")


class MaritimeDocument(BaseModel):
    doc_id: str = Field(..., description="文档唯一ID")
    title: str = Field(..., description="文档标题")
    url: Optional[str] = Field(default=None, description="来源URL")
    source_type: str = Field(default="web", description="来源类型: web/pdf/word/ppt/mp3/text")
    content: str = Field(..., description="文档全文")
    summary: str = Field(default="", description="内容摘要")
    tags: DocumentTags = Field(default_factory=DocumentTags)
    chunks: List[DocumentChunk] = Field(default=[], description="文本切片")
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)


class ChatRequest(BaseModel):
    message: str = Field(..., description="用户消息")
    doc_filter: Optional[List[str]] = Field(default=None)
    tag_filter: Optional[DocumentTags] = Field(default=None)
    search_internet: bool = Field(default=False, description="是否同时搜索互联网")


class Citation(BaseModel):
    id: str = Field(..., description="稳定引用ID")
    index: int = Field(..., description="回答中的角标序号")
    cite_marker: str = Field(..., description="模型必须原样使用的引用角标")
    source_type: Literal["knowledge", "web"]
    title: str
    snippet: str = ""
    url: str = ""
    doc_id: str = ""
    chunk_id: str = ""
    chunk_index: Optional[int] = None
    start_idx: Optional[int] = None
    end_idx: Optional[int] = None
    line_start: Optional[int] = None
    line_end: Optional[int] = None
    locator_label: str = ""
    provider: str = ""
    score: Optional[float] = None


class ChatResponse(BaseModel):
    answer: str = Field(..., description="AI回答")
    sources: List[Citation] = Field(default_factory=list)
    confidence: float = Field(default=0.0)
    search_status: Literal["disabled", "ok", "degraded", "failed"] = "disabled"
    search_message: str = ""


class WebSearchResult(BaseModel):
    title: str
    url: str
    snippet: str = ""
    provider: str
    score: Optional[float] = None
    published_at: Optional[str] = None


class SearchWarning(BaseModel):
    code: str
    message: str
    provider: str = ""


class SearchOutcome(BaseModel):
    status: Literal["ok", "degraded", "failed"]
    provider: str = ""
    results: List[WebSearchResult] = Field(default_factory=list)
    warnings: List[SearchWarning] = Field(default_factory=list)


class UploadRequest(BaseModel):
    url: Optional[str] = Field(default=None, description="网页URL")
    content: Optional[str] = Field(default=None, description="直接文本内容")
    title: Optional[str] = Field(default=None)


class UploadResponse(BaseModel):
    success: bool = Field(..., description="是否成功")
    doc_id: Optional[str] = Field(default=None)
    message: str = Field(..., description="状态信息")
    tags: Optional[DocumentTags] = Field(default=None)


class ReportGenerateRequest(BaseModel):
    report_type: str = Field(..., description="报告类型: weekly_shipping/risk_alert/convention_update")
    time_range: Optional[str] = Field(default="week", description="时间范围: week/month/quarter")
    topic_filter: Optional[str] = Field(default=None, description="主题过滤")
    search_internet: bool = Field(default=False, description="是否联网搜索补充素材")


class ReportGenerateResponse(BaseModel):
    success: bool
    title: str = ""
    content: str = ""
    sources: List[dict] = Field(default=[])
    generated_at: str = ""


class FileUploadResponse(BaseModel):
    success: bool
    file_id: Optional[str] = None
    filename: str = ""
    message: str = ""
    doc_id: Optional[str] = None
    tags: Optional[DocumentTags] = None


# ── SQLAlchemy ORM models ──

class Document(Base):
    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    content_preview: Mapped[str] = mapped_column(Text, default="")
    source_type: Mapped[str] = mapped_column(String(20), default="web")  # web/pdf/word/ppt/mp3/text
    source_url: Mapped[str] = mapped_column(String(2000), default="")
    file_path: Mapped[str] = mapped_column(String(1000), default="")
    file_size: Mapped[int] = mapped_column(Integer, default=0)
    chroma_doc_id: Mapped[str] = mapped_column(String(64), default="")  # Chroma 中的 doc_id
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    team_id: Mapped[str] = mapped_column(String(36), ForeignKey("teams.id", ondelete="SET NULL"), nullable=True)
    is_public: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    owner = relationship("User", back_populates="documents")
