from __future__ import annotations

import json

from app.config import settings
from app.services.bedrock import try_bedrock


def _tool_json(tool: dict) -> str:
    return json.dumps(tool, indent=2)


def _format_context_block(idx: int, doc: dict) -> str:
    meta = []
    if doc.get("section_path"):
        meta.append(f"section_path: {doc['section_path']}")
    if doc.get("page_start") is not None:
        ps, pe = doc.get("page_start"), doc.get("page_end")
        meta.append(f"pages: {ps}" + (f"-{pe}" if pe != ps else ""))
    header = f"[{idx}] " + (" | ".join(meta) if meta else "internal doc")
    text = (doc.get("text") or "").strip()
    return f"{header}\nsource_file: {doc.get('source', 'unknown')}\n{text}"


def compose_answer_bedrock(
    question: str,
    context_docs: list[dict],
    tool_result: dict | None = None,
) -> str | None:
    if not settings.use_bedrock:
        return None

    context_parts = [_format_context_block(i + 1, d) for i, d in enumerate(context_docs[: settings.max_context_chunks])]
    tool_block = ""
    if tool_result:
        tool_block = f"\n\nTool result (authoritative for incident / ITSM fields):\n{_tool_json(tool_result)}\n"

    tool_rules = ""
    if tool_result:
        tool_rules = (
            "If the tool result lists incidents or tickets, you MUST answer using those rows "
            "(IDs, titles, status). Do not refuse or say evidence is insufficient when the tool "
            "returned matching incidents. "
        )

    user_payload = (
        "Use the numbered evidence passages and the tool result below. "
        + tool_rules
        + "If there is no tool result and no relevant passages, say briefly what is missing. "
        "Do not use canned phrases like 'trusted evidence' or 'support ticket'. "
        "End with a short 'Sources:' line listing passage numbers used (or 'Sources: tool only').\n\n"
        f"Question:\n{question}\n"
        f"{tool_block}\n"
        "Evidence:\n"
        + "\n\n---\n\n".join(context_parts)
    )

    system = (
        "You are an enterprise internal Ops Copilot. Be concise and accurate. "
        "Do not invent policies or ticket states not supported by evidence or tool output. "
        "Cite evidence as [1], [2], etc., matching the numbered passages."
    )
    return try_bedrock(user_payload, system_prompt=system)


def _format_tool_block_template(tool_result: dict) -> list[str]:
    lines: list[str] = []
    lines.append("Synthetic ITSM snapshot (demo data — not a live API):")
    lines.append("")
    if not tool_result.get("found"):
        op = tool_result.get("op")
        if op == "get_incident":
            lines.append(f"Incident {tool_result.get('ticket_id', '?')} was not found.")
        else:
            lines.append("No matching incidents in the synthetic catalog.")
        return lines

    op = tool_result.get("op")
    if op == "get_incident" and tool_result.get("incident"):
        inc = tool_result["incident"]
        lines.append(
            f"{inc['ticket_id']}: {inc['title']} — status={inc['status']}, "
            f"priority={inc['priority']}, team={inc['assignee_team']}, service={inc['service']}"
        )
        if inc.get("summary"):
            lines.append(f"Summary: {inc['summary']}")
        if inc.get("resolution_notes"):
            lines.append(f"Resolution: {inc['resolution_notes']}")
        return lines

    if op in ("list_incidents", "search_incidents"):
        label = "Open incidents" if tool_result.get("filter_status") == "open" else "Incidents"
        if tool_result.get("query"):
            label = f"Search ({tool_result['query']})"
        lines.append(f"{label} ({tool_result.get('count', 0)} items):")
        for inc in tool_result.get("incidents") or []:
            lines.append(
                f"  - {inc['ticket_id']}: [{inc['status']}] {inc['title']} ({inc['service']})"
            )
        return lines

    lines.append(_tool_json(tool_result))
    return lines


def compose_answer_template(
    question: str,
    context_docs: list[dict],
    tool_result: dict | None = None,
) -> str:
    if not context_docs and not tool_result:
        return "I could not find reliable information in the indexed support docs."

    lines: list[str] = []
    lines.append(f"Question: {question}")
    lines.append("")
    if tool_result:
        lines.extend(_format_tool_block_template(tool_result))
        lines.append("")
    if context_docs:
        lines.append("Evidence from internal docs:")
        for idx, doc in enumerate(context_docs[:4], start=1):
            snippet = doc.get("text", "")[:300].replace("\n", " ")
            source = doc.get("source", "unknown")
            sec = doc.get("section_path")
            tag = f"[{source}]" + (f" ({sec})" if sec else "")
            lines.append(f"{idx}. {tag} {snippet}")
        lines.append("")
    else:
        lines.append("(No retrieved doc passages; answer uses tool output only.)")
        lines.append("")
    lines.append("Answer: Based on the cited evidence above, this is the best supported response.")
    return "\n".join(lines)


def compose_tool_only_answer(question: str, tool_result: dict) -> str:
    """Deterministic response for ticket/tool queries (fast path, no LLM)."""
    lines: list[str] = []
    lines.append(f"Question: {question}")
    lines.append("")
    lines.extend(_format_tool_block_template(tool_result))
    lines.append("")
    lines.append("Sources: tool only")
    return "\n".join(lines)


def compose_tool_polished_answer(question: str, tool_result: dict) -> str | None:
    """
    LLM-polished ticket response that is strictly grounded in tool JSON.
    Uses no retrieved doc chunks to keep latency lower than full RAG synthesis.
    """
    if not settings.use_bedrock:
        return None
    payload = (
        "Answer the question using ONLY the tool JSON below.\n"
        "Do not invent any fields or incidents.\n"
        "If count is 0, clearly say no matching incidents were found.\n"
        "Keep the response concise and factual.\n"
        "End with: Sources: tool only\n\n"
        f"Question:\n{question}\n\n"
        f"Tool JSON:\n{_tool_json(tool_result)}\n"
    )
    system = (
        "You are Ops Copilot. Tool output is authoritative. "
        "Never contradict or add facts beyond the tool JSON."
    )
    return try_bedrock(payload, system_prompt=system)


def compose_answer(
    question: str,
    context_docs: list[dict],
    tool_result: dict | None = None,
) -> str:
    bedrock = compose_answer_bedrock(question, context_docs, tool_result)
    if bedrock:
        return bedrock
    return compose_answer_template(question, context_docs, tool_result)
