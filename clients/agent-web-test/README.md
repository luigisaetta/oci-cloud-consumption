# Agent Web Test Client (Next.js)

This is a simple Next.js web client used to test the HTTP Agent API endpoint:
- `POST /agent/invoke`

## Prerequisites
- Node.js 18+
- npm 9+

## Setup
From the project root:

```bash
cd clients/agent-web-test
npm install
cp .env.local.example .env.local
```

Edit `.env.local` if needed:

```env
NEXT_PUBLIC_AGENT_API_URL=http://127.0.0.1:8100
DEV_BASIC_AUTH_USER=dev_user
DEV_BASIC_AUTH_PASS=dev_password_123
```

When `DEV_BASIC_AUTH_USER` and `DEV_BASIC_AUTH_PASS` are set, the app is protected with HTTP Basic Auth via Next.js middleware.

## Run the Client

```bash
npm run dev
```

Open:
- `http://localhost:3000`

## End-to-End Local Test
1. Start MCP server:
```bash
uvicorn mcp_consumption:app --app-dir ../../mcp --host 127.0.0.1 --port 8000
```

2. Start Agent API (from repo root):
```bash
uvicorn api.agent_api:app --host 127.0.0.1 --port 8100 --reload
```

3. Run this Next.js client and invoke the agent from the UI.
