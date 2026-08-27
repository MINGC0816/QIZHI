from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from langchain_huggingface import HuggingFaceEmbeddings

from src.config import EMBEDDING_MODEL_PATH
from src.logging_config import get_logger

log = get_logger("qizhi.embeddings")


@lru_cache(maxsize=1)
def get_embeddings() -> HuggingFaceEmbeddings:
    """本地 sentence-transformers Embedding（优先项目内 models/ 目录）。"""
    path = EMBEDDING_MODEL_PATH
    local = Path(path)
    if local.is_dir():
        log.info("loading embedding from local dir: %s", local)
    else:
        log.warning(
            "embedding path is not a local dir, will treat as HF id: %s",
            path,
        )
    return HuggingFaceEmbeddings(
        model_name=path,
        model_kwargs={"device": "cpu"},
        encode_kwargs={"normalize_embeddings": True},
    )
