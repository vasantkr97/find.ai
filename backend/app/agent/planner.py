from __future__ import annotations

from typing import Any, Literal

from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field

from app.schemas.types import (
    AgentPlan,
    AgentStep,
    Citation,
    NextComplete,
    NextToolCall,
    SynthesisResult,
)
from app.services.llm import LLMUsage, chat_json, chat_stream
from app.tools.registry import get_tool_registry

PLAN_SYSTEM_PROMPT = """You are an autonomous AI research agent called Archon.
When given a task, create a concise plan with clear steps.

Available tools:
{tools}

Respond in JSON:
{
  "analysis": "brief analysis",
  "steps": [
    {"description": "...", "tool": "tool_name or null", "reasoning": "..."}
  ]
}

Rules:
- Keep plans concise (1-15 steps)
- For simple questions answerable directly, use one step with tool: null
- Use tools only when needed
- Always end with a synthesis step (tool: null)
"""


DECIDE_SYSTEM_PROMPT = """You are Archon executing a task step by step.
Given task, plan, and previous steps, decide next action.

Available tools:
{tools}

Respond in JSON with either:
1) tool call:
{
  "type": "tool_call",
  "reasoning": "...",
  "tool": "tool_name",
  "args": {}
}
2) complete:
{
  "type": "complete",
  "reasoning": "...",
  "answer": "final answer"
}

Rules:
- If enough info is available, choose complete
- Never invent unknown tools
- Provide valid args for tools
"""


SYNTH_PROMPT = """You are Archon, an AI research agent.
Synthesize a clear, comprehensive answer using the provided step results.

Rules:
- Be concise but thorough
- Use markdown formatting
- Cite sources inline when available
- If uncertain, say so

Output markdown only.
"""


class PlanResponse(BaseModel):
    analysis: str
    steps: list[dict[str, Any]] = Field(default_factory=list)


class DecisionResponse(BaseModel):
    type: Literal["tool_call", "complete"]
    reasoning: str
    tool: str | None = None
    args: dict[str, Any] = Field(default_factory=dict)
    answer: Any = None


def _tools_description() -> str:
    return get_tool_registry().descriptions()


def _prompt_messages(system_template: str, user_text: str) -> list[dict[str, str]]:
    prompt = ChatPromptTemplate.from_messages([("system", system_template), ("user", "{input}")])
    rendered = prompt.invoke({"input": user_text})
    role_map = {"human": "user", "ai": "assistant", "system": "system"}
    return [
        {"role": role_map.get(m.type, "user"), "content": str(m.content)}
        for m in rendered.to_messages()
    ]


async def create_plan(
    task: str,
    previous_turns: list[dict[str, str]] | None = None,
) -> tuple[AgentPlan, LLMUsage]:
    system = PLAN_SYSTEM_PROMPT.format(tools=_tools_description())
    if previous_turns:
        context = "\n\n".join(
            f"Turn {idx + 1}:\nQ: {row['task']}\nA: {row['answer'][:500]}"
            for idx, row in enumerate(previous_turns)
        )
        system += f"\nPrevious conversation context:\n{context}"
    messages = _prompt_messages(system, f"Task: {task}")
    parsed, usage = await chat_json(messages, PlanResponse, temperature=0.3)
    plan = AgentPlan.model_validate(
        {
            "analysis": parsed.analysis,
            "steps": [
                {
                    "description": step.get("description", ""),
                    "tool": step.get("tool"),
                    "reasoning": step.get("reasoning", ""),
                }
                for step in parsed.steps
            ],
        }
    )
    return plan, usage


async def decide_next_step(
    task: str,
    plan: AgentPlan,
    steps: list[AgentStep],
    previous_turns: list[dict[str, str]] | None = None,
) -> tuple[NextToolCall | NextComplete, LLMUsage]:
    system = DECIDE_SYSTEM_PROMPT.format(tools=_tools_description())
    if previous_turns:
        context = "\n\n".join(
            f"Turn {idx + 1}:\nQ: {row['task']}\nA: {row['answer'][:500]}"
            for idx, row in enumerate(previous_turns)
        )
        system += f"\nPrevious conversation context:\n{context}"

    step_summary = "\n\n".join(
        f"Step {index + 1}: [{step.action.tool if step.action else 'reasoning'}] {step.reasoning}\n"
        f"Result: {step.result.model_dump_json() if step.result else 'no result'}"
        for index, step in enumerate(steps)
    )

    user_message = (
        f"Task: {task}\n\n"
        f"Original Plan:\n{plan.analysis}\n"
        + "\n".join(
            f"{index + 1}. {row.description} (tool: {row.tool or 'none'})"
            for index, row in enumerate(plan.steps)
        )
        + f"\n\nSteps completed so far:\n{step_summary or 'None yet - this is the first step.'}\n\n"
        + "Decide the next action."
    )
    messages = _prompt_messages(system, user_message)
    parsed, usage = await chat_json(messages, DecisionResponse, temperature=0.2)

    if parsed.type == "complete":
        complete_action = NextComplete(
            type="complete", reasoning=parsed.reasoning, answer=parsed.answer
        )
        return complete_action, usage
    tool_action = NextToolCall(
        type="tool_call",
        reasoning=parsed.reasoning,
        tool=parsed.tool or "",
        args=parsed.args or {},
    )
    return tool_action, usage


def extract_citations_from_steps(steps: list[AgentStep]) -> list[Citation]:
    citations: list[Citation] = []
    seen: set[str] = set()
    for step in steps:
        if not step.result or not step.result.success or not step.action:
            continue
        data = step.result.data if isinstance(step.result.data, dict) else {}
        if step.action.tool == "web_search":
            for row in data.get("results", []):
                key = row.get("url") or row.get("title")
                if not key or key in seen:
                    continue
                seen.add(key)
                citations.append(
                    Citation(
                        title=row.get("title") or "Web result",
                        url=row.get("url"),
                        source="web_search",
                        snippet=row.get("snippet"),
                    )
                )
        elif step.action.tool == "web_scrape":
            key = data.get("url")
            if key and key not in seen:
                seen.add(key)
                citations.append(
                    Citation(
                        title=data.get("title") or "Webpage",
                        url=key,
                        source="web_scrape",
                        snippet=data.get("description"),
                    )
                )
        elif step.action.tool == "drive_search":
            for row in data.get("results", []):
                key = row.get("fileId") or row.get("fileName")
                if not key or key in seen:
                    continue
                seen.add(key)
                citations.append(
                    Citation(
                        title=row.get("fileName") or "Drive file",
                        source="drive_search",
                        snippet=row.get("content", "")[:200],
                    )
                )
        elif step.action.tool == "vector_search":
            for row in data.get("results", []):
                key = row.get("fileId") or row.get("source")
                if not key or key in seen:
                    continue
                seen.add(key)
                citations.append(
                    Citation(
                        title=row.get("source") or "Document",
                        source="vector_search",
                        snippet=(row.get("content") or "")[:200],
                    )
                )
    return citations


async def synthesize_answer_stream(
    task: str,
    steps: list[AgentStep],
    on_chunk: Any,
) -> tuple[SynthesisResult, LLMUsage]:
    step_details = "\n\n".join(
        f"Step {idx + 1} [{step.action.tool if step.action else 'reasoning'}]: {step.reasoning}\n"
        f"Result: {step.result.model_dump_json() if step.result else 'no result'}"
        for idx, step in enumerate(steps)
    )
    messages = [
        {"role": "system", "content": SYNTH_PROMPT},
        {
            "role": "user",
            "content": f"Task: {task}\n\nResearch steps and results:\n{step_details}\n\nSynthesize final answer.",
        },
    ]
    answer, usage = await chat_stream(messages, on_chunk, temperature=0.3, max_tokens=4096)
    citations = extract_citations_from_steps(steps)
    return SynthesisResult(answer=answer, citations=citations), usage
