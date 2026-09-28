"""
Streamlit demo UI for the Secure Enterprise RAG system.

Run:
    streamlit run streamlit_app.py
"""

import os

import streamlit as st

from src.auth import UserDirectory
from src.ingest import build_index
from src.rag_pipeline import SecureRAGPipeline
from src.config import CHROMA_PERSIST_DIR

st.set_page_config(page_title="Secure Enterprise RAG (RBAC)", layout="wide")


@st.cache_resource
def get_directory():
    return UserDirectory()


@st.cache_resource
def get_pipeline():
    # If deployed somewhere with an ephemeral filesystem (e.g. some cloud
    # hosts), the Chroma index may not exist yet on first boot - build it
    # automatically so the app is self-sufficient.
    if not os.path.exists(CHROMA_PERSIST_DIR) or not os.listdir(CHROMA_PERSIST_DIR):
        with st.spinner("First-time setup: building the document index..."):
            build_index(reset=True)
    return SecureRAGPipeline()


directory = get_directory()

if "user" not in st.session_state:
    st.session_state.user = None

st.title("🔐 Secure Enterprise Document Intelligence")
st.caption("RAG with Role-Based Access Control - retrieval is filtered by role "
           "*before* any content reaches the answer.")

# ---------------------------------------------------------------------
# Login screen
# ---------------------------------------------------------------------
if st.session_state.user is None:
    st.subheader("Sign in")
    with st.form("login_form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Log in")

    if submitted:
        try:
            st.session_state.user = directory.login(username, password)
            st.rerun()
        except PermissionError as e:
            st.error(str(e))

    with st.expander("Demo accounts (for testing)"):
        st.markdown(
            "Each demo user has their own password. Ask whoever set up this "
            "project for credentials, or create your own with "
            "`python scripts/create_user.py`."
        )
    st.stop()

# ---------------------------------------------------------------------
# Main app (authenticated)
# ---------------------------------------------------------------------
user = st.session_state.user
pipeline = get_pipeline()

with st.sidebar:
    st.header("Session")
    st.markdown(f"**Name:** {user.full_name}")
    st.markdown(f"**Username:** {user.username}")
    st.markdown(f"**Role:** `{user.role.name}`")
    st.markdown(f"**Departments allowed:** {sorted(user.role.allowed_departments)}")
    st.markdown(f"**Max confidentiality level:** {user.role.max_confidentiality}")
    if st.button("Log out"):
        st.session_state.user = None
        st.rerun()

question = st.text_input("Ask a question about company documents",
                          placeholder="e.g. What is the remote work policy?")

if st.button("Ask") and question:
    with st.spinner("Retrieving accessible documents and generating answer..."):
        result = pipeline.ask(question, user)

    st.subheader("Answer")
    st.write(result.answer)

    if result.sources:
        st.subheader("Sources")
        for s in result.sources:
            with st.expander(f"{s.title}  ·  {s.department}  ·  level {s.confidentiality_level}"):
                st.write(s.text)

    if result.denied_count:
        st.warning(
            f"{result.denied_count} matching chunk(s) existed but were withheld "
            f"because they exceed your role's access level."
        )
