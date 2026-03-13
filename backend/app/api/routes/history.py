from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import and_, delete, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.session import require_session
from app.db.models import QueryRun, QueryStep, User
from app.db.session import get_db
from app.schemas.types import AppSession

router = APIRouter()


def _run_payload(run: QueryRun, user: User | None) -> dict[str, object]:
    return {
        "id": run.id,
        "task": run.task,
        "answer": run.answer,
        "status": run.status,
        "totalSteps": run.totalSteps,
        "durationMs": run.durationMs,
        "promptTokens": run.promptTokens,
        "completionTokens": run.completionTokens,
        "estimatedCost": run.estimatedCost,
        "conversationId": run.conversationId,
        "createdAt": run.createdAt,
        "user": (
            {"id": user.id, "name": user.name, "email": user.email}
            if user
            else None
        ),
    }


@router.get("/history")
async def history_list(
    limit: int = Query(default=20, le=100),
    cursor: str | None = None,
    search: str | None = None,
    stats: bool = False,
    session: AppSession = Depends(require_session),
    db: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    where = [QueryRun.userId == session.userId]
    if search:
        where.append(QueryRun.task.ilike(f"%{search}%"))

    stmt = (
        select(QueryRun, User)
        .join(User, QueryRun.userId == User.id, isouter=True)
        .where(and_(*where))
        .order_by(desc(QueryRun.createdAt))
        .limit(limit + 1)
    )
    if cursor:
        cursor_row = await db.get(QueryRun, cursor)
        if cursor_row:
            stmt = stmt.where(QueryRun.createdAt <= cursor_row.createdAt, QueryRun.id != cursor)

    rows = (await db.execute(stmt)).all()
    has_more = len(rows) > limit
    rows = rows[:limit]
    items = [_run_payload(run, user) for run, user in rows]
    next_cursor = items[-1]["id"] if has_more and items else None

    if stats:
        total_runs = await db.scalar(select(func.count()).select_from(QueryRun).where(and_(*where)))
        completed_runs = await db.scalar(
            select(func.count()).select_from(QueryRun).where(and_(*where), QueryRun.status == "completed")
        )
        avg_duration = await db.scalar(select(func.avg(QueryRun.durationMs)).where(and_(*where)))
        total_prompt = await db.scalar(select(func.coalesce(func.sum(QueryRun.promptTokens), 0)).where(and_(*where)))
        total_completion = await db.scalar(
            select(func.coalesce(func.sum(QueryRun.completionTokens), 0)).where(and_(*where))
        )
        total_cost = await db.scalar(select(func.coalesce(func.sum(QueryRun.estimatedCost), 0.0)).where(and_(*where)))
        success_rate = float(completed_runs or 0) / float(total_runs or 1) if total_runs else 0.0
        return {
            "items": items,
            "nextCursor": next_cursor,
            "stats": {
                "totalRuns": int(total_runs or 0),
                "completedRuns": int(completed_runs or 0),
                "successRate": success_rate,
                "avgDurationMs": int(round(float(avg_duration or 0))),
                "totalTokens": int(total_prompt or 0) + int(total_completion or 0),
                "totalCost": float(total_cost or 0.0),
            },
        }

    return {"items": items, "nextCursor": next_cursor}


@router.get("/history/{run_id}")
async def history_get(
    run_id: str,
    session: AppSession = Depends(require_session),
    db: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    run = await db.get(QueryRun, run_id)
    if not run or run.userId != session.userId:
        raise HTTPException(status_code=404, detail="Run not found")

    steps_stmt = (
        select(QueryStep)
        .where(QueryStep.runId == run.id)
        .order_by(QueryStep.index.asc())
    )
    steps = [row[0] for row in (await db.execute(steps_stmt)).all()]
    return {
        "id": run.id,
        "task": run.task,
        "answer": run.answer,
        "status": run.status,
        "totalSteps": run.totalSteps,
        "durationMs": run.durationMs,
        "promptTokens": run.promptTokens,
        "completionTokens": run.completionTokens,
        "estimatedCost": run.estimatedCost,
        "conversationId": run.conversationId,
        "createdAt": run.createdAt,
        "updatedAt": run.updatedAt,
        "steps": [
            {
                "id": s.id,
                "runId": s.runId,
                "index": s.index,
                "reasoning": s.reasoning,
                "tool": s.tool,
                "args": s.args,
                "success": s.success,
                "result": s.result,
                "durationMs": s.durationMs,
                "timestamp": s.timestamp,
            }
            for s in steps
        ],
    }


@router.delete("/history/{run_id}", status_code=204)
async def history_delete(
    run_id: str,
    session: AppSession = Depends(require_session),
    db: AsyncSession = Depends(get_db),
) -> None:
    run = await db.get(QueryRun, run_id)
    if not run or run.userId != session.userId:
        raise HTTPException(status_code=404, detail="Run not found")
    await db.execute(delete(QueryRun).where(QueryRun.id == run_id))
    await db.commit()

