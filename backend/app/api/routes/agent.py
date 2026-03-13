import asyncio
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Request
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.graph import run_agent
from app.api.utils import (
    sse_event,
    sse_stream_from_queue,
)
from app.auth.session import require_session
from app.core.request_context import request_runtime_context, request_user_context
from app.core.utils import generate_id
from app.db.models import QueryRun, QueryStep
from app.db.session import SessionLocal, get_db
from app.schemas.types import AgentRequest, AppSession

router = APIRouter()


@router.post("/agent")
async def agent_run(
    request: Request,
    body: AgentRequest,
    session: AppSession = Depends(require_session),
    db: AsyncSession = Depends(get_db),
):
    run_id = generate_id()
    conversation_id = body.conversationId or generate_id()
    queue: asyncio.Queue[str | None] = asyncio.Queue()

    db_run = QueryRun(
        id=run_id,
        task=body.task,
        status="running",
        userId=session.userId,
        conversationId=conversation_id,
    )
    db.add(db_run)
    await db.commit()

    previous_turns: list[dict[str, str]] = []
    if body.conversationId:
        stmt = (
            select(QueryRun.task, QueryRun.answer)
            .where(
                and_(
                    QueryRun.conversationId == body.conversationId,
                    QueryRun.userId == session.userId,
                    QueryRun.id != run_id,
                    QueryRun.status == "completed",
                    QueryRun.answer.is_not(None),
                )
            )
            .order_by(QueryRun.createdAt.asc())
            .limit(10)
        )
        rows = (await db.execute(stmt)).all()
        previous_turns = [{"task": row[0], "answer": row[1]} for row in rows if row[1]]

    queue.put_nowait(sse_event({"type": "conversation_id", "conversationId": conversation_id}))

    async def _run() -> None:
        async with SessionLocal() as task_db:
            task_run = await task_db.get(QueryRun, run_id)
            if not task_run:
                queue.put_nowait(sse_event({"type": "error", "error": "Run not found"}))
                queue.put_nowait(None)
                return

            try:
                def emit(event):
                    queue.put_nowait(sse_event(event))

                with request_user_context(session.userId), request_runtime_context({"db": task_db, "session": session}):
                    result, usage = await run_agent(
                        task=body.task,
                        max_steps=body.maxSteps,
                        run_id=run_id,
                        emit=emit,
                        previous_turns=previous_turns,
                    )

                for step in result.steps:
                    if not step.action:
                        continue
                    task_db.add(
                        QueryStep(
                            id=step.id,
                            runId=run_id,
                            index=step.index,
                            reasoning=step.reasoning,
                            tool=step.action.tool if step.action else None,
                            args=step.action.args if step.action else None,
                            success=step.result.success if step.result else None,
                            result=step.result.data if step.result else None,
                            durationMs=step.durationMs,
                            timestamp=datetime.fromtimestamp(step.timestamp / 1000, tz=UTC),
                        )
                    )

                task_run.answer = result.answer
                task_run.status = result.status
                task_run.totalSteps = result.totalSteps
                task_run.durationMs = result.durationMs
                task_run.promptTokens = usage.promptTokens
                task_run.completionTokens = usage.completionTokens
                task_run.estimatedCost = usage.estimatedCost
                await task_db.commit()
            except Exception as err:  # noqa: BLE001
                task_run.status = "error"
                task_run.answer = str(err)
                await task_db.commit()
                queue.put_nowait(sse_event({"type": "error", "error": str(err)}))
            finally:
                queue.put_nowait(None)

    asyncio.create_task(_run())

    response = sse_stream_from_queue(queue)
    response.headers["X-Run-Id"] = run_id
    response.headers["X-Conversation-Id"] = conversation_id
    return response
