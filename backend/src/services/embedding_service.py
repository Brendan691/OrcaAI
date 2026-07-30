"""向量化服务 —— 调用通义千问 Embedding API。

无 API Key 时自动降级为确定性 mock 向量(见 ADR-0007),
让整条管线在离线/无 key 环境下也能跑通、测试可复现。
mock 向量基于词袋 hash:共享词越多的文本越相似,检索仍有基本语义近似,便于演示。
"""
import hashlib
import math
import re
from typing import List

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
        if not config.has_api_key:
            return self._mock_embed(text)
        response = self.client.embeddings.create(
            model=self.model, input=text, dimensions=self._dimension,
        )
        return response.data[0].embedding

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """批量文本向量化。无 key 时用 mock。"""
        if not config.has_api_key:
            return [self._mock_embed(t) for t in texts]
        response = self.client.embeddings.create(
            model=self.model, input=texts, dimensions=self._dimension,
        )
        return [item.embedding for item in response.data]

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
