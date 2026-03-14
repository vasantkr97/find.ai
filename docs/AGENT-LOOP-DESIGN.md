# Agent Loop Design

## State Machine

The agent operates as an explicit finite state machine:

```
+----------+    +----------+    +----------+    +-----------+    +--------------+    +-----------+
| planning | -> | deciding | -> | executing| -> | deciding  | -> | synthesizing | -> | completed |
+----------+    +----------+    +----------+    +-----------+    +--------------+    +-----------+
        |                        ^                    |
        |                        |                    |
        +--------> complete -----+                    +----> error
        
Any state -> aborted (via signal)
```

### States

| State | Description |
|-------|-------------|
| `planning` | LLM creates a multi-step research plan |
| `deciding` | LLM decides the next action based on context |
| `executing` | A tool is being executed |
| `synthesizing` | LLM synthesizes final answer from all step results |
| `completed` | Execution finished successfully |
| `error` | An unrecoverable error occurred |
| `aborted` | Execution was cancelled via signal |

## Execution Flow

1. **Planning Phase** - The LLM receives the task and available tools, producing a structured plan.
2. **Execution Loop** - For each step up to `maxSteps`:
   - The LLM receives the task, plan, and all previous step results
   - It decides either `tool_call` (execute a tool) or `complete` (enough info)
   - If `tool_call`: the tool is executed with timeout protection, result is recorded
   - If `complete`: early exit from the loop
3. **Synthesis Phase** - The LLM receives all step results and produces a final answer with citations.

## Safety Mechanisms

### Step Limit
Configurable via `AGENT_MAX_STEPS` (default 10). Prevents infinite loops.

### Tool Timeout
Each tool execution is wrapped in `asyncio.wait_for` with a configurable timeout (`AGENT_STEP_TIMEOUT_MS`).

### Tool Validation
Before execution, tool names are validated against the registry. Unknown tools are converted to a completion step.

### Abort Support
A signal can be passed to cancel execution. Checked before every phase transition.

### LLM Retries
All LLM calls use exponential backoff (up to `AGENT_LLM_RETRY_ATTEMPTS`). Rate limit errors trigger longer delays.

### Circuit Breaker
After repeated LLM failures within a window, the circuit breaker opens and rejects calls until reset.

### Schema Validation
LLM JSON outputs are validated via Pydantic models. Invalid outputs raise `LLMParseError` with raw output for debugging.

## Event Stream

The agent emits events via SSE for real-time UI updates:

| Event | Payload | When |
|-------|---------|------|
| `conversation_id` | `{ conversationId }` | At start |
| `state_change` | `{ state }` | Every state transition |
| `thinking` | `{ content }` | Agent is processing |
| `plan` | `{ plan }` | Plan created |
| `step_start` | `{ step }` | Tool execution begins |
| `step_complete` | `{ step }` | Tool execution completes |
| `answer_chunk` | `{ content }` | Streaming final answer |
| `complete` | `{ result, usage }` | Final result ready |
| `error` | `{ error }` | Error occurred |
