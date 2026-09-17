"""纯检索数据类型，不导入数据库或外部存储。"""

from typing import List, Optional

from pydantic import BaseModel, Field


class DocumentTags(BaseModel):
    business_type: List[str] = Field(default=[], description="业务类型")
    geographic_region: List[str] = Field(default=[], description="地理区域")
    topic_category: List[str] = Field(default=[], description="主题类别")
    event_nature: List[str] = Field(default=[], description="事件性质")
    confidence: float = Field(default=0.0, description="分类置信度")


class SearchResult(BaseModel):
    doc_id: str = Field(..., description="文档ID")
    title: str = Field(..., description="文档标题")
    content: str = Field(..., description="匹配内容片段")
    chunk_id: str = ""
    chunk_index: Optional[int] = None
    url: str = ""
    source_type: str = ""
    start_idx: Optional[int] = None
    end_idx: Optional[int] = None
    line_start: Optional[int] = None
    line_end: Optional[int] = None
    score: float = Field(..., description="综合得分")
    vector_score: float = Field(default=0.0)
    keyword_score: float = Field(default=0.0)
    time_score: float = Field(default=0.0)
    tag_score: float = Field(default=0.0)
    tags: DocumentTags = Field(default_factory=DocumentTags)
