from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class AskRequest(BaseModel):
    """Body must be JSON with a "question" key — not plain text."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "question": "Check ticket INC-1001 status",
            }
        }
    )

    question: str = Field(
        min_length=3,
        max_length=4000,
        description="Your support or ops question (string inside JSON).",
    )
    user_id: str | None = None
    top_k: int | None = None


class Citation(BaseModel):
    source: str
    chunk_id: str
    score: float
    section_path: str | None = None
    section_title: str | None = None
    page_start: int | None = None
    page_end: int | None = None


class AskResponse(BaseModel):
    answer: str
    intent: str
    citations: list[Citation] = Field(default_factory=list)
    used_tool: bool = False
    fallback_used: bool = False
    latency_ms: int
    debug: dict[str, Any] = Field(default_factory=dict)
