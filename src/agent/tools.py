from __future__ import annotations

from langchain.tools import tool

from src.rag.retriever import format_docs, search_knowledge as _search
from src.rag.store import list_sources


@tool
def search_knowledge(query: str) -> str:
    """在企业知识库中检索与问题相关的制度、手册片段。
    Args:
        query: 检索用的自然语言查询，尽量包含关键制度关键词。
    """
    docs = _search(query)
    return format_docs(docs)


@tool
def list_documents() -> str:
    """列出知识库中已入库的文档名称。"""
    sources = list_sources()
    if not sources:
        return "知识库为空，尚未入库任何文档。"
    return "已入库文档：\n" + "\n".join(f"- {s}" for s in sources)
