# API - find.ai

This document summarizes the backend API surface.

**Base URL**
- Local: `http://localhost:8081`

**Agent**

`POST /api/agent` (SSE)

Request body:
```json
{
  "task": "string",
  "maxSteps": 10,
  "conversationId": "optional"
}
```

Streamed events (examples):
```json
{"type":"state_change","state":"planning"}
{"type":"plan","plan":{...}}
{"type":"step_start","step":{...}}
{"type":"answer_chunk","content":"..."}
{"type":"complete","result":{...},"usage":{...}}
```

**Health**
- `GET /api/health`

**Drive**
- `GET /api/drive/auth`
- `GET /api/drive/callback`
- `GET /api/drive/status`
- `GET /api/drive/files`
- `POST /api/drive/ingest` (SSE)

**History**
- `GET /api/history`
- `GET /api/history/{id}`
- `DELETE /api/history/{id}`

**Users**
- `GET /api/users`
- `POST /api/users`
- `GET /api/users/{id}`
- `PATCH /api/users/{id}`
- `DELETE /api/users/{id}`

**Auth**
- `GET /api/auth/status`
- `POST /api/auth/logout`
