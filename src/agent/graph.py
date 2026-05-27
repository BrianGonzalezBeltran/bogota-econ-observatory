"""
LangGraph agent for natural language queries over the Bogotá Economic Observatory.

Architecture:
  User question → LLM (with tools) → Tool calls → LLM synthesis → Answer

Uses the ReAct pattern: the LLM reasons about which tool to use,
executes it, observes the result, and either calls another tool
or generates the final answer.
"""

import time
import logging
from langgraph.prebuilt import create_react_agent
from langchain_core.messages import SystemMessage
from src.agent.tools import ALL_TOOLS
from src.agent.llm import get_llm
from src.agent.observability import get_langfuse_handler

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are an analytical assistant for the Bogotá Economic Observatory.
You answer questions about Bogotá's economy using real data from the Secretaría Distrital de Desarrollo Económico (SDDE).

You have access to tools that query a live database with three datasets:
1. **Dinámica Empresarial**: Business creation, cancellation, and active companies by locality, size, sector, and gender of legal representative. Periods: 2023-2024.
2. **Mercado Laboral**: Employment, unemployment, and informality rates. Quarterly, 2021-2025.
3. **PIB Bogotá**: GDP by 25 economic sectors. Quarterly, 2005-2025.

TOOL USAGE RULES:
- Call a tool ONCE, then answer immediately with the data you received. Do NOT call the same tool again.
- Maximum 2 tool calls per question. After 2 calls, you MUST synthesize an answer.
- Never say you need more steps. Always provide the best answer possible with available data.

SYNTHESIS RULES (follow these strictly):
- LANGUAGE: Always respond in the same language the user wrote in. English question = English answer.
- STRUCTURE: Lead with a direct answer to the question, then supporting data.
- ACCURACY: Only state trends the numbers actually support. If values go from 57,271 to 19,934, that is a DECREASE, not an increase. Double-check directionality before writing.
- COMPARISONS: When asked to compare two datasets, explicitly state the relationship or correlation between them, not just list each dataset separately.
- DATA COVERAGE: State how many data points you have. If a time series has only 2 points, say "based on 2 available data points (Sep 2023 and Mar 2024)" — do not imply a robust trend.
- NUMBERS: Format clearly (e.g., "104,330 active businesses"). Round rates to 1 decimal (e.g., "8.8%").
- LIMITATIONS: If data is sparse or incomplete, note it briefly at the end. Do not speculate beyond the data.
- If a question cannot be answered with available data, say so clearly.
- For locality names, use exact casing (e.g., "Suba", not "suba"). Use get_localities if unsure.
"""


def create_observatory_agent():
    """Create and return the LangGraph agent."""
    llm = get_llm()

    agent = create_react_agent(
        model=llm,
        tools=ALL_TOOLS,
        prompt=SystemMessage(content=SYSTEM_PROMPT),
    )

    return agent


def ask(question: str) -> dict:
    """
    Ask a question to the Observatory agent.

    Args:
        question: Natural language question in Spanish or English.

    Returns:
        dict with 'answer', 'tools_used', 'steps', 'latency_ms', and 'trace_url'.
    """
    agent = create_observatory_agent()

    # Initialize Langfuse tracing
    langfuse_handler = get_langfuse_handler(
        tags=["observatory", "agent"],
        metadata={"question_language": "auto"},
    )

    start = time.perf_counter()

    result = agent.invoke(
        {"messages": [{"role": "user", "content": question}]},
        config={"callbacks": [langfuse_handler]},
    )

    latency_ms = round((time.perf_counter() - start) * 1000)

    # Extract the final answer and tool usage info
    messages = result["messages"]
    final_message = messages[-1]

    tools_used = []
    for msg in messages:
        if hasattr(msg, "tool_calls") and msg.tool_calls:
            for tc in msg.tool_calls:
                tools_used.append(tc["name"])

    # Build trace URL for debugging
    trace_id = langfuse_handler.last_trace_id
    trace_url = f"https://us.cloud.langfuse.com/trace/{trace_id}" if trace_id else None

    logger.info(
        "agent_query",
        extra={
            "question": question[:200],
            "tools_used": tools_used,
            "steps": len(messages),
            "latency_ms": latency_ms,
            "trace_url": trace_url,
        },
    )

    return {
        "answer": final_message.content,
        "tools_used": tools_used,
        "steps": len(messages),
        "latency_ms": latency_ms,
        "trace_url": trace_url,
    }
