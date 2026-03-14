# Tools - find.ai

Tools are registered in the backend and invoked by the agent when needed.

**Registry**
- `backend/app/tools/registry.py` holds tool registration and descriptions.

**Core Tools**
- Web search
- Web scrape
- Vector search
- Google Drive search/ingest

**Execution Path**
1. The planner selects a tool.
2. The executor calls the tool via registry.
3. Results are stored and streamed back to the client.

**Where to Add New Tools**
- Implement in `backend/app/tools/`.
- Register in the tool registry.
- Provide a short description for the planner.
