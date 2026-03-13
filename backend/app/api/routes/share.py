from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import QueryRun, QueryStep
from app.db.session import get_db

router = APIRouter()


@router.get("/share/{run_id}")
async def share_get(run_id: str, db: AsyncSession = Depends(get_db)) -> dict[str, object]:
    run = await db.get(QueryRun, run_id)
    if not run or not run.answer:
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
        "createdAt": run.createdAt,
        "steps": [
            {
                "id": step.id,
                "index": step.index,
                "reasoning": step.reasoning,
                "tool": step.tool,
            }
            for step in steps
        ],
    }

