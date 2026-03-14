# Agent Loop - find.ai

This document details the end-to-end agent loop, the decision model, and streaming behavior.

**Loop Stages**
1. Plan: Generate a concise plan from the user task.
2. Decide: Choose the next tool or complete.
3. Execute: Run the tool and capture results.
4. Synthesize: Stream final answer + citations.

**State Flow**

```text
planning -> deciding -> executing -> deciding -> ... -> synthesizing -> END
```

**Decision Rules**
- If a tool is required, emit a `tool_call` decision.
- If enough information is available, emit `complete`.
- If the tool is unknown or invalid, the agent completes with available info.

**Streaming Events (SSE)**
During `/api/agent` the backend emits:
- `conversation_id`
- `state_change` (planning, deciding, executing, synthesizing, completed)
- `thinking`
- `plan`
- `step_start`
- `step_complete`
- `answer_chunk`
- `complete`
- `error`

**Relevant Code**
- `backend/app/agent/graph.py` (graph orchestration)
- `backend/app/agent/planner.py` (plan + decision prompts)
- `backend/app/api/routes/agent.py` (SSE endpoint)
