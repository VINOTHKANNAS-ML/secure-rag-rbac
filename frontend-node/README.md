# Node.js Frontend

A separate Express-based frontend for the Secure Enterprise RAG project.
It does not talk to ChromaDB, the embedding model, or the LLM directly —
it proxies to the Python FastAPI backend (`api_server.py` in the project
root), keeping the session token server-side.

```
Browser  <-->  Node/Express (this folder, port 3000)  <-->  FastAPI (port 8000)  <-->  src/ (RBAC + retrieval + LLM)
```

## Setup

1. Make sure the Python backend is ready (from the project root):
   ```bash
   pip install -r requirements.txt
   python generate_dataset.py
   python -m src.ingest
   uvicorn api_server:app --reload --port 8000
   ```
   Leave that running in one terminal.

2. In a second terminal, set up this frontend:
   ```bash
   cd frontend-node
   npm install
   cp .env.example .env
   npm start
   ```

3. Open **http://localhost:3000** in your browser. Log in with any
   account from `../DEMO_CREDENTIALS.md` (e.g. `aisha.hr` / `HrMgr@123`).

## Admin panel

Log in with an admin account (e.g. `admin.root` / `Admin@123`) to see an
"🛠 Admin Panel" link in the sidebar, or go directly to
**http://localhost:3000/admin**. Non-admin users are redirected away from
this page both client-side and (more importantly) server-side — the
Python API re-checks the role on every admin request regardless of what
the frontend shows.

From the admin panel you can:
- **View all users** (username, full name, department, role).
- **Add a user** — pick a role/department from dropdowns, set a password
  (stored as a salted PBKDF2 hash, never plaintext).
- **Remove a user** — blocked for your own account and for the last
  remaining admin, to prevent locking everyone out.
- **View login activity** — every login attempt (success or failure),
  with timestamp, username, and source IP, newest first.
- **Download login activity as CSV** — via the "⬇ Download CSV" button,
  which streams the full history from the Python backend.

## How it works

- `server.js` — Express app. Serves `public/login.html` and
  `public/chat.html`, and exposes `/api/login`, `/api/ask`, `/api/me`,
  `/api/logout`, which proxy to the Python API and store the session
  token in an HTTP-only cookie (via `express-session`) so it's never
  exposed to client-side JavaScript.
- `public/login.html` — username/password form, posts to `/api/login`.
- `public/chat.html` — question box + answer/sources display, posts to
  `/api/ask`, reads session info from `/api/me`.
- `public/style.css` — shared styling for both pages.

## Configuration

Set in `.env` (copy from `.env.example`):

| Variable          | Default                 | Purpose                                   |
|-------------------|--------------------------|--------------------------------------------|
| `PYTHON_API_URL`  | `http://localhost:8000` | Where the FastAPI backend is running       |
| `SESSION_SECRET`  | (change this)            | Signs the session cookie — use a long random string |
| `PORT`            | `3000`                   | Port this Node server listens on           |

## Notes

- This frontend is stateless regarding RAG logic — all retrieval, RBAC
  enforcement, and LLM calls happen in the Python backend. This server
  only manages the browser session and forwards requests.
- Sessions are stored in-memory in both the Node server (`express-session`
  default `MemoryStore`) and the Python API (`SESSIONS` dict in
  `api_server.py`). Restarting either process logs everyone out — fine
  for a demo/single-instance deployment; swap in Redis-backed sessions
  and a JWT or database-backed session store for production.
