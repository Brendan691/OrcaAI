"""API路由 — 文档管理 / 知识库问答 / 搜索 / 标签"""
import json
import traceback
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.database import get_db
from ..core.security import get_current_user
from ..models.document import (
    ChatRequest,
    ChatResponse,
    DocumentTags,
    MaritimeDocument,
    SearchResult,
    UploadRequest,
    UploadResponse,
)
from ..models.user import User
from ..services.document_processor import document_processor
from ..services.embedding_service import embedding_service
from ..services.tag_classifier import tag_classifier
from ..services.chroma_store import chroma_store
from ..services.rag_service import rag_service
from ..services.search_service import search_service

router = APIRouter(prefix="/api", tags=["小鲸OrcaAI API"])


# ── 文档管理 ──

class DocumentListResponse(BaseModel):
    documents: List[dict] = Field(default=[])
    total: int = Field(default=0)


@router.post("/documents/upload", response_model=UploadResponse)
async def upload_document(request: UploadRequest, user: User | None = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    try:
        if request.url:
            # 通过采集器注册表选择合适的采集器(公众号链接会走专用采集器,见 ADR-0004)
            from ..collectors import collect as collect_source
            raw = collect_source(request.url)
            title, content = raw.title, raw.content
            source_type = raw.source_type
            doc_id = document_processor.generate_doc_id(url=request.url)
        elif request.content:
            content = request.content
            title = request.title or "未命名文档"
            source_type = "text"
            doc_id = document_processor.generate_doc_id(content=content)
        else:
            return UploadResponse(success=False, message="请提供URL或content")

        full_text, chunks = document_processor.process_text(content, title)
        tags = tag_classifier.classify(full_text, use_llm=True)

        chunk_texts = [c.content for c in chunks]
        embeddings = embedding_service.embed_batch(chunk_texts)

        metadata = {
            "title": title,
            "url": request.url or "",
            "source_type": source_type,
            "created_at": datetime.now().isoformat(),
            "tags": {
                "business_type": tags.business_type,
                "geographic_region": tags.geographic_region,
                "topic_category": tags.topic_category,
                "event_nature": tags.event_nature,
            },
        }

        chroma_store.add_document(doc_id=doc_id, chunks=chunk_texts, embeddings=embeddings, metadata=metadata)

        # 存入 PostgreSQL
        from ..models.document import Document
        doc_record = Document(
            title=title,
            content_preview=content[:500],
            source_type=source_type,
            source_url=request.url or "",
            chroma_doc_id=doc_id,
            user_id=user.id if user else None,
        )
        db.add(doc_record)
        await db.commit()

        return UploadResponse(
            success=True, doc_id=doc_id,
            message=f"文档《{title}》上传成功，共{len(chunks)}个切片",
            tags=tags,
        )
    except Exception as e:
        traceback.print_exc()
        return UploadResponse(success=False, message=f"上传失败: {str(e)}")


@router.get("/documents", response_model=DocumentListResponse)
async def list_documents(user: User | None = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    docs = chroma_store.get_all_documents()
    return DocumentListResponse(documents=docs, total=len(docs))


@router.delete("/documents/{doc_id}")
async def delete_document(doc_id: str, db: AsyncSession = Depends(get_db)):
    try:
        chroma_store.delete_document(doc_id)
        from ..models.document import Document
        result = await db.execute(select(Document).where(Document.chroma_doc_id == doc_id))
        doc = result.scalar_one_or_none()
        if doc:
            await db.delete(doc)
            await db.commit()
        return {"success": True, "message": f"文档 {doc_id} 已删除"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── 知识库问答 ──

@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    try:
        result = rag_service.chat(request)

        # 如果要求联网搜索，追加互联网结果
        if request.search_internet:
            internet_ctx = await search_service.search_and_format(request.message, num=3)
            if internet_ctx and result.confidence < 0.7:
                enhanced = rag_service._generate_answer(
                    request.message,
                    rag_service._build_context(rag_service._rerank(
                        chroma_store.search(embedding_service.embed_text(request.message), top_k=5),
                        request.message, None,
                    )[:3]) + f"\n\n{internet_ctx}"
                )
                result.answer = enhanced
                result.confidence = min(result.confidence + 0.2, 1.0)

        return result
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"问答失败: {str(e)}")


# ── 标签体系 ──

class TagsResponse(BaseModel):
    dimensions: dict = Field(default={})


@router.get("/tags", response_model=TagsResponse)
async def get_tags():
    """返回当前领域包的标签维度(见 ADR-0003)。"""
    from ..domains import get_active_domain
    return TagsResponse(dimensions=get_active_domain().dimensions_as_dict())


# ── 搜索 ──

class SearchRequest(BaseModel):
    query: str = Field(..., description="搜索关键词")
    top_k: int = Field(default=5)
    doc_filter: Optional[List[str]] = Field(default=None)
    tag_filter: Optional[DocumentTags] = Field(default=None)


class SearchResponse(BaseModel):
    results: List[dict] = Field(default=[])
    total: int = Field(default=0)


@router.post("/search", response_model=SearchResponse)
async def search(request: SearchRequest):
    try:
        query_embedding = embedding_service.embed_text(request.query)
        hits = chroma_store.search(query_embedding=query_embedding, top_k=request.top_k * 3, doc_filter=request.doc_filter)

        if not hits:
            return SearchResponse(results=[], total=0)

        from ..services.hybrid_search import hybrid_search

        results = []
        for hit in hits:
            vector_score = hybrid_search.compute_vector_score(hit.get("distance", 0.5))
            keyword_score = hybrid_search.compute_keyword_score(request.query, hit.get("content", ""))
            time_score = hybrid_search.compute_time_score(hit.get("created_at", ""))
            tag_score = hybrid_search.compute_tag_score(request.tag_filter, hit.get("tags", {}))

            fused = hybrid_search.fuse_scores(vector_score, keyword_score, time_score, tag_score)

            results.append({
                "doc_id": hit.get("doc_id", ""),
                "title": hit.get("title", ""),
                "content": hit.get("content", "")[:300] + "...",
                "url": hit.get("url", ""),
                "score": round(fused, 4),
                "vector_score": round(vector_score, 4),
                "keyword_score": round(keyword_score, 4),
                "time_score": round(time_score, 4),
                "tag_score": round(tag_score, 4),
                "tags": hit.get("tags", {}),
            })

        results.sort(key=lambda x: x["score"], reverse=True)
        results = results[:request.top_k]

        return SearchResponse(results=results, total=len(results))
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"搜索失败: {str(e)}")


# ── 系统状态 ──

@router.get("/status")
async def get_status():
    return {
        "status": "running",
        "document_count": chroma_store.get_document_count(),
        "version": "0.3.0",
        "name": "小鲸OrcaAI",
    }
