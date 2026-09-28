# Secure Enterprise Document Intelligence — RAG with RBAC

A Retrieval-Augmented Generation system that enforces **Role-Based Access
Control (RBAC)** at the retrieval layer, so a user's role determines which
document chunks the LLM is even allowed to see — not just what's shown in
the UI afterward. Each user logs in with their own **username and
password**, not just a name picked from a list.

## Why this matters

Most "add RAG to our docs" demos ignore access control entirely: every
chunk in the vector store is fair game for every user. In a real
enterprise, HR, Legal, Finance, and Engineering documents have very
different audiences. This project treats access control — and real
authentication — as first-class parts of the pipeline, not an afterthought.

## Architecture

```
 Username + password --> UserDirectory (PBKDF2 hash check) --> Role (RBAC policy)
                                                                    |
                                                                    v
 Question --> Embed query --> Chroma vector search
                                 WHERE department IN (allowed)
                                   AND confidentiality <= max
                                                                    |
                                                                    v
                              Post-filter re-check (defense in depth)
                                                                    |
                                                                    v
                         Only allowed chunks --> LLM (Groq/Llama) or
                                                  extractive fallback
                                                                    |
                                                                    v
                                    Answer + cited sources
                                                                    |
                                                                    v
                                     Audit log (JSONL)
```

**Authentication:** passwords are never stored in plaintext. Each account
in `data/users.json` stores a random salt and a PBKDF2-HMAC-SHA256 hash
(200,000 iterations). Login re-derives the hash from the supplied password
and compares it in constant time (`hmac.compare_digest`) to avoid timing
attacks. See `DEMO_CREDENTIALS.md` for the pre-built demo accounts.

**Two layers of access enforcement:**
1. The vector DB query itself is constrained with a metadata `where`
   clause (department + confidentiality ceiling) — disallowed chunks are
   never even retrieved.
2. Every result is re-checked in Python against the same policy before
   being handed to the LLM, so a bug in the DB filter can't leak data.

Every query is logged to `audit_log.jsonl` with the user, role, which
documents were returned, and how many matching-but-disallowed chunks were
withheld — useful for security review and for demonstrating the control
actually works.

## Dataset

`generate_dataset.py` builds **80 synthetic documents** across 7
departments (General, HR, Finance, Engineering, Legal, Sales, Executive)
and 4 confidentiality tiers (Public → Internal → Confidential →
Restricted). It mixes hand-written policy/incident documents with
templated recurring reports (quarterly budgets, sales pipeline reviews,
engineering incident postmortems, sprint notes, board updates) so the
vector index has enough density and topical overlap for retrieval quality
to be meaningfully testable — not just a handful of unrelated one-off
documents. Everything is fully synthetic; there's no real company data.

## Project structure

```
secure-rag-rbac/
├── generate_dataset.py     # builds the synthetic document corpus (80 docs)
├── main.py                 # CLI: username/password login, then ask questions
├── streamlit_app.py        # web UI with a real login form (streamlit run streamlit_app.py)
├── requirements.txt
├── .env.example              # copy to .env, add GROQ_API_KEY (optional)
├── .gitignore
├── DEMO_CREDENTIALS.md      # pre-built demo usernames/passwords
├── data/
│   ├── documents/           # generated .txt documents
│   ├── metadata.json        # doc_id -> department/confidentiality
│   └── users.json           # username -> role + hashed password
├── scripts/
│   └── create_user.py        # add/reset a user with a securely hashed password
├── src/
│   ├── rbac.py               # role & confidentiality-level definitions
│   ├── auth.py                # real login: PBKDF2 password verification
│   ├── config.py
│   ├── chunking.py
│   ├── ingest.py              # build the Chroma index
│   ├── retriever.py           # RBAC-filtered vector search + audit log
│   └── rag_pipeline.py        # retrieval + answer generation
└── tests/
    ├── test_rbac.py           # unit tests for the access-control logic
    └── test_auth.py           # unit tests for password hashing/login
```

## Setup (VS Code)

1. Open this folder in VS Code, open a terminal (`` Ctrl+` ``).
2. Create a virtual environment and install dependencies:
   ```bash
   python -m venv venv
   source venv/bin/activate        # Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```
3. (Optional) Copy `.env.example` to `.env` and add your
   `GROQ_API_KEY` for LLM-generated answers. Without it, the pipeline
   still runs end-to-end using an extractive fallback.
4. Generate the dataset:
   ```bash
   python generate_dataset.py
   ```
5. Build the vector index:
   ```bash
   python -m src.ingest
   ```
6. Run the CLI demo:
   ```bash
   python main.py
   ```
   Log in with one of the accounts in `DEMO_CREDENTIALS.md`, e.g.
   `aisha.hr` / `HrMgr@123`.

   Or run the web UI:
   ```bash
   streamlit run streamlit_app.py
   ```

   Or run the Node.js frontend + FastAPI backend:
   ```bash
   uvicorn api_server:app --reload --port 8000
   # in a second terminal:
   cd frontend-node && npm install && cp .env.example .env && npm start
   ```
   Then open http://localhost:3000. See `frontend-node/README.md` for details.

## Managing users

Don't hand-edit `data/users.json` — passwords are hashed. Use:
```bash
python scripts/create_user.py
```
See `DEMO_CREDENTIALS.md` for details and the full list of built-in demo
accounts.

## Try this to see RBAC in action

Log in as different users and ask the same question:

- `"What is the executive compensation for VPs?"`
  - `priya.intern` → no accessible documents
  - `aisha.hr` (max level Confidential) → still denied (that doc is Restricted)
  - `james.ceo` (executive) → full answer with the Restricted doc as a source

- `"What is the remote work policy?"`
  - any employee-level account → answered (Internal-level, general access)

- `"Summarize the Q1 2026 budget"`
  - `carlos.finance` → answered
  - `arjun.dev` (Engineering employee) → denied (Finance not in his allowed departments)

## Uploading documents from the UI

Open **Documents & Upload** in the sidebar (`/documents` on the Node frontend).
Choose a file (`.txt`, `.md`, `.csv`, `.json`, `.docx`, `.pdf`, max 2 MB), a
department and a confidentiality level, and click **Upload & index**. The
document is chunked, embedded and added to the vector index immediately, so
you can ask questions about it right away - no re-ingest needed.

Rules (enforced by the backend, not just the UI):
- You can only upload into departments and levels **your own role can access**
  (an HR manager cannot upload a *Restricted* document or a Finance one).
- Interns cannot upload.
- Only the uploader or an admin can delete an uploaded document; built-in
  dataset documents can only be deleted by an admin.
- Uploaded documents obey the same RBAC filter as everything else at query time.
- PDF support needs `pip install -r requirements.txt` (adds `pypdf`).
- Re-running `generate_dataset.py` keeps uploaded documents.

## Running tests

```bash
python -m unittest discover tests
```

## Deploying

The app is ready for Streamlit Community Cloud:
1. Push to GitHub (`.env` and `chroma_store/` are already git-ignored).
2. `streamlit_app.py` auto-builds the vector index on first launch if it's
   missing (important since cloud filesystems are often ephemeral).
3. In the Streamlit Cloud dashboard, add `GROQ_API_KEY` under
   Settings → Secrets — `rag_pipeline.py` checks `st.secrets` automatically
   if the environment variable isn't set.

## Extending this for a real deployment

- Replace `src/auth.py` with a real IdP integration (Okta/Azure AD/SAML) —
  the `AuthenticatedUser`/`Role` shape stays the same.
- Replace the character-based chunker in `src/chunking.py` with a
  token-aware or semantic chunker for longer/heterogeneous documents.
- Swap Chroma for a managed vector DB (Pinecone, Weaviate, pgvector) — the
  RBAC `where`-clause pattern in `src/retriever.py` carries over directly.
- Add rate limiting / account lockout on top of the login attempt cap
  already in `main.py`'s CLI flow.
- Extend `audit_log.jsonl` into a proper audit datastore for compliance
  reporting.
