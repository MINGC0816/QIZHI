from __future__ import annotations

import sqlite3
from functools import lru_cache

from langchain.agents import create_agent
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langgraph.checkpoint.sqlite import SqliteSaver

from src.agent.prompts import SYSTEM_PROMPT
from src.agent.tools import list_documents, search_knowledge
from src.config import CHECKPOINT_DB
from src.llm import get_llm
from src.logging_config import get_logger
from src.sessions.store import delete_thread_meta, touch_thread

log = get_logger("qizhi.agent")


def _extract_text(content) -> str:
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict) and isinstance(block.get("text"), str):
                parts.append(block["text"])
        return "".join(parts)
    return str(content)


@lru_cache(maxsize=1)
def _get_connection() -> sqlite3.Connection:
    CHECKPOINT_DB.parent.mkdir(parents=True, exist_ok=True)
    return sqlite3.connect(str(CHECKPOINT_DB), check_same_thread=False)


@lru_cache(maxsize=1)
def get_checkpointer() -> SqliteSaver:
    checkpointer = SqliteSaver(_get_connection())
    checkpointer.setup()
    return checkpointer


@lru_cache(maxsize=1)
def get_agent():
    return create_agent(
        model=get_llm(),
        tools=[search_knowledge, list_documents],
        checkpointer=get_checkpointer(),
        system_prompt=SYSTEM_PROMPT,
    )


def ask(question: str, *, thread_id: str = "default") -> str:
    """同步问答，返回最终助手文本，并更新会话元数据。"""
    log.info("ask thread=%s q=%s", thread_id, question[:80].replace("\n", " "))
    agent = get_agent()
    try:
        result = agent.invoke(
            {"messages": [HumanMessage(content=question)]},
            {"configurable": {"thread_id": thread_id}},
        )
    except Exception:
        log.exception("ask failed thread=%s", thread_id)
        raise
    messages = result.get("messages") or []
    answer = ""
    for msg in reversed(messages):
        if isinstance(msg, AIMessage):
            text = _extract_text(msg.content).strip()
            if text:
                answer = text
                break

    touch_thread(
        thread_id,
        title=question.strip()[:40] or "新对话",
        preview=(answer or question)[:120],
    )
    log.info("ask done thread=%s answer_len=%s", thread_id, len(answer))
    return answer


def get_thread_messages(thread_id: str) -> list[dict]:
    """从 checkpoint 读取可展示的 user/assistant 消息。"""
    checkpointer = get_checkpointer()
    checkpoint = checkpointer.get({"configurable": {"thread_id": thread_id}})
    if not checkpoint:
        return []
    channel_values = checkpoint.get("channel_values") or {}
    raw = channel_values.get("messages") or []
    out: list[dict] = []
    for msg in raw:
        if isinstance(msg, HumanMessage):
            text = _extract_text(msg.content).strip()
            if text:
                out.append({"role": "user", "content": text})
        elif isinstance(msg, AIMessage):
            # 跳过纯 tool_calls 的中间轮
            if getattr(msg, "tool_calls", None):
                continue
            text = _extract_text(msg.content).strip()
            if text:
                out.append({"role": "assistant", "content": text})
        elif isinstance(msg, ToolMessage):
            continue
    return out


def delete_thread(thread_id: str) -> None:
    """删除会话元数据；checkpoint 随不再引用自然闲置（V1 不强制清 checkpoints 表）。"""
    delete_thread_meta(thread_id)
