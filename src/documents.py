"""
Document management for uploads made through the UI.

An uploaded document goes through the same path as the built-in dataset:
text is extracted, saved under data/documents/, recorded in
data/metadata.json, chunked, embedded, and added to the Chroma collection
with department + confidentiality_level metadata - so the RBAC filter in
src/retriever.py applies to it automatically, and it is searchable
immediately (no re-ingest needed).

Upload rules (enforced here, not just in the UI):
  - A user may only upload into a department and confidentiality level
    that their own role can access (nobody can upload above their own
    clearance, or into a department they can't see).
  - Interns cannot upload.
  - Only the uploader or an admin can delete an uploaded document.
    Built-in dataset documents can only be deleted by an admin.

Supported file types: .txt, .md, .csv, .json, .docx (text extracted with
the standard library), and .pdf (needs the optional `pypdf` package).
"""

import base64
import io
import json
import os
import re
import threading
import zipfile
from datetime import datetime, timezone
from typing import List, Optional

from src.chunking import chunk_text
from src.config import DOCS_DIR, METADATA_PATH
from src.rbac import CONFIDENTIALITY_LEVELS, DEPARTMENTS, LEVEL_NAMES, Role

MAX_FILE_BYTES = 2 * 1024 * 1024  # 2 MB per upload
MAX_TEXT_CHARS = 200_000
UPLOAD_DENIED_ROLES = {"intern"}
ALLOWED_EXTENSIONS = {".txt", ".md", ".csv", ".json", ".docx", ".pdf"}

_lock = threading.Lock()


class UploadError(Exception):
    """Raised for any user-correctable problem with an upload."""


# ---------------------------------------------------------------------
# Text extraction
# ---------------------------------------------------------------------
def _extract_docx(data: bytes) -> str:
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            xml = z.read("word/document.xml").decode("utf-8", errors="ignore")
    except (zipfile.BadZipFile, KeyError):
        raise UploadError("That .docx file could not be read.")
    xml = re.sub(r"</w:p>", "\n", xml)
    xml = re.sub(r"<w:tab/>", "\t", xml)
    text = re.sub(r"<[^>]+>", "", xml)
    return (text.replace("&amp;", "&").replace("&lt;", "<")
                .replace("&gt;", ">").replace("&quot;", '"').replace("&apos;", "'"))


def _extract_pdf(data: bytes) -> str:
    try:
        from pypdf import PdfReader
    except ImportError:
        raise UploadError(
            "PDF support needs the 'pypdf' package. Run: pip install pypdf"
        )
    try:
        reader = PdfReader(io.BytesIO(data))
        return "\n".join((page.extract_text() or "") for page in reader.pages)
    except Exception:
        raise UploadError("That PDF could not be read (it may be encrypted or scanned images).")


def extract_text(filename: str, data: bytes) -> str:
    ext = os.path.splitext(filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise UploadError(
            f"Unsupported file type '{ext or filename}'. "
            f"Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}"
        )
    if ext == ".docx":
        text = _extract_docx(data)
    elif ext == ".pdf":
        text = _extract_pdf(data)
    else:
        text = data.decode("utf-8", errors="ignore")

    text = text.replace("\r\n", "\n").strip()
    if len(text) < 20:
        raise UploadError("No readable text was found in that file.")
    return text[:MAX_TEXT_CHARS]


# ---------------------------------------------------------------------
# Permissions
# ---------------------------------------------------------------------
def can_upload(role: Role) -> bool:
    return role.name not in UPLOAD_DENIED_ROLES


def upload_options(role: Role) -> dict:
    """What this role may upload into - used to populate the UI dropdowns."""
    if not can_upload(role):
        return {"allowed": False, "departments": [], "levels": []}
    departments = [d for d in DEPARTMENTS
                   if any(role.can_access(d, lvl) for lvl in CONFIDENTIALITY_LEVELS.values())]
    levels = [{"value": v, "name": k} for k, v in CONFIDENTIALITY_LEVELS.items()
              if v <= role.max_confidentiality]
    return {"allowed": True, "departments": departments, "levels": levels}


# ---------------------------------------------------------------------
# Metadata store
# ---------------------------------------------------------------------
def _load_metadata() -> dict:
    if not os.path.exists(METADATA_PATH):
        return {}
    with open(METADATA_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_metadata(metadata: dict):
    os.makedirs(os.path.dirname(METADATA_PATH), exist_ok=True)
    with open(METADATA_PATH, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:40] or "document"


# ---------------------------------------------------------------------
# Operations
# ---------------------------------------------------------------------
def add_document(collection, role: Role, username: str, filename: str,
                 content_base64: str, title: str, department: str,
                 confidentiality_level: int) -> dict:
    if not can_upload(role):
        raise UploadError("Your role is not allowed to upload documents.")
    if department not in DEPARTMENTS:
        raise UploadError(f"Unknown department '{department}'.")
    if confidentiality_level not in LEVEL_NAMES:
        raise UploadError("Unknown confidentiality level.")
    if not role.can_access(department, confidentiality_level):
        raise UploadError(
            "You can only upload documents into departments and confidentiality "
            "levels that your own role has access to."
        )

    try:
        data = base64.b64decode(content_base64, validate=True)
    except Exception:
        raise UploadError("The file data was not valid.")
    if len(data) > MAX_FILE_BYTES:
        raise UploadError(f"File is too large (max {MAX_FILE_BYTES // (1024 * 1024)} MB).")

    text = extract_text(filename, data)
    title = (title or os.path.splitext(filename)[0]).strip()[:120] or "Untitled"

    with _lock:
        metadata = _load_metadata()
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
        doc_id = f"upl_{stamp}_{_slug(title)}"
        n = 2
        while doc_id in metadata:
            doc_id = f"upl_{stamp}_{_slug(title)}-{n}"
            n += 1

        os.makedirs(DOCS_DIR, exist_ok=True)
        path = os.path.join(DOCS_DIR, f"{doc_id}.txt")
        with open(path, "w", encoding="utf-8") as f:
            f.write(f"Title: {title}\nDepartment: {department}\n\n{text}\n")

        chunks = chunk_text(f"Title: {title}\nDepartment: {department}\n\n{text}")
        collection.add(
            ids=[f"{doc_id}__chunk{i}" for i in range(len(chunks))],
            documents=chunks,
            metadatas=[{
                "doc_id": doc_id,
                "title": title,
                "department": department,
                "confidentiality_level": int(confidentiality_level),
            }] * len(chunks),
        )

        metadata[doc_id] = {
            "title": title,
            "department": department,
            "confidentiality_level": int(confidentiality_level),
            "path": path.replace("\\", "/"),
            "uploaded_by": username,
            "uploaded_at": datetime.now(timezone.utc).isoformat(),
            "original_filename": filename,
        }
        _save_metadata(metadata)

    return {"doc_id": doc_id, "title": title, "chunks": len(chunks)}


def list_documents(role: Role, username: str) -> List[dict]:
    """Documents this role may see, newest uploads first."""
    metadata = _load_metadata()
    rows = []
    for doc_id, m in metadata.items():
        if not role.can_access(m["department"], m["confidentiality_level"]):
            continue
        uploaded_by = m.get("uploaded_by")
        rows.append({
            "doc_id": doc_id,
            "title": m["title"],
            "department": m["department"],
            "confidentiality_level": m["confidentiality_level"],
            "confidentiality_name": LEVEL_NAMES.get(m["confidentiality_level"], "?"),
            "uploaded_by": uploaded_by,
            "uploaded_at": m.get("uploaded_at"),
            "can_delete": role.name == "admin" or (uploaded_by is not None and uploaded_by == username),
        })
    rows.sort(key=lambda r: (r["uploaded_at"] or ""), reverse=True)
    return rows


def delete_document(collection, role: Role, username: str, doc_id: str):
    with _lock:
        metadata = _load_metadata()
        m = metadata.get(doc_id)
        if m is None:
            raise KeyError("Document not found.")
        if not role.can_access(m["department"], m["confidentiality_level"]):
            # Don't reveal that a document the user can't see exists.
            raise KeyError("Document not found.")
        uploaded_by = m.get("uploaded_by")
        if not (role.name == "admin" or (uploaded_by is not None and uploaded_by == username)):
            raise PermissionError("Only the uploader or an admin can delete this document.")

        collection.delete(where={"doc_id": doc_id})
        try:
            if m.get("path") and os.path.exists(m["path"]):
                os.remove(m["path"])
        except OSError:
            pass
        del metadata[doc_id]
        _save_metadata(metadata)
