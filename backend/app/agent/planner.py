from __future__ import annotations

import json
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.core.errors import LLMParseError
from app.schemas.types import (
    AgentPlan,
    AgentStep,
    Citation,
    NextComplete,
    NextToolCall,
    SynthesisResult,
)
from app.services.llm import LLMUsage, chat_json, chat_stream, parse_json_object
from app.tools.registry import get_tool_registry

PLAN_SYSTEM_PROMPT = """You are an autonomous AI research agent called Archon.
When given a task, create a concise plan with clear steps.

Available tools:
__TOOLS__

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
__TOOLS__

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


def _normalize_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    return str(value)


def _normalize_tool(value: Any) -> str | None:
    if isinstance(value, str):
        cleaned = value.strip()
        return cleaned if cleaned else None
    return None


def _find_key(payload: dict[str, Any], target: str) -> str | None:
    if target in payload:
        return target
    target_lower = target.lower()
    for key in payload.keys():
        if key.strip().lower() == target_lower:
            return key
    for key in payload.keys():
        if target_lower in key.lower():
            return key
    return None


def _coerce_plan_payload(payload: Any) -> AgentPlan:
    analysis = ""
    steps_value: Any = []

    if isinstance(payload, dict):
        analysis_key = _find_key(payload, "analysis")
        if analysis_key:
            analysis = _normalize_text(payload.get(analysis_key))
        steps_value = payload.get("steps")
        if steps_value is None and isinstance(payload.get("plan"), dict):
            plan_payload = payload["plan"]
            if not analysis:
                analysis = _normalize_text(plan_payload.get("analysis"))
            steps_value = plan_payload.get("steps")
    elif isinstance(payload, list):
        steps_value = payload
    elif isinstance(payload, str):
        analysis = payload
        steps_value = []

    steps: list[dict[str, Any]] = []
    if isinstance(steps_value, list):
        for item in steps_value:
            if isinstance(item, dict):
                description = _normalize_text(
                    item.get("description")
                    or item.get("step")
                    or item.get("task")
                    or item.get("action")
                )
                reasoning = _normalize_text(item.get("reasoning") or item.get("why") or item.get("rationale"))
                tool = _normalize_tool(item.get("tool") or item.get("tool_name"))
                steps.append({"description": description, "tool": tool, "reasoning": reasoning})
            else:
                steps.append({"description": _normalize_text(item), "tool": None, "reasoning": ""})

    steps = [step for step in steps if step["description"] or step["tool"] or step["reasoning"]]
    if not steps:
        steps = [
            {
                "description": "Provide the final answer.",
                "tool": None,
                "reasoning": "No tools required.",
            }
        ]

    return AgentPlan.model_validate({"analysis": analysis or "Generated a concise plan.", "steps": steps})


def _coerce_decision_payload(payload: Any) -> NextToolCall | NextComplete:
    if isinstance(payload, dict):
        type_value = _normalize_text(payload.get("type") or payload.get("action")).lower()
        tool_value = _normalize_tool(payload.get("tool") or payload.get("tool_name"))
        reasoning = _normalize_text(payload.get("reasoning") or payload.get("analysis"))
        args = payload.get("args") if isinstance(payload.get("args"), dict) else {}
        if type_value == "tool_call" or (tool_value and not type_value):
            return NextToolCall(
                type="tool_call",
                reasoning=reasoning or "Executing the next tool.",
                tool=tool_value or "",
                args=args,
            )
        if type_value == "complete":
            return NextComplete(
                type="complete",
                reasoning=reasoning or "Providing the best possible answer.",
                answer=payload.get("answer") or payload.get("final") or payload.get("result") or "",
            )
    return NextComplete(
        type="complete",
        reasoning="Providing the best possible answer.",
        answer=_normalize_text(payload),
    )


def _usage_from_context(err: LLMParseError) -> LLMUsage:
    usage = err.context.get("usage") if isinstance(err.context, dict) else None
    if isinstance(usage, dict):
        return LLMUsage(
            prompt_tokens=int(usage.get("prompt_tokens", 0) or 0),
            completion_tokens=int(usage.get("completion_tokens", 0) or 0),
        )
    return LLMUsage()


def _tools_description() -> str:
    return get_tool_registry().descriptions()


def _prompt_messages(system_template: str, user_text: str) -> list[dict[str, str]]:
    return [
        {"role": "system", "content": system_template},
        {"role": "user", "content": user_text},
    ]


async def create_plan(
    task: str,
    previous_turns: list[dict[str, str]] | None = None,
) -> tuple[AgentPlan, LLMUsage]:
    system = PLAN_SYSTEM_PROMPT.replace("__TOOLS__", _tools_description())
    if previous_turns:
        context = "\n\n".join(
            f"Turn {idx + 1}:\nQ: {row['task']}\nA: {row['answer'][:500]}"
            for idx, row in enumerate(previous_turns)
        )
        system += f"\nPrevious conversation context:\n{context}"
    messages = _prompt_messages(system, f"Task: {task}")
    try:
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
    except LLMParseError as err:
        try:
            payload = parse_json_object(err.raw_output)
        except json.JSONDecodeError as parse_err:
            raise err from parse_err
        plan = _coerce_plan_payload(payload)
        return plan, _usage_from_context(err)


async def decide_next_step(
    task: str,
    plan: AgentPlan,
    steps: list[AgentStep],
    previous_turns: list[dict[str, str]] | None = None,
) -> tuple[NextToolCall | NextComplete, LLMUsage]:
    system = DECIDE_SYSTEM_PROMPT.replace("__TOOLS__", _tools_description())
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
    try:
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
    except LLMParseError as err:
        try:
            payload = parse_json_object(err.raw_output)
        except json.JSONDecodeError as parse_err:
            raise err from parse_err
        return _coerce_decision_payload(payload), _usage_from_context(err)


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
