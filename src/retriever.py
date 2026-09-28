"""
RBAC-aware retrieval.

Security model (defense in depth):
  1. PRE-FILTER: the vector search itself is constrained with a Chroma
     `where` clause so the database never even returns chunks outside the
     user's allowed departments / confidentiality ceiling.
  2. POST-FILTER: results are re-checked in application code against the
     same RBAC rules before being handed to the LLM or the user. This
     protects against a misconfigured filter, a metadata bug, or a future
     change to the retrieval query that forgets step 1.
  3. AUDIT LOG: every query is logged with the user, role, and which
     chunks were returned vs. would-have-matched-but-were-denied, so
     access can be reviewed later.
"""

import datetime
import json
import os
from dataclasses import dataclass, field
from typing import List

from src.config import CHROMA_PERSIST_DIR
from src.ingest import get_chroma_client, get_embedding_function
from src.rbac import Role, allowed_departments_for

AUDIT_LOG_PATH = os.path.join(os.path.dirname(CHROMA_PERSIST_DIR), "audit_log.jsonl")


@dataclass
class RetrievedChunk:
    doc_id: str
    title: str
    department: str
    confidentiality_level: int
    text: str
    distance: float


@dataclass
class RetrievalResult:
    allowed: List[RetrievedChunk] = field(default_factory=list)
    denied_count: int = 0  # matched semantically but blocked by RBAC


class RBACRetriever:
    def __init__(self):
        client = get_chroma_client()
        embed_fn = get_embedding_function()
        self.collection = client.get_or_create_collection(
            name="enterprise_docs", embedding_function=embed_fn
        )

    def query(self, query_text: str, role: Role, username: str, top_k: int = 4,
               fetch_multiplier: int = 3) -> RetrievalResult:
        allowed_depts = allowed_departments_for(role)

        # --- Step 1: pre-filter at the database level ---
        where_clause = {
            "$and": [
                {"department": {"$in": allowed_depts}},
                {"confidentiality_level": {"$lte": role.max_confidentiality}},
            ]
        }

        # Over-fetch a bit before re-ranking/truncating to top_k.
        raw = self.collection.query(
            query_texts=[query_text],
            n_results=top_k * fetch_multiplier,
            where=where_clause,
        )

        result = RetrievalResult()
        docs = raw.get("documents", [[]])[0]
        metas = raw.get("metadatas", [[]])[0]
        dists = raw.get("distances", [[]])[0]

        for text, meta, dist in zip(docs, metas, dists):
            # --- Step 2: post-filter re-check (defense in depth) ---
            if role.can_access(meta["department"], meta["confidentiality_level"]):
                result.allowed.append(
                    RetrievedChunk(
                        doc_id=meta["doc_id"],
                        title=meta["title"],
                        department=meta["department"],
                        confidentiality_level=meta["confidentiality_level"],
                        text=text,
                        distance=dist,
                    )
                )
            else:
                result.denied_count += 1
            if len(result.allowed) >= top_k:
                break

        # --- Step 3: for audit purposes, also measure how many chunks
        # *would* have matched with no RBAC filter at all ---
        unfiltered = self.collection.query(query_texts=[query_text], n_results=top_k)
        unfiltered_ids = set(unfiltered.get("ids", [[]])[0])
        allowed_ids = {c.doc_id for c in result.allowed}
        blocked_by_rbac = len(unfiltered_ids) - len(
            unfiltered_ids & {f"{d}" for d in allowed_ids}
        )

        self._log_audit_event(
            username=username,
            role=role.name,
            query=query_text,
            allowed_doc_ids=[c.doc_id for c in result.allowed],
            denied_count=result.denied_count,
            unfiltered_top_match_blocked_estimate=max(blocked_by_rbac, 0),
        )

        return result

    def _log_audit_event(self, **event):
        event["timestamp"] = datetime.datetime.utcnow().isoformat() + "Z"
        os.makedirs(os.path.dirname(AUDIT_LOG_PATH), exist_ok=True)
        with open(AUDIT_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(event) + "\n")
