"""BGE-M3 编码器：线上服务与离线实验共用的唯一实现。

约定（冻结）：
- 模型：/Volumes/Lenovo/26大创/models/bge-m3（权重哈希 b5e0ce3470abf5ef…）
- 池化：CLS（last_hidden_state[:, 0]），不是 mean
- 归一化：L2
- max_length：1024
- 设备：CPU，4 线程

任何调用方（离线脚本、本地编码 sidecar、线上服务）都必须 import 本模块，
不得自行复制加载/池化/归一化逻辑，以保证"评测口径 = 系统口径"。
"""

from __future__ import annotations

import os
import threading
from typing import Any

import numpy as np

VERSION = "bge-encoder-20261017-v1"
MODEL_PATH = os.environ.get("BGE_M3_MODEL_PATH", "/Volumes/Lenovo/26大创/models/bge-m3")
MAX_LENGTH = 1024
BATCH_SIZE = 8
THREADS = 4
POOLING = "cls"
NORMALIZE = "l2"

_lock = threading.Lock()
_tokenizer: Any = None
_model: Any = None


def _load() -> tuple[Any, Any]:
    global _tokenizer, _model
    if _model is not None and _tokenizer is not None:
        return _tokenizer, _model
    with _lock:
        if _model is None or _tokenizer is None:
            import torch
            from transformers import AutoModel, AutoTokenizer

            torch.set_num_threads(THREADS)
            tokenizer = AutoTokenizer.from_pretrained(MODEL_PATH)
            model = AutoModel.from_pretrained(MODEL_PATH)
            model.eval()
            _tokenizer, _model = tokenizer, model
    return _tokenizer, _model


def encode(
    texts: list[str],
    *,
    batch_size: int = BATCH_SIZE,
    max_length: int = MAX_LENGTH,
) -> np.ndarray:
    """把一批文本编码成 L2 归一化的 1024 维向量。"""
    if not texts:
        return np.zeros((0, 1024), dtype=np.float32)
    import torch

    tokenizer, model = _load()
    chunks: list[np.ndarray] = []
    with torch.no_grad():
        for offset in range(0, len(texts), batch_size):
            batch = tokenizer(
                texts[offset : offset + batch_size],
                padding=True,
                truncation=True,
                max_length=max_length,
                return_tensors="pt",
            )
            hidden = model(**batch).last_hidden_state[:, 0]
            chunks.append(
                torch.nn.functional.normalize(hidden, p=2, dim=1).cpu().numpy()
            )
    return np.vstack(chunks).astype(np.float32)


def encode_query(text: str) -> np.ndarray:
    return encode([text])[0]


def encode_documents(texts: list[str]) -> np.ndarray:
    return encode(texts)


def fingerprint() -> dict[str, Any]:
    return {
        "version": VERSION,
        "model_path": MODEL_PATH,
        "pooling": POOLING,
        "normalize": NORMALIZE,
        "max_length": MAX_LENGTH,
        "batch_size": BATCH_SIZE,
        "threads": THREADS,
    }
