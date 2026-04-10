from typing import Iterable


BLOCKED_PATTERNS = [
    "ignore all previous instructions",
    "reveal system prompt",
    "export credentials",
    "password dump",
]


def is_blocked_prompt(question: str) -> bool:
    lowered = question.lower()
    return any(pattern in lowered for pattern in BLOCKED_PATTERNS)


def is_low_confidence(retrieved: Iterable[dict], min_score: float) -> bool:
    rows = list(retrieved)
    if not rows:
        return True
    top_score = rows[0].get("score", 0.0)
    return float(top_score) < min_score


def fallback_message() -> str:
    return (
        "I do not have enough trusted evidence to answer confidently. "
        "Please refine the question or open a support ticket for a human follow-up."
    )
