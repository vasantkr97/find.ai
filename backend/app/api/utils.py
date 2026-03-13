import asyncio
import json
import time
from collections.abc import AsyncIterator
from typing import Any

from starlette.responses import StreamingResponse


def sse_event(payload: Any) -> str:
    return f"data: {json.dumps(payload, ensure_ascii=True)}\n\n"


def sse_stream_from_queue(queue: "asyncio.Queue[str | None]") -> StreamingResponse:
    async def iterator() -> AsyncIterator[str]:
        while True:
            msg = await queue.get()
            if msg is None:
                break
            yield msg

    return StreamingResponse(
        iterator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


def now_ms() -> int:
    return int(time.time() * 1000)
