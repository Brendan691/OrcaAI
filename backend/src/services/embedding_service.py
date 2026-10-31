"""向量化服务 —— 支持远程 DashScope 或本地 BGE-M3 sidecar。

`EMBEDDING_BACKEND=local` 时把文本 POST 到本地编码 sidecar，该 sidecar 直接 import
`backend/src/services/bge_encoder.py`——与离线实验共用同一份编码实现（CLS + L2 + 1024）。
本地后端不会静默降级为 mock：连不上就报错，避免把失败伪装成成功。
"""
import hashlib
import math
import re
from typing import List

import httpx
from openai import OpenAI

from ..core.config import config


class EmbeddingService:
    """文本向量化服务。"""

    def __init__(self):
        self._client = None
        self.model = config.EMBEDDING_MODEL
        self._dimension = 1024  # text-embedding-v3 输出维度

    @property
    def client(self):
        """延迟创建 OpenAI 客户端(避免无 API Key 时导入失败)。"""
        if self._client is None:
            self._client = OpenAI(
                api_key=config.DASHSCOPE_API_KEY,
                base_url=config.DASHSCOPE_BASE_URL,
            )
        return self._client

    def embed_text(self, text: str) -> List[float]:
        """单条文本向量化。无 key 时用 mock。"""
        if config.EMBEDDING_BACKEND == "local":
            return self._local_embed([text])[0]
        if not config.has_dashscope_api_key:
            return self._mock_embed(text)
        response = self.client.embeddings.create(
            model=self.model, input=text, dimensions=self._dimension,
        )
        return response.data[0].embedding

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """批量文本向量化。无 key 时用 mock。"""
        if config.EMBEDDING_BACKEND == "local":
            return self._local_embed(texts)
        if not config.has_dashscope_api_key:
            return [self._mock_embed(t) for t in texts]
        response = self.client.embeddings.create(
            model=self.model, input=texts, dimensions=self._dimension,
        )
        return [item.embedding for item in response.data]

    def _local_embed(self, texts: List[str]) -> List[List[float]]:
        """调用本地 BGE-M3 sidecar；失败直接抛出，不降级。"""
        with httpx.Client(timeout=60.0) as client:
            response = client.post(
                config.EMBEDDING_ENDPOINT,
                json={"texts": texts},
            )
            response.raise_for_status()
            payload = response.json()
        vectors = payload.get("vectors")
        if not vectors or len(vectors) != len(texts):
            raise RuntimeError("local embedding sidecar returned malformed payload")
        return vectors

    def _mock_embed(self, text: str) -> List[float]:
        """确定性伪向量(词袋 hash + L2 归一化)。

        - 相同文本 → 相同向量(检索可命中)
        - 共享词多的文本 → 余弦相似度高(演示时检索有基本意义)
        注意:mock 向量无真实语义,仅用于流程演示与测试,不代表真实检索质量。
        """
        vec = [0.0] * self._dimension
        tokens = re.findall(r"[一-鿿]{1,2}|[a-zA-Z]+", text.lower())
        if not tokens:
            tokens = [text[:8] or "empty"]
        for tok in tokens:
            h = int(hashlib.md5(tok.encode("utf-8")).hexdigest(), 16)
            idx = h % self._dimension
            vec[idx] += 1.0
        norm = math.sqrt(sum(v * v for v in vec))
        if norm > 0:
            vec = [v / norm for v in vec]
        return vec

    @property
    def dimension(self) -> int:
        return self._dimension


# 全局实例
embedding_service = EmbeddingService()
