import pytest

from app.agent import graph as graph_module
from app.schemas.types import AgentAction, AgentStep, ToolResult


class _FailingGraph:
    async def ainvoke(self, initial):
        emit = initial["emit"]
        step = AgentStep(
            id="step-1",
            index=0,
            reasoning="Attempting web search",
            action=AgentAction(tool="web_search", args={"query": "hello"}),
            result=None,
            timestamp=1,
        )
        emit({"type": "step_start", "step": step.model_dump()})
        step.result = ToolResult(success=False, data=None, error="Search failed")
        emit({"type": "step_complete", "step": step.model_dump()})
        raise RuntimeError("planner crashed")


@pytest.mark.asyncio
async def test_run_agent_preserves_partial_steps_on_error(monkeypatch) -> None:
    monkeypatch.setattr(graph_module, "compiled_graph", _FailingGraph())
    events: list[dict[str, object]] = []

    def emit(event: dict[str, object]) -> None:
        events.append(event)

    result, usage = await graph_module.run_agent(task="hello", emit=emit)

    assert result.status == "error"
    assert result.totalSteps == 1
    assert len(result.steps) == 1
    assert result.steps[0].id == "step-1"
    assert result.steps[0].result is not None
    assert result.steps[0].result.success is False
    assert usage.totalTokens == 0
