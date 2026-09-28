"""
Ties RBAC-aware retrieval to answer generation.

Generation is pluggable:
  - If GROQ_API_KEY is set, uses Groq's free, OpenAI-compatible API to
    synthesize a grounded answer from the allowed chunks only. Groq hosts
    fast inference of open-source models (Llama, GPT-OSS, etc.) on custom
    LPU hardware - it is a different product from xAI's "Grok" despite
    the similar name.
  - Otherwise, falls back to a simple extractive answer (concatenated top
    chunks) so the whole project runs end-to-end with zero API cost.

Either way, the LLM (or fallback) only ever sees chunks that already
passed RBAC filtering - it is architecturally impossible for the model to
leak a chunk the user wasn't allowed to retrieve, because it's never in
its context.
"""

import os
from dataclasses import dataclass
from typing import List

from dotenv import load_dotenv

from src.auth import AuthenticatedUser
from src.retriever import RBACRetriever, RetrievedChunk
from src.config import GROQ_MODEL, TOP_K

load_dotenv()


@dataclass
class RAGAnswer:
    answer: str
    sources: List[RetrievedChunk]
    denied_count: int
    used_llm: bool


def _secrets_file_exists() -> bool:
    """
    Streamlit shows a visible 'no secrets.toml found' banner the moment
    st.secrets is touched at all, even inside try/except - so check for
    the file on disk first and only access st.secrets if it's actually
    there. Mirrors Streamlit's own lookup locations.
    """
    candidates = [
        os.path.join(os.path.expanduser("~"), ".streamlit", "secrets.toml"),
        os.path.join(os.getcwd(), ".streamlit", "secrets.toml"),
    ]
    return any(os.path.exists(p) for p in candidates)


def _resolve_api_key() -> str:
    """
    Checks the environment first (local dev via .env), then falls back to
    Streamlit's secrets store only if a secrets.toml file actually exists
    (e.g. on Streamlit Cloud, where secrets are configured via the app
    dashboard instead of a .env file).
    """
    key = os.getenv("GROQ_API_KEY", "").strip()
    if key:
        return key
    if not _secrets_file_exists():
        return ""
    try:
        import streamlit as st
        return str(st.secrets.get("GROQ_API_KEY", "")).strip()
    except Exception:
        return ""


class SecureRAGPipeline:
    def __init__(self):
        self.retriever = RBACRetriever()
        self._api_key = _resolve_api_key()

    def ask(self, question: str, user: AuthenticatedUser, top_k: int = TOP_K) -> RAGAnswer:
        result = self.retriever.query(
            query_text=question,
            role=user.role,
            username=user.username,
            top_k=top_k,
        )

        if not result.allowed:
            note = ""
            if result.denied_count > 0:
                note = (
                    f" ({result.denied_count} matching document(s) exist but are "
                    f"outside your access level.)"
                )
            return RAGAnswer(
                answer=f"No accessible documents were found for that question.{note}",
                sources=[],
                denied_count=result.denied_count,
                used_llm=False,
            )

        if self._api_key:
            answer_text = self._generate_with_groq(question, result.allowed)
            used_llm = True
        else:
            answer_text = self._generate_extractive(result.allowed)
            used_llm = False

        return RAGAnswer(
            answer=answer_text,
            sources=result.allowed,
            denied_count=result.denied_count,
            used_llm=used_llm,
        )

    def _generate_with_groq(self, question: str, chunks: List[RetrievedChunk]) -> str:
        from openai import OpenAI

        context = "\n\n".join(
            f"[Source: {c.title} | {c.department} | "
            f"confidentiality={c.confidentiality_level}]\n{c.text}"
            for c in chunks
        )
        system_prompt = (
            "You are an enterprise document assistant. Answer the user's "
            "question using ONLY the provided context. If the context does "
            "not contain the answer, say so plainly - do not use outside "
            "knowledge. Format your answer in clean Markdown (headings, "
            "bold, numbered/bulleted lists as appropriate). Cite sources "
            "inline using the exact format (Source: <Title>) with normal "
            "parentheses - never use special bracket characters like 【】."
        )

        client = OpenAI(api_key=self._api_key, base_url="https://api.groq.com/openai/v1")
        response = client.chat.completions.create(
            model=GROQ_MODEL,
            max_tokens=600,
            messages=[
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": f"Context:\n{context}\n\nQuestion: {question}",
                },
            ],
        )
        return response.choices[0].message.content or ""

    def _generate_extractive(self, chunks: List[RetrievedChunk]) -> str:
        lines = ["(No GROQ_API_KEY set - showing extractive results.)\n"]
        for c in chunks:
            lines.append(f"- [{c.title}] {c.text[:300].strip()}...")
        return "\n".join(lines)
