"""文件上传 API"""
from datetime import datetime

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.config import settings
from ..core.database import get_db
from ..core.security import get_current_user
from ..models.document import FileUploadResponse
from ..models.user import User
from ..services.document_processor import document_processor
from ..services.embedding_service import embedding_service
from ..services.file_service import file_service
from ..services.tag_classifier import tag_classifier
from ..services.chroma_store import chroma_store

router = APIRouter(prefix="/api/files", tags=["文件上传"])

MAX_SIZE = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024


@router.post("/upload", response_model=FileUploadResponse)
async def upload_file(
    file: UploadFile = File(...),
    user: User | None = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not file.filename:
        raise HTTPException(400, "文件名不能为空")

    if not file_service.is_supported(file.filename):
        raise HTTPException(400, f"不支持的文件格式: {file.filename}。支持:PDF/Word/PPT/TXT/MD/CSV")

    content_bytes = await file.read()
    if len(content_bytes) > MAX_SIZE:
        raise HTTPException(400, f"文件超过大小限制 ({settings.MAX_UPLOAD_SIZE_MB}MB)")

    # 解析为纯文本
    text = file_service.parse_to_text(content_bytes, file.filename)
    if not text or text.startswith("[无法解析"):
        raise HTTPException(400, f"无法解析文件内容: {text}")

    # 存储原始文件
    object_name = file_service.upload_file(
        content_bytes, file.filename, file.content_type or ""
    )

    # 切片 → 标签 → 向量化 → 存 Chroma
    full_text, chunks = document_processor.process_text(text, file.filename)
    tags = tag_classifier.classify(full_text, use_llm=True)
    chunk_texts = [c.content for c in chunks]
    embeddings = embedding_service.embed_batch(chunk_texts)
    doc_id = document_processor.generate_doc_id(content=text[:100])

    metadata = {
        "title": file.filename,
        "url": "",
        "source_type": "file",
        "created_at": datetime.now().isoformat(),
        "tags": {
            "business_type": tags.business_type,
            "geographic_region": tags.geographic_region,
            "topic_category": tags.topic_category,
            "event_nature": tags.event_nature,
        },
    }
    chroma_store.add_document(doc_id=doc_id, chunks=chunk_texts, embeddings=embeddings, metadata=metadata)

    # 存元数据记录
    from ..models.document import Document
    doc_record = Document(
        title=file.filename,
        content_preview=text[:500],
        source_type="file",
        file_path=object_name,
        file_size=len(content_bytes),
        chroma_doc_id=doc_id,
        user_id=user.id if user else None,
    )
    db.add(doc_record)
    await db.commit()
    await db.refresh(doc_record)

    return FileUploadResponse(
        success=True,
        file_id=doc_record.id,
        filename=file.filename,
        message=f"文件《{file.filename}》解析成功,共 {len(chunks)} 个切片",
        doc_id=doc_id,
        tags=tags,
    )


@router.get("/{object_name}/raw")
async def get_raw_file(object_name: str):
    """本地存储的文件下载端点。"""
    try:
        data = file_service.download_file(object_name)
    except Exception:
        raise HTTPException(404, "文件不存在")
    return Response(content=data, media_type="application/octet-stream")
