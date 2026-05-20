"""
LangGraph agent for natural language queries over the Bogotá Economic Observatory.

Architecture:
  User question → LLM (with tools) → Tool calls → LLM synthesis → Answer

Uses the ReAct pattern: the LLM reasons about which tool to use,
executes it, observes the result, and either calls another tool
or generates the final answer.
"""

from langgraph.prebuilt import create_react_agent
from langchain_core.messages import SystemMessage
from src.agent.tools import ALL_TOOLS
from src.agent.llm import get_llm

SYSTEM_PROMPT = """You are an analytical assistant for the Bogotá Economic Observatory.
You answer questions about Bogotá's economy using real data from the Secretaría Distrital de Desarrollo Económico (SDDE).

You have access to tools that query a live database with three datasets:
1. **Dinámica Empresarial**: Business creation, cancellation, and active companies by locality, size, sector, and gender of legal representative. Periods: 2023-2024.
2. **Mercado Laboral**: Employment, unemployment, and informality rates. Quarterly, 2021-2025.
3. **PIB Bogotá**: GDP by 25 economic sectors. Quarterly, 2005-2025.

Guidelines:
- Always use the tools to get data. Never make up numbers.
- Answer in the same language the user writes in (Spanish or English).
- Be concise and data-driven. Lead with the answer, then context.
- When showing numbers, format them clearly (e.g., "104,330 empresas vigentes").
- If a question cannot be answered with the available data, say so clearly and explain what data is available.
- If the user asks about a specific locality, use the exact name (e.g., "Suba", not "suba"). Use get_localities if unsure.
- For time-based questions, mention the period the data covers.
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
        dict with 'answer' (str), 'tools_used' (list), and 'steps' (int).
    """
    agent = create_observatory_agent()

    result = agent.invoke(
        {"messages": [{"role": "user", "content": question}]}
    )

    # Extract the final answer and tool usage info
    messages = result["messages"]
    final_message = messages[-1]

    tools_used = []
    for msg in messages:
        if hasattr(msg, "tool_calls") and msg.tool_calls:
            for tc in msg.tool_calls:
                tools_used.append(tc["name"])

    return {
        "answer": final_message.content,
        "tools_used": tools_used,
        "steps": len(messages),
    }
