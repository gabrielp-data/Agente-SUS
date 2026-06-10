"""LangGraph agent for SINAN analysis."""
from __future__ import annotations

from typing import Any, TypedDict

from langgraph.graph import END, StateGraph

from agents.nodes import (
    analyze_intent,
    execute_sql_node,
    fix_sql_node,
    generate_answer_node,
    generate_chart_node,
    generate_sql,
    query_rag,
    validate_sql_node,
)
from utils.logger import get_logger

logger = get_logger("sinan_agent")


# ── State ─────────────────────────────────────────────────────────────────────


class AgentState(TypedDict, total=False):
    # Input
    question: str
    chat_history: list[dict]
    db_schema: dict

    # Intent analysis
    intent: str
    disease: str
    selected_tables: list[str]
    needs_chart: bool
    chart_type: str

    # RAG
    rag_context: str

    # SQL
    sql: str
    sql_valid: bool
    sql_error: str
    sql_explanation: str
    tables_used: list[str]
    columns_used: list[str]
    filters_applied: list[str]

    # Execution
    execution_error: str
    results: Any
    retry_count: int

    # Output
    chart: Any
    answer: str

    # Telemetry
    steps: list[str]
    total_input_tokens: int
    total_output_tokens: int


# ── Edge conditions ───────────────────────────────────────────────────────────


def _route_after_validate(state: AgentState) -> str:
    retry = state.get("retry_count", 0)
    if state.get("sql_valid"):
        return "execute_sql"
    if retry < 2:
        return "generate_sql"
    return "generate_answer"


def _route_after_execute(state: AgentState) -> str:
    if state.get("execution_error"):
        if state.get("retry_count", 0) < 2:
            return "fix_sql"
    return "generate_chart"


# ── Graph ─────────────────────────────────────────────────────────────────────


def build_graph() -> StateGraph:
    g = StateGraph(AgentState)

    g.add_node("analyze_intent",    analyze_intent)
    g.add_node("query_rag",         query_rag)
    g.add_node("generate_sql",      generate_sql)
    g.add_node("validate_sql",      validate_sql_node)
    g.add_node("execute_sql",       execute_sql_node)
    g.add_node("fix_sql",           fix_sql_node)
    g.add_node("generate_chart",    generate_chart_node)
    g.add_node("generate_answer",   generate_answer_node)

    g.set_entry_point("analyze_intent")
    g.add_edge("analyze_intent", "query_rag")
    g.add_edge("query_rag",      "generate_sql")
    g.add_edge("generate_sql",   "validate_sql")
    g.add_conditional_edges("validate_sql", _route_after_validate,
                             {"execute_sql": "execute_sql",
                              "generate_sql": "generate_sql",
                              "generate_answer": "generate_answer"})
    g.add_conditional_edges("execute_sql", _route_after_execute,
                             {"fix_sql": "fix_sql",
                              "generate_chart": "generate_chart"})
    g.add_edge("fix_sql",          "execute_sql")
    g.add_edge("generate_chart",   "generate_answer")
    g.add_edge("generate_answer",  END)

    return g


class SinanAgent:
    """High-level wrapper around the compiled LangGraph."""

    def __init__(self) -> None:
        self._graph = build_graph().compile()

    def run(
        self,
        question: str,
        chat_history: list[dict] | None = None,
        db_schema: dict | None = None,
    ) -> AgentState:
        """
        Execute the agent for a user question.

        Args:
            question:     Natural language question in Portuguese
            chat_history: Previous turns [{question, answer}]
            db_schema:    Loaded DB schema dict (passed in to avoid repeated DB calls)

        Returns:
            Final AgentState with answer, sql, chart, steps, etc.
        """
        initial_state: AgentState = {
            "question": question,
            "chat_history": chat_history or [],
            "db_schema": db_schema or {},
            "steps": [],
            "retry_count": 0,
            "total_input_tokens": 0,
            "total_output_tokens": 0,
        }

        logger.info("Agent iniciado — pergunta: %s", question[:80])
        result = self._graph.invoke(initial_state)
        logger.info(
            "Agent concluído — tokens: %d/%d steps: %d",
            result.get("total_input_tokens", 0),
            result.get("total_output_tokens", 0),
            len(result.get("steps", [])),
        )
        return result
