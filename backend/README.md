# Archon Python Backend

FastAPI + LangGraph backend that mirrors the original Next.js API contract.

## Run Locally

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -e .
copy .env.example .env
uvicorn app.main:app --reload --port 8081
```

## Key Endpoints

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
