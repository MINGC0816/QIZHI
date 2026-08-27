from __future__ import annotations

from langchain.chat_models import init_chat_model

from src.config import (
    VLLM_API_KEY,
    VLLM_BASE_URL,
    VLLM_ENABLE_THINKING,
    VLLM_MODEL,
)


def get_llm(*, temperature: float = 0.2, max_tokens: int = 2048):
    """对接内网 OpenAI 兼容 vLLM。"""
    return init_chat_model(
        model=VLLM_MODEL,
        model_provider="openai",
        base_url=VLLM_BASE_URL,
        api_key=VLLM_API_KEY,
        temperature=temperature,
        max_tokens=max_tokens,
        extra_body={
            "chat_template_kwargs": {"enable_thinking": VLLM_ENABLE_THINKING},
        },
    )
