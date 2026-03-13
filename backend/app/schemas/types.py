from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class ToolResult(BaseModel):
    success: bool
    data: Any = None
    error: str | None = None


class ParameterDef(BaseModel):
    type: str
    description: str
    required: bool = False


class Citation(BaseModel):
    title: str
    url: str | None = None
    source: str
    snippet: str | None = None


class PlanStep(BaseModel):
    description: str
    tool: str | None
    reasoning: str


class AgentPlan(BaseModel):
    analysis: str
    steps: list[PlanStep]


class AgentAction(BaseModel):
    tool: str
    args: dict[str, Any] = Field(default_factory=dict)


class AgentStep(BaseModel):
    id: str
    index: int
    reasoning: str
    action: AgentAction | None = None
    result: ToolResult | None = None
    timestamp: int
    durationMs: int | None = None


AgentStatus = Literal["completed", "step_limit", "error", "aborted"]


class AgentResult(BaseModel):
    answer: str
    citations: list[Citation]
    steps: list[AgentStep]
    totalSteps: int
    durationMs: int
    status: AgentStatus


AgentState = Literal[
    "idle",
    "planning",
    "deciding",
    "executing",
    "synthesizing",
    "completed",
    "error",
    "aborted",
]


class TokenUsage(BaseModel):
    promptTokens: int = 0
    completionTokens: int = 0
    totalTokens: int = 0
    estimatedCost: float = 0.0


GPT4O_MINI_INPUT_COST = 0.15 / 1_000_000
GPT4O_MINI_OUTPUT_COST = 0.60 / 1_000_000


def add_usage(acc: TokenUsage, prompt: int, completion: int) -> TokenUsage:
    prompt_tokens = acc.promptTokens + prompt
    completion_tokens = acc.completionTokens + completion
    return TokenUsage(
        promptTokens=prompt_tokens,
        completionTokens=completion_tokens,
        totalTokens=prompt_tokens + completion_tokens,
        estimatedCost=prompt_tokens * GPT4O_MINI_INPUT_COST
        + completion_tokens * GPT4O_MINI_OUTPUT_COST,
    )


class NextToolCall(BaseModel):
    type: Literal["tool_call"]
    reasoning: str
    tool: str
    args: dict[str, Any] = Field(default_factory=dict)


class NextComplete(BaseModel):
    type: Literal["complete"]
    reasoning: str
    answer: Any

    @property
    def answer_text(self) -> str:
        val = self.answer
        if isinstance(val, str):
            return val
        if isinstance(val, dict):
            if isinstance(val.get("text"), str):
                return val["text"]
            if isinstance(val.get("content"), str):
                return val["content"]
        return str(val)


NextAction = NextToolCall | NextComplete


class SynthesisResult(BaseModel):
    answer: str
    citations: list[Citation]


class AgentRequest(BaseModel):
    task: str = Field(min_length=1, max_length=2000)
    maxSteps: int = Field(default=10, ge=1, le=30)
    userId: str | None = None
    conversationId: str | None = None


class IngestRequest(BaseModel):
    incremental: bool = True


class DriveFile(BaseModel):
    id: str
    name: str
    mimeType: str
    modifiedTime: str
    size: str | None = None


class IngestError(BaseModel):
    file: str
    error: str


class IngestProgress(BaseModel):
    total: int
    processed: int
    current: str | None = None
    errors: list[IngestError] = Field(default_factory=list)


class SessionUser(BaseModel):
    id: str
    email: str
    name: str | None = None


class AppSession(BaseModel):
    userId: str
    user: SessionUser


class HistoryItem(BaseModel):
    id: str
    task: str
    answer: str | None
    status: str
    totalSteps: int
    durationMs: int
    promptTokens: int
    completionTokens: int
    estimatedCost: float
    conversationId: str | None
    createdAt: datetime

