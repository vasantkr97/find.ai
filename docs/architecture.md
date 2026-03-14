# Architecture

## Directory Structure

```
frontend/
  src/                 # Next.js App Router (pages + UI)
  public/
backend/
  app/
    api/               # API routes (SSE, Drive, history, users)
    agent/             # LangGraph agent loop
    tools/             # Tool registry + implementations
    services/          # LLMs, Drive, vector store
    schemas/           # Pydantic schemas
    core/              # Config, logging, errors, rate limit
    db/                # SQLAlchemy models, session, init
```

## Design Principles

### Separation of Concerns

- **agent/** - Pure agent logic (plan, decide, execute, synthesize)
- **tools/** - Each tool is isolated with validated inputs
- **services/** - External integrations isolated behind clear APIs
- **core/** - Cross-cutting infrastructure (logging, config, errors)
- **schemas/** - Single source of truth for shared types

### Dependency Flow

```
API Routes -> agent/ -> tools/registry -> tools/*
                 -> planner (services/llm)
                 -> executor -> tools/*
                                |
                                v
                           services/drive, services/vector
                                |
                                v
                           services/llm (embeddings)
```

No circular dependencies. Dependencies flow downward only.

### Error Hierarchy

```
AppError (base)
- LLMError
  - LLMRateLimitError
  - LLMParseError
- ToolError
  - ToolNotFoundError
  - ToolTimeoutError
  - ToolValidationError
- DriveError
  - DriveAuthError
- VectorStoreError
- AgentAbortedError
```

### Observability

Every major operation includes:
- Structured log entries (JSON)
- Request IDs propagated through API -> agent -> tools
- Agent run IDs for correlating steps in a single execution
- Duration tracking at API, agent, and tool levels

### Security Layers

1. **Input validation** - Pydantic schemas on all API endpoints
2. **SSRF protection** - URL allowlist in web scraper (blocks localhost, internal IPs)
3. **Rate limiting** - In-memory per-IP rate limiter on agent endpoint
4. **OAuth tokens** - Stored per user; Drive client scoped by session
5. **Tool validation** - Hallucinated tool names caught before execution
6. **Session-based auth** - Agent, history, and Drive APIs require a valid session
7. **Per-user vector store** - Stored under `.data/vectors/{userId}.json`
