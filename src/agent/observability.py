"""
Langfuse observability for the Observatory agent.
Provides tracing of LLM calls, tool usage, latency, and token counts.
"""

from langfuse.langchain import CallbackHandler


def get_langfuse_handler(**kwargs) -> CallbackHandler:
    """
    Create a Langfuse callback handler for LangGraph tracing.
    
    Reads LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY, and LANGFUSE_HOST
    from environment variables (loaded via systemd EnvironmentFile).
    """
    return CallbackHandler()
