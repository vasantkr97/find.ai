# Deployment Guide

## Prerequisites

- Node.js 22+ (frontend)
- Python 3.11+ (backend)
- OpenAI API key
- Serper API key (for web search)
- Google Cloud Console project (for Drive integration, optional)

## Environment Setup

Copy `frontend/.env.example` to `frontend/.env.local` (frontend env) and `backend/.env.example` to `backend/.env` (backend env):

```bash
cp frontend/.env.example frontend/.env.local
cp backend/.env.example backend/.env
```

### Required Variables
- `OPENAI_API_KEY` — OpenAI API key for LLM and embeddings
- `SERPER_API_KEY` — Serper.dev API key for Google search

### Optional: Google Drive
- `GOOGLE_CLIENT_ID` — OAuth 2.0 client ID
- `GOOGLE_CLIENT_SECRET` — OAuth 2.0 client secret
- `GOOGLE_REDIRECT_URI` — OAuth callback URL
- `NEXT_PUBLIC_APP_URL` — Application base URL

#### Allowing more users to sign in with Google
If only one Google account can sign in and others see "Google does not allow it", your OAuth consent screen is in **Testing** mode. Fix it in [Google Cloud Console](https://console.cloud.google.com/):

1. Open **APIs & Services** → **OAuth consent screen**.
2. Choose one of:
   - **Quick fix (small team):** Under **Test users**, click **+ ADD USERS** and add each Google email that should be able to sign in. They will get the normal sign-in flow.
   - **Allow any Google account:** Click **PUBLISH APP** to move the app to **Production**. See below for the "unverified app" warning.

#### "Google hasn't verified this app" warning
After you publish, users may see: *"The app is requesting access to sensitive info... Until the developer verifies this app with Google, you shouldn't use it."* That happens because your app uses **sensitive scopes** (e.g. Google Drive). You have two paths:

- **Recommended for personal / small team:** Switch back to **Testing** and add only the people who need access as **Test users**. Test users can still sign in: on the warning screen they click **Advanced** then **Go to [your app name] (unsafe)** to continue. No verification needed.
- **Public app / many users:** Submit your app for [Google OAuth verification](https://support.google.com/cloud/answer/9110914). You'll need a privacy policy, app homepage, and possibly a security assessment. Use this only if you need anyone on the internet to sign in without the warning.

## Local Development

Start backend:

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -e .
uvicorn app.main:app --reload --port 8081
```

Then start frontend:

```bash
cd frontend
npm install
npm run dev
```

## Docker

```bash
# Build and run
docker compose up -d

# View logs
docker compose logs -f frontend

# Stop
docker compose down
```

## Production Build

```bash
cd frontend
npm run build
npm start
```

## Deployment Platforms

### Vercel
The app is configured for Vercel with `serverExternalPackages: ["googleapis"]` in `frontend/next.config.ts`. Environment variables should be set in the Vercel dashboard.

Note: The app uses **per-user** file-based vector stores (`.data/vectors/{userId}.json`). On serverless (e.g. Vercel), these files do not persist across invocations. For production at scale, use a shared vector DB (Pinecone, Qdrant, pgvector) with a `userId` (or tenant) dimension and keep the same `getVectorStore(userId)`-style API.

### Docker / VPS
Use `frontend/Dockerfile` for frontend container deployments. The image uses a multi-stage build for minimal size and runs as a non-root user.

```bash
docker build -t query-agent-frontend ./frontend
docker run -p 3001:3001 --env-file ./frontend/.env.local query-agent-frontend
```

### Health Check
The `/api/health` endpoint returns:
```json
{ "status": "ok", "timestamp": "...", "uptime": 123.456 }
```

## Production Recommendations

1. **Vector database (optional at scale)** — The app ships with per-user file stores (`.data/vectors/{userId}.json`), which is correct for multi-tenant isolation. For hundreds of users or serverless, replace with a vector DB (Pinecone, Qdrant, pgvector) keyed by `userId`.
2. **Redis** — Use Redis for rate limiting and query caching in multi-instance deployments.
3. **Secrets Management** — Use platform-native secrets (AWS Secrets Manager, Vercel Environment Variables) instead of `.env` files.
4. **Monitoring** — Connect structured logs to a log aggregator (Datadog, Grafana Loki).
5. **CDN** — Place the app behind a CDN for static asset caching.
6. **Auth** — Session-based auth is built in; all data (runs, history, Drive, vector store) is scoped per user.
