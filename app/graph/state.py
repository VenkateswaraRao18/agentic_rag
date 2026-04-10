from typing import Any, TypedDict


class AgentState(TypedDict):
    question: str
    intent: str
    retrieved_docs: list[dict[str, Any]]
    tool_result: dict[str, Any] | None
    answer: str
    citations: list[dict[str, Any]]
    used_tool: bool
    fallback_used: bool
