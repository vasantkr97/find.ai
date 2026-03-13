from __future__ import annotations

import asyncio
import time
from typing import Any, TypedDict, cast

from langgraph.graph import END, StateGraph

from app.agent.executor import execute_tool
from app.agent.planner import create_plan, decide_next_step, synthesize_answer_stream
from app.core.errors import AgentAbortedError, to_error_message
from app.core.utils import generate_id
from app.schemas.types import (
    AgentAction,
    AgentResult,
    AgentState,
    AgentStep,
    NextComplete,
    TokenUsage,
    ToolResult,
    add_usage,
)
from app.tools.registry import get_tool_registry


class AgentGraphState(TypedDict, total=False):
    task: str
    max_steps: int
    run_id: str
    previous_turns: list[dict[str, str]]
    steps: list[AgentStep]
    plan: Any
    decision: Any
    usage: TokenUsage
    result: AgentResult
    status: str
    emit: Any
    signal: asyncio.Event | None
    force_synthesize: bool


def _emit(state: AgentGraphState, event: dict[str, Any]) -> None:
    emitter = state["emit"]
    emitter(event)


def _check_aborted(state: AgentGraphState) -> None:
    signal = state.get("signal")
    if signal and signal.is_set():
        raise AgentAbortedError()


async def planning_node(state: AgentGraphState) -> AgentGraphState:
    _emit(state, {"type": "state_change", "state": "planning"})
    _emit(state, {"type": "thinking", "content": "Analyzing task and creating a plan..."})
    _check_aborted(state)
    plan, usage = await create_plan(state["task"], state.get("previous_turns"))
    usage_total = add_usage(state["usage"], usage.prompt_tokens, usage.completion_tokens)
    _emit(state, {"type": "plan", "plan": plan.model_dump()})
    needs_tools = any(step.tool is not None for step in plan.steps)
    return {"plan": plan, "usage": usage_total, "force_synthesize": not needs_tools}


async def deciding_node(state: AgentGraphState) -> AgentGraphState:
    _check_aborted(state)
    _emit(state, {"type": "state_change", "state": "deciding"})
    _emit(
        state,
        {"type": "thinking", "content": f"Deciding next action (step {len(state['steps']) + 1}/{state['max_steps']})..."},
    )
    decision, usage = await decide_next_step(
        state["task"],
        state["plan"],
        state["steps"],
        state.get("previous_turns"),
    )
    usage_total = add_usage(state["usage"], usage.prompt_tokens, usage.completion_tokens)

    if isinstance(decision, NextComplete):
        completion_step = AgentStep(
            id=generate_id(),
            index=len(state["steps"]),
            reasoning=decision.reasoning,
            action=None,
            result=ToolResult(success=True, data={"answer": decision.answer_text}),
            timestamp=int(time.time() * 1000),
        )
        steps = [*state["steps"], completion_step]
        _emit(state, {"type": "step_complete", "step": completion_step.model_dump()})
        return {"decision": decision, "usage": usage_total, "steps": steps, "force_synthesize": True}

    if not get_tool_registry().has(decision.tool):
        completion_step = AgentStep(
            id=generate_id(),
            index=len(state["steps"]),
            reasoning=f"Attempted invalid tool '{decision.tool}'. Completing with available information.",
            action=None,
            result=ToolResult(success=True, data={"answer": decision.reasoning}),
            timestamp=int(time.time() * 1000),
        )
        steps = [*state["steps"], completion_step]
        _emit(state, {"type": "step_complete", "step": completion_step.model_dump()})
        return {"usage": usage_total, "steps": steps, "force_synthesize": True}

    return {"decision": decision, "usage": usage_total}


async def executing_node(state: AgentGraphState) -> AgentGraphState:
    _check_aborted(state)
    decision = state["decision"]
    _emit(state, {"type": "state_change", "state": "executing"})
    step = AgentStep(
        id=generate_id(),
        index=len(state["steps"]),
        reasoning=decision.reasoning,
        action=AgentAction(tool=decision.tool, args=decision.args or {}),
        result=None,
        timestamp=int(time.time() * 1000),
    )
    _emit(state, {"type": "step_start", "step": step.model_dump()})
    start = time.time()
    result = await execute_tool(decision.tool, decision.args or {})
    step.result = result
    step.durationMs = int((time.time() - start) * 1000)
    steps = [*state["steps"], step]
    _emit(state, {"type": "step_complete", "step": step.model_dump()})
    return {"steps": steps}


async def synthesizing_node(state: AgentGraphState) -> AgentGraphState:
    _check_aborted(state)
    _emit(state, {"type": "state_change", "state": "synthesizing"})
    _emit(state, {"type": "thinking", "content": "Synthesizing final answer..."})

    def _on_chunk(chunk: str) -> None:
        _emit(state, {"type": "answer_chunk", "content": chunk})

    synthesis, usage = await synthesize_answer_stream(state["task"], state["steps"], _on_chunk)
    usage_total = add_usage(state["usage"], usage.prompt_tokens, usage.completion_tokens)
    reached_limit = len(state["steps"]) >= state["max_steps"] and bool(state["steps"][-1].action)
    result = AgentResult(
        answer=synthesis.answer,
        citations=synthesis.citations,
        steps=state["steps"],
        totalSteps=len(state["steps"]),
        durationMs=0,
        status="step_limit" if reached_limit else "completed",
    )
    return {"result": result, "usage": usage_total}


def route_after_planning(state: AgentGraphState) -> str:
    return "synthesizing" if state.get("force_synthesize") else "deciding"


def route_after_deciding(state: AgentGraphState) -> str:
    if state.get("force_synthesize"):
        return "synthesizing"
    if len(state["steps"]) >= state["max_steps"]:
        return "synthesizing"
    return "executing"


def route_after_executing(state: AgentGraphState) -> str:
    if len(state["steps"]) >= state["max_steps"]:
        return "synthesizing"
    return "deciding"


graph = StateGraph(AgentGraphState)
graph.add_node("planning", planning_node)
graph.add_node("deciding", deciding_node)
graph.add_node("executing", executing_node)
graph.add_node("synthesizing", synthesizing_node)
graph.set_entry_point("planning")
graph.add_conditional_edges("planning", route_after_planning, {"deciding": "deciding", "synthesizing": "synthesizing"})
graph.add_conditional_edges("deciding", route_after_deciding, {"executing": "executing", "synthesizing": "synthesizing"})
graph.add_conditional_edges("executing", route_after_executing, {"deciding": "deciding", "synthesizing": "synthesizing"})
graph.add_edge("synthesizing", END)
compiled_graph = graph.compile()


async def run_agent(
    *,
    task: str,
    emit: Any,
    max_steps: int = 10,
    run_id: str | None = None,
    previous_turns: list[dict[str, str]] | None = None,
    signal: asyncio.Event | None = None,
) -> tuple[AgentResult, TokenUsage]:
    start = time.time()
    initial: AgentGraphState = {
        "task": task,
        "max_steps": max_steps,
        "run_id": run_id or generate_id(),
        "previous_turns": previous_turns or [],
        "steps": [],
        "usage": TokenUsage(),
        "emit": emit,
        "signal": signal,
        "force_synthesize": False,
    }
    try:
        final = cast(AgentGraphState, await cast(Any, compiled_graph).ainvoke(initial))
        result = final.get("result")
        if not result:
            result = AgentResult(
                answer="No result generated.",
                citations=[],
                steps=final.get("steps", []),
                totalSteps=len(final.get("steps", [])),
                durationMs=0,
                status="error",
            )
        result.durationMs = int((time.time() - start) * 1000)
        usage = final.get("usage", TokenUsage())
        emit({"type": "state_change", "state": "completed"})
        emit({"type": "complete", "result": result.model_dump(), "usage": usage.model_dump()})
        return result, usage
    except Exception as err:  # noqa: BLE001
        aborted = isinstance(err, AgentAbortedError)
        status: AgentState = "aborted" if aborted else "error"
        message = "The request was cancelled." if aborted else f"An error occurred while processing your request: {to_error_message(err)}"
        partial_steps = initial.get("steps", [])
        result = AgentResult(
            answer=message,
            citations=[],
            steps=partial_steps,
            totalSteps=len(partial_steps),
            durationMs=int((time.time() - start) * 1000),
            status="aborted" if aborted else "error",
        )
        emit({"type": "state_change", "state": status})
        emit({"type": "error", "error": to_error_message(err)})
        return result, initial["usage"]
