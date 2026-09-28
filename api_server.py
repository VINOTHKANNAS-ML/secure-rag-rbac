"""
HTTP API exposing the RBAC RAG pipeline, plus admin endpoints for user
management and login auditing, so the Node.js frontend can offer an admin
panel.

Run:
    uvicorn api_server:app --reload --port 8000

Endpoints:
    POST   /api/login                    {username, password} -> {token, ...}
    POST   /api/ask                      {question}  (Bearer token) -> answer
    POST   /api/logout                   (Bearer token)
    GET    /api/health

    Admin-only (requires an admin-role token):
    GET    /api/admin/users               -> list of users (no password data)
    POST   /api/admin/users               {username, full_name, department,
                                            role, password} -> create a user
    DELETE /api/admin/users/{username}    -> remove a user
    GET    /api/admin/roles               -> valid role names + departments
    GET    /api/admin/login-log           -> recent login attempts (JSON)
    GET    /api/admin/login-log/csv       -> same, as a downloadable CSV
"""

import csv
import io
import json
import os
import secrets
import time
from datetime import datetime, timezone
from typing import Dict, Optional

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from src import documents
from src.auth import AuthenticatedUser, UserDirectory
from src.config import BASE_DIR
from src.rag_pipeline import SecureRAGPipeline
from src.rbac import DEPARTMENTS, ROLES

app = FastAPI(title="Secure Enterprise RAG API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

directory = UserDirectory()
pipeline = SecureRAGPipeline()

# In-memory session store: token -> (user, created_at).
# Fine for a demo/single-process deployment; swap for Redis or a signed
# JWT if you need multi-process or persistence across restarts.
SESSIONS: Dict[str, tuple] = {}
SESSION_TTL_SECONDS = 8 * 60 * 60  # 8 hours

LOGIN_LOG_PATH = os.path.join(BASE_DIR, "login_log.jsonl")
LOGIN_LOG_MAX_RETURNED = 500  # cap how many rows the API returns at once


class LoginRequest(BaseModel):
    username: str
    password: str


class AskRequest(BaseModel):
    question: str


class UploadRequest(BaseModel):
    filename: str
    content_base64: str
    title: str = ""
    department: str
    confidentiality_level: int


class CreateUserRequest(BaseModel):
    username: str
    full_name: str
    department: str
    role: str
    password: str


# ---------------------------------------------------------------------
# Session helpers
# ---------------------------------------------------------------------
def _get_current_user(authorization: Optional[str]) -> AuthenticatedUser:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or malformed Authorization header.")

    token = authorization.removeprefix("Bearer ").strip()
    entry = SESSIONS.get(token)
    if entry is None:
        raise HTTPException(status_code=401, detail="Invalid or expired session.")

    user, created_at = entry
    if time.time() - created_at > SESSION_TTL_SECONDS:
        del SESSIONS[token]
        raise HTTPException(status_code=401, detail="Session expired. Please log in again.")

    return user


def _require_admin(authorization: Optional[str]) -> AuthenticatedUser:
    user = _get_current_user(authorization)
    if user.role.name != "admin":
        raise HTTPException(status_code=403, detail="Admin access required.")
    return user


# ---------------------------------------------------------------------
# Login audit log (separate from the RAG query audit log in
# src/retriever.py, which tracks what documents were retrieved).
# ---------------------------------------------------------------------
def _log_login_attempt(username: str, success: bool, ip: Optional[str]):
    event = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "username": username,
        "success": success,
        "ip": ip,
    }
    with open(LOGIN_LOG_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(event) + "\n")


def _read_login_log(limit: int = LOGIN_LOG_MAX_RETURNED):
    if not os.path.exists(LOGIN_LOG_PATH):
        return []

    with open(LOGIN_LOG_PATH, "r", encoding="utf-8") as f:
        lines = f.readlines()

    events = []
    for line in lines[-limit:]:
        line = line.strip()
        if not line:
            continue
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            continue

    events.reverse()  # most recent first
    return events


# ---------------------------------------------------------------------
# Core endpoints
# ---------------------------------------------------------------------
@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.post("/api/login")
def login(payload: LoginRequest, request: Request):
    client_ip = request.client.host if request.client else None

    try:
        user = directory.login(payload.username, payload.password)
    except PermissionError as e:
        _log_login_attempt(payload.username, success=False, ip=client_ip)
        raise HTTPException(status_code=401, detail=str(e))

    _log_login_attempt(payload.username, success=True, ip=client_ip)

    token = secrets.token_urlsafe(32)
    SESSIONS[token] = (user, time.time())

    return {
        "token": token,
        "username": user.username,
        "full_name": user.full_name,
        "department": user.department,
        "role": user.role.name,
        "allowed_departments": sorted(user.role.allowed_departments),
        "max_confidentiality": user.role.max_confidentiality,
    }


@app.post("/api/logout")
def logout(authorization: Optional[str] = Header(None)):
    if authorization and authorization.startswith("Bearer "):
        token = authorization.removeprefix("Bearer ").strip()
        SESSIONS.pop(token, None)
    return {"status": "logged out"}


@app.post("/api/ask")
def ask(payload: AskRequest, authorization: Optional[str] = Header(None)):
    user = _get_current_user(authorization)

    result = pipeline.ask(payload.question, user)

    return {
        "answer": result.answer,
        "used_llm": result.used_llm,
        "denied_count": result.denied_count,
        "sources": [
            {
                "title": s.title,
                "department": s.department,
                "confidentiality_level": s.confidentiality_level,
                "text": s.text,
            }
            for s in result.sources
        ],
    }


# ---------------------------------------------------------------------
# Document upload / management (any logged-in user; RBAC enforced in
# src/documents.py - users can only upload within their own access)
# ---------------------------------------------------------------------
@app.get("/api/documents/options")
def document_upload_options(authorization: Optional[str] = Header(None)):
    user = _get_current_user(authorization)
    return documents.upload_options(user.role)


@app.get("/api/documents")
def list_documents(authorization: Optional[str] = Header(None)):
    user = _get_current_user(authorization)
    return {"documents": documents.list_documents(user.role, user.username)}


@app.post("/api/documents")
def upload_document(payload: UploadRequest, authorization: Optional[str] = Header(None)):
    user = _get_current_user(authorization)
    try:
        result = documents.add_document(
            collection=pipeline.retriever.collection,
            role=user.role,
            username=user.username,
            filename=payload.filename,
            content_base64=payload.content_base64,
            title=payload.title,
            department=payload.department,
            confidentiality_level=payload.confidentiality_level,
        )
    except documents.UploadError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"status": "uploaded", **result}


@app.delete("/api/documents/{doc_id}")
def delete_document(doc_id: str, authorization: Optional[str] = Header(None)):
    user = _get_current_user(authorization)
    try:
        documents.delete_document(pipeline.retriever.collection, user.role, user.username, doc_id)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e.args[0]))
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    return {"status": "deleted", "doc_id": doc_id}


# ---------------------------------------------------------------------
# Admin endpoints
# ---------------------------------------------------------------------
@app.get("/api/admin/roles")
def list_roles(authorization: Optional[str] = Header(None)):
    _require_admin(authorization)
    return {"roles": list(ROLES.keys()), "departments": DEPARTMENTS}


@app.get("/api/admin/users")
def list_users(authorization: Optional[str] = Header(None)):
    _require_admin(authorization)
    return {"users": directory.list_users()}


@app.post("/api/admin/users")
def create_user(payload: CreateUserRequest, authorization: Optional[str] = Header(None)):
    _require_admin(authorization)
    try:
        directory.add_user(
            username=payload.username,
            full_name=payload.full_name,
            department=payload.department,
            role=payload.role,
            password=payload.password,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"status": "created", "username": payload.username}


@app.delete("/api/admin/users/{username}")
def delete_user(username: str, authorization: Optional[str] = Header(None)):
    admin_user = _require_admin(authorization)

    if username == admin_user.username:
        raise HTTPException(status_code=400, detail="You cannot remove your own account.")

    remaining_admins = [
        u for u in directory.list_users()
        if u["role"] == "admin" and u["username"] != username
    ]
    target = next((u for u in directory.list_users() if u["username"] == username), None)
    if target and target["role"] == "admin" and not remaining_admins:
        raise HTTPException(status_code=400, detail="Cannot remove the last remaining admin account.")

    try:
        directory.remove_user(username)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return {"status": "removed", "username": username}


@app.get("/api/admin/login-log")
def get_login_log(authorization: Optional[str] = Header(None)):
    _require_admin(authorization)
    return {"events": _read_login_log()}


@app.get("/api/admin/login-log/csv")
def get_login_log_csv(authorization: Optional[str] = Header(None)):
    _require_admin(authorization)
    events = _read_login_log(limit=100_000)  # full history for the CSV export

    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=["timestamp", "username", "success", "ip"])
    writer.writeheader()
    for event in events:
        writer.writerow(event)
    buffer.seek(0)

    filename = f"login_log_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.csv"
    return StreamingResponse(
        iter([buffer.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
