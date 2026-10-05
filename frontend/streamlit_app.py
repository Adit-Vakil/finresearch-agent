"""
FinResearch Streamlit frontend — stub for Phase 1.
Full implementation in Phase 6.
"""
import streamlit as st

st.set_page_config(page_title="FinResearch", page_icon="📊", layout="wide")

st.title("FinResearch")
st.subheader("Evidence-grounded financial research across SEC filings.")

st.info(
    "This interface requires the FinResearch backend to be running. "
    "Start it with `docker compose up` or `uvicorn app.main:app --reload`, "
    "then populate the database using the ingestion scripts."
)

st.markdown("### What this system will do")
st.markdown(
    """
- Ingest SEC 10-K and 10-Q filings from EDGAR
- Parse and chunk filing text intelligently
- Answer research questions grounded in the actual filings
- Return structured citations pointing back to the source document
- Compare retrieval strategies: vector-only vs. hybrid (vector + keyword)
"""
)
