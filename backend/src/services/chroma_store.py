"""Chroma向量数据库封装"""
import json
from datetime import datetime
from typing import List, Optional, Dict, Any

import chromadb
from chromadb.config import Settings

from ..core.config import config
from ..models.document import DocumentChunk, DocumentTags, MaritimeDocument


class ChromaStore:
    """Chroma向量数据库操作类"""

    def __init__(self):
        self.client = chromadb.PersistentClient(
            path=config.CHROMA_PERSIST_DIR,
            settings=Settings(anonymized_telemetry=False),
        )
        # 获取或创建集合
        self.collection = self.client.get_or_create_collection(
            name="maritime_docs",
            metadata={"hnsw:space": "cosine"},
        )

    def add_document(
        self,
        doc_id: str,
        chunks: List[DocumentChunk],
        embeddings: List[List[float]],
        metadata: Dict[str, Any],
    ) -> bool:
        """添加文档到向量库

        Args:
            doc_id: 文档ID
            chunks: 文本切片列表
            embeddings: 对应的向量列表
            metadata: 文档元数据

        Returns:
            是否成功
        """
        if len(chunks) != len(embeddings):
            raise ValueError("chunks和embeddings数量不匹配")

        # 为每个切片生成唯一ID
        chunk_ids = [f"{doc_id}_chunk_{i}" for i in range(len(chunks))]

        # 准备元数据（每个切片都需要）
        metadatas = []
        for i in range(len(chunks)):
            chunk_meta = {
                "doc_id": doc_id,
                "chunk_index": i,
                "start_idx": chunks[i].start_idx,
                "end_idx": chunks[i].end_idx,
                "line_start": chunks[i].line_start,
                "line_end": chunks[i].line_end,
                "title": metadata.get("title", ""),
                "url": metadata.get("url", ""),
                "source_type": metadata.get("source_type", "web"),
                "created_at": metadata.get("created_at", datetime.now().isoformat()),
                "published_at": metadata.get("published_at", ""),
                # 标签序列化为JSON字符串
                "tags_business": json.dumps(metadata.get("tags", {}).get("business_type", [])),
                "tags_geo": json.dumps(metadata.get("tags", {}).get("geographic_region", [])),
                "tags_topic": json.dumps(metadata.get("tags", {}).get("topic_category", [])),
                "tags_event": json.dumps(metadata.get("tags", {}).get("event_nature", [])),
            }
            metadatas.append(chunk_meta)

        self.collection.add(
            ids=chunk_ids,
            documents=[chunk.content for chunk in chunks],
            embeddings=embeddings,
            metadatas=metadatas,
        )
        return True

    def search(
        self,
        query_embedding: List[float],
        top_k: int = 5,
        doc_filter: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """向量检索

        Args:
            query_embedding: 查询向量
            top_k: 返回结果数量
            doc_filter: 按文档ID筛选

        Returns:
            检索结果列表
        """
        where_filter = None
        if doc_filter:
            where_filter = {"doc_id": {"$in": doc_filter}}

        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            where=where_filter,
            include=["documents", "metadatas", "distances"],
        )

        # 解析结果
        hits = []
        if results["ids"] and len(results["ids"]) > 0:
            for i, chunk_id in enumerate(results["ids"][0]):
                hit = {
                    "chunk_id": chunk_id,
                    "chunk_index": results["metadatas"][0][i].get("chunk_index"),
                    "doc_id": results["metadatas"][0][i].get("doc_id", ""),
                    "content": results["documents"][0][i],
                    "title": results["metadatas"][0][i].get("title", ""),
                    "url": results["metadatas"][0][i].get("url", ""),
                    "source_type": results["metadatas"][0][i].get("source_type", ""),
                    "start_idx": results["metadatas"][0][i].get("start_idx"),
                    "end_idx": results["metadatas"][0][i].get("end_idx"),
                    "line_start": results["metadatas"][0][i].get("line_start"),
                    "line_end": results["metadatas"][0][i].get("line_end"),
                    "distance": results["distances"][0][i],
                    "created_at": results["metadatas"][0][i].get("created_at", ""),
                    "published_at": results["metadatas"][0][i].get("published_at", ""),
                    "tags": {
                        "business_type": json.loads(results["metadatas"][0][i].get("tags_business", "[]")),
                        "geographic_region": json.loads(results["metadatas"][0][i].get("tags_geo", "[]")),
                        "topic_category": json.loads(results["metadatas"][0][i].get("tags_topic", "[]")),
                        "event_nature": json.loads(results["metadatas"][0][i].get("tags_event", "[]")),
                    },
                }
                hits.append(hit)

        return hits

    def delete_document(self, doc_id: str) -> bool:
        """删除文档的所有切片"""
        # Chroma 支持按 metadata 删除
        self.collection.delete(where={"doc_id": doc_id})
        return True

    def get_all_documents(self) -> List[Dict[str, Any]]:
        """获取所有文档（去重）"""
        results = self.collection.get(
            include=["metadatas"],
        )

        # 按 doc_id 去重
        docs = {}
        if results["metadatas"]:
            for meta in results["metadatas"]:
                doc_id = meta.get("doc_id", "")
                if doc_id and doc_id not in docs:
                    docs[doc_id] = {
                        "doc_id": doc_id,
                        "title": meta.get("title", ""),
                        "url": meta.get("url", ""),
                        "source_type": meta.get("source_type", ""),
                        "created_at": meta.get("created_at", ""),
                        "published_at": meta.get("published_at", ""),
                        "tags": {
                            "business_type": json.loads(meta.get("tags_business", "[]")),
                            "geographic_region": json.loads(meta.get("tags_geo", "[]")),
                            "topic_category": json.loads(meta.get("tags_topic", "[]")),
                            "event_nature": json.loads(meta.get("tags_event", "[]")),
                        },
                    }

        return list(docs.values())

    def get_document_count(self) -> int:
        """获取文档切片总数"""
        return self.collection.count()


# 全局实例
chroma_store = ChromaStore()
