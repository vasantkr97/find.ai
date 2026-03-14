# find.ai Backend

FastAPI backend that powers the find.ai research agent. It exposes a streaming `/api/agent` endpoint, manages tool execution, and persists runs to Postgres.

**Architecture**
- Clean Architecture layers and the agent loop design are documented in `../docs/architecture.md`.

**Getting Started**

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -e ".[dev]"
copy .env.example .env
uvicorn app.main:app --reload --port 8081
```

**Environment Configuration**
Core settings live in `app/core/config.py` and load from `backend/.env`.

OpenAI:
```env
LLM_PROVIDER=openai
OPENAI_API_KEY=...
LLM_MODEL=gpt-4o-mini
```

Gemini:
```env
LLM_PROVIDER=gemini
GEMINI_API_KEY=...
GEMINI_MODEL=gemini-2.0-flash
```

Ollama (local):
```env
LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://127.0.0.1:11434
OLLAMA_MODEL=qwen2.5:7b
OLLAMA_EMBEDDING_MODEL=nomic-embed-text
```

**Key Endpoints**
- `POST /api/agent` (SSE)
- `GET /api/health`
- `GET /api/drive/auth`
- `GET /api/drive/callback`
- `GET /api/drive/status`
- `GET /api/drive/files`
- `POST /api/drive/ingest` (SSE)
- `GET /api/history`
- `GET /api/history/{id}`
- `DELETE /api/history/{id}`
- `GET /api/auth/status`
- `POST /api/auth/logout`
- `GET /api/users`
- `POST /api/users`
- `GET /api/users/{id}`
- `PATCH /api/users/{id}`
- `DELETE /api/users/{id}`

**Troubleshooting**
- CORS errors: set `CORS_ALLOWED_ORIGINS` to your frontend origin.
- Ollama timeouts: switch to a smaller model (`qwen2.5:3b`) or lower `LLM_MAX_TOKENS`.
- Red squiggles in VS Code: ensure interpreter points to `backend/.venv`.
