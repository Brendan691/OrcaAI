"""切片定位器必须持久化到向量库元数据。"""

from src.models.document import DocumentChunk
from src.services.chroma_store import ChromaStore


class CapturingCollection:
    def __init__(self):
        self.payload = None

    def add(self, **kwargs):
        self.payload = kwargs


def test_add_document_persists_chunk_locator_metadata():
    store = ChromaStore.__new__(ChromaStore)
    store.collection = CapturingCollection()
    chunk = DocumentChunk(
        chunk_id="chunk_0",
        content="第一行\n第二行",
        start_idx=0,
        end_idx=7,
        line_start=1,
        line_end=2,
    )

    store.add_document(
        doc_id="doc-1",
        chunks=[chunk],
        embeddings=[[1.0, 0.0]],
        metadata={"title": "测试文档", "published_at": "2026-08-20", "tags": {}},
    )

    metadata = store.collection.payload["metadatas"][0]
    assert store.collection.payload["documents"] == ["第一行\n第二行"]
    assert metadata["start_idx"] == 0
    assert metadata["end_idx"] == 7
    assert metadata["line_start"] == 1
    assert metadata["line_end"] == 2
    assert metadata["published_at"] == "2026-08-20"
