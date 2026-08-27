from __future__ import annotations

from langchain_core.documents import Document

from src.config import RETRIEVE_TOP_K
from src.rag.store import get_vectorstore


def search_knowledge(query: str, *, k: int | None = None) -> list[Document]:
    top_k = k or RETRIEVE_TOP_K
    store = get_vectorstore()
    return store.similarity_search(query, k=top_k)


def format_docs(docs: list[Document]) -> str:
    if not docs:
        return "（未检索到相关内容）"
    parts: list[str] = []
    for i, doc in enumerate(docs, start=1):
        meta = doc.metadata or {}
        source = meta.get("source", "未知")
        page = meta.get("page", "?")
        parts.append(
            f"[{i}] 来源: {source} | 页/段: {page}\n{doc.page_content.strip()}"
        )
    return "\n\n".join(parts)
