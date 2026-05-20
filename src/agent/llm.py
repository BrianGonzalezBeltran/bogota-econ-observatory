"""
LLM configuration for the agent.
Supports Groq (default, free tier) with easy switching to other providers.
"""

import os
from langchain_groq import ChatGroq


def get_llm(
    provider: str = None,
    model: str = None,
    temperature: float = 0,
):
    """
    Get a configured LLM instance.

    Default: Groq with Llama 3.1 70B (free tier, fast inference).
    Set GROQ_API_KEY in environment or .env file.

    Args:
        provider: "groq" (default). Extensible to "openai", "anthropic".
        model: Model name. Defaults based on provider.
        temperature: 0 for deterministic tool-use.
    """
    provider = provider or os.getenv("LLM_PROVIDER", "groq")

    if provider == "groq":
        model = model or os.getenv("LLM_MODEL", "llama-3.3-70b-versatile")
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            raise ValueError(
                "GROQ_API_KEY not set. Get a free key at https://console.groq.com"
            )
        return ChatGroq(
            model=model,
            api_key=api_key,
            temperature=temperature,
        )
    else:
        raise ValueError(f"Unsupported provider: {provider}. Currently supported: groq")
