import re
from typing import Any

from app.config import settings
from app.graph.state import AgentState
from app.services.guardrails import is_blocked_prompt
from app.services.llm import compose_answer
from app.services.retriever import Retriever
from app.services.tooling import list_incidents, lookup_ticket, search_incidents


def classify_intent(state: AgentState) -> dict[str, Any]:
    question = state["question"].lower()
    if is_blocked_prompt(question):
        return {"intent": "blocked"}
    if re.search(r"\b(ticket|tickets|incident|incidents)\b", question) or re.search(
        r"\binc-\d+\b", question, re.IGNORECASE
    ):
        return {"intent": "ticket_lookup"}
    return {"intent": "knowledge_qa"}


def retrieve_docs(state: AgentState, retriever: Retriever) -> dict[str, Any]:
    return {"retrieved_docs": retriever.retrieve(state["question"])}


def maybe_call_tool(state: AgentState) -> dict[str, Any]:
    """Return explicit keys only — LangGraph merges partial updates; in-place mutation is unreliable."""
    if state["intent"] == "blocked":
        return {}

    q = state["question"]
    ql = q.lower()
    used_tool = False
    tool_result: dict[str, Any] | None = None

    if state["intent"] == "ticket_lookup":
        match = re.search(r"\b(INC-\d+)\b", q, re.IGNORECASE)
        if match:
            return {"used_tool": True, "tool_result": lookup_ticket(match.group(1))}

        if re.search(r"\b(list|show|what are|give me)\b", ql) and re.search(
            r"\b(open|active)\b", ql
        ) and re.search(r"\b(incident|incidents|ticket|tickets)\b", ql):
            return {"used_tool": True, "tool_result": list_incidents(status="open", limit=12)}

        if re.search(r"\b(all|every)\b", ql) and re.search(r"\b(incident|incidents|ticket|tickets)\b", ql):
            return {"used_tool": True, "tool_result": list_incidents(status=None, limit=50)}

        if re.search(r"\b(recent|latest)\b", ql) and re.search(r"\bincident", ql):
            return {"used_tool": True, "tool_result": list_incidents(status=None, limit=6)}

    topic_pat = r"(?:about|for|related to|mentioning|involving|regarding|concerning)\s+(.+?)(?:\?|$)"
    about = re.search(topic_pat, q, re.IGNORECASE | re.DOTALL)
    if about and re.search(
        r"\b(find|search|list|show|give|tell|which|any|are there)\b",
        ql,
    ) and re.search(r"\b(incident|incidents|ticket|tickets)\b", ql):
        used_tool = True
        tool_result = search_incidents(about.group(1).strip(), limit=8)
    else:
        related_only = re.search(
            r"(?:related to|about|regarding|concerning|mentioning|involving)\s+(.+?)(?:\?|$)",
            q,
            re.IGNORECASE | re.DOTALL,
        )
        if related_only and re.search(r"\b(incident|incidents|ticket|tickets)\b", ql):
            topic = related_only.group(1).strip()
            if len(topic) >= 2:
                used_tool = True
                tool_result = search_incidents(topic, limit=8)

    if used_tool:
        return {"used_tool": True, "tool_result": tool_result}
    return {"used_tool": False, "tool_result": None}


def generate_answer(state: AgentState) -> dict[str, Any]:
    if state["intent"] == "blocked":
        return {
            "answer": "Request blocked by safety policy.",
            "fallback_used": True,
            "citations": [],
        }

    tool_result = state.get("tool_result")
    used_tool = bool(state.get("used_tool"))
    # Merge can leave tool_result as None or {} — both skip the Bedrock tool block unless we recompute.
    if not tool_result:
        t = maybe_call_tool(state)
        tool_result = t.get("tool_result")
        used_tool = bool(t.get("used_tool"))

    # Do not gate on RAG similarity alone — it produced false "no trusted evidence" when
    # LangGraph state was incomplete. compose_answer + Bedrock handle thin retrieval.

    answer = compose_answer(
        question=state["question"],
        context_docs=state["retrieved_docs"][: settings.max_context_chunks],
        tool_result=tool_result,
    )
    citations = [
        {
            "source": doc.get("source", "unknown"),
            "chunk_id": doc.get("chunk_id", "na"),
            "score": float(doc.get("score", 0.0)),
            "section_path": doc.get("section_path"),
            "section_title": doc.get("section_title"),
            "page_start": doc.get("page_start"),
            "page_end": doc.get("page_end"),
        }
        for doc in state["retrieved_docs"][: settings.max_context_chunks]
    ]
    return {"answer": answer, "fallback_used": False, "citations": citations}
