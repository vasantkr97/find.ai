# Deployment Guide

## Prerequisites

- Node.js 22+
- Python 3.11+
- Postgres 16 (or Docker)
- LLM provider credentials (OpenAI or Gemini) or local Ollama
- Serper API key (for web search)
- Google Cloud Console project (for Drive integration, optional)

## Environment Setup

Backend config is in `backend/.env`. Frontend config is in `frontend/.env.local`.

### Backend Required Variables
- `DATABASE_URL` - Postgres connection string
- `SERPER_API_KEY` - Serper.dev API key for web search
- `OPENAI_API_KEY` or `GEMINI_API_KEY` (unless using Ollama)

### Optional: Google Drive
- `GOOGLE_CLIENT_ID`
- `GOOGLE_CLIENT_SECRET`
- `GOOGLE_REDIRECT_URI`
- `NEXT_PUBLIC_APP_URL`

### LLM Provider Selection

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

## Local Development

```bash
# Backend
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -e ".[dev]"
copy .env.example .env
uvicorn app.main:app --reload --port 8081
```

```bash
# Frontend
cd frontend
npm install
cp .env.example .env.local
npm run dev
```

## Docker

```bash
# Build and run
docker compose up -d

# View logs
docker compose logs -f

# Stop
docker compose down
```

## Production Build

Frontend:
```bash
npm run build
npm run start
```

Backend:
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8081
```

## Deployment Platforms

### Vercel (Frontend)
Deploy the Next.js frontend on Vercel and point `NEXT_PUBLIC_BACKEND_URL` to your backend.

### Docker / VPS
Use the provided `Dockerfile` and `docker-compose.yml` for container deployments. The backend writes vector data to `.data/vectors/{userId}.json`.

## Health Check

The `/api/health` endpoint returns:

```json
{ "status": "ok", "timestamp": "...", "uptime": 123.456 }
```

## Production Recommendations

1. **Vector database (optional at scale)** - Replace file-based vector store with a shared vector DB keyed by `userId`.
2. **Redis** - Use Redis for rate limiting and caching in multi-instance deployments.
3. **Secrets Management** - Use platform-native secrets instead of `.env` files.
4. **Monitoring** - Connect structured logs to a log aggregator.
5. **CDN** - Place the frontend behind a CDN for static asset caching.
