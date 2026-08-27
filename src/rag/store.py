from __future__ import annotations

from functools import lru_cache

from langchain_chroma import Chroma
from langchain_core.documents import Document

from src.config import CHROMA_COLLECTION, CHROMA_DIR
from src.rag.embeddings import get_embeddings


@lru_cache(maxsize=1)
def get_vectorstore() -> Chroma:
    return Chroma(
        collection_name=CHROMA_COLLECTION,
        embedding_function=get_embeddings(),
        persist_directory=str(CHROMA_DIR),
    )


def add_documents(docs: list[Document]) -> list[str]:
    if not docs:
        return []
    store = get_vectorstore()
    ids = store.add_documents(docs)
    return ids


def delete_by_source(source: str) -> None:
    store = get_vectorstore()
    try:
        store.delete(where={"source": source})
    except Exception:
        # 旧集合为空或不支持 where 时忽略
        pass


def list_sources() -> list[str]:
    store = get_vectorstore()
    data = store.get(include=["metadatas"])
    metadatas = data.get("metadatas") or []
    sources = sorted(
        {
            m.get("source")
            for m in metadatas
            if isinstance(m, dict) and m.get("source")
        }
    )
    return sources
