"""
FinResearch — Streamlit frontend.

Connects to the FastAPI backend at FINRESEARCH_API_URL (default: localhost:8000).
"""

import os

import requests
import streamlit as st

API_URL = os.getenv("FINRESEARCH_API_URL", "http://localhost:8000")

st.set_page_config(
    page_title="FinResearch",
    page_icon="📊",
    layout="wide",
)

# ------------------------------------------------------------------
# Sidebar
# ------------------------------------------------------------------

with st.sidebar:
    st.title("FinResearch")
    st.caption("Evidence-grounded financial research across SEC filings.")
    st.divider()

    ticker = st.text_input("Ticker (optional)", placeholder="AAPL")
    filing_type = st.selectbox("Filing type", ["", "10-K", "10-Q"], index=0)
    retrieval_mode = st.selectbox("Retrieval mode", ["hybrid", "vector", "keyword"], index=0)
    top_k = st.slider("Retrieved sources", min_value=3, max_value=15, value=6)

    st.divider()
    if st.button("Check backend health"):
        try:
            resp = requests.get(f"{API_URL}/health", timeout=5)
            data = resp.json()
            if data.get("db_connected"):
                st.success(f"Backend healthy — v{data.get('version', '?')}")
            else:
                st.warning("Backend up but database not connected.")
        except Exception as exc:
            st.error(f"Cannot reach backend: {exc}")

    st.divider()
    if st.button("Load available companies"):
        try:
            resp = requests.get(f"{API_URL}/companies", timeout=10)
            companies = resp.json()
            if companies:
                st.write(f"**{len(companies)} companies indexed:**")
                for c in companies[:20]:
                    st.write(f"- {c['ticker']}: {c.get('company_name', '')}")
            else:
                st.info("No companies indexed yet. Run the ingestion script first.")
        except Exception as exc:
            st.error(f"Error: {exc}")

# ------------------------------------------------------------------
# Main panel
# ------------------------------------------------------------------

st.markdown("## Ask a question about SEC filings")
st.caption(
    "Answers are generated from retrieved filing excerpts. "
    "All citations link back to the original SEC document."
)

EXAMPLE_QUESTIONS = [
    "What risks did the company identify related to supply chains?",
    "What changed in revenue compared to the prior year?",
    "What did management say about competition?",
    "What are the company's major operating risks?",
    "How did gross margin change and why?",
]

with st.expander("Example questions"):
    for q in EXAMPLE_QUESTIONS:
        if st.button(q, key=q):
            st.session_state["question"] = q

question = st.text_area(
    "Your question",
    value=st.session_state.get("question", ""),
    height=80,
    placeholder="e.g. What risks did the company identify?",
)

col_ask, col_search, _ = st.columns([2, 2, 6])
ask_clicked = col_ask.button("Search & Answer", type="primary")
search_clicked = col_search.button("Search only", type="secondary")

if ask_clicked and question.strip():
    params = {"mode": retrieval_mode}
    payload = {
        "question": question.strip(),
        "ticker": ticker.upper() if ticker.strip() else None,
        "filing_type": filing_type if filing_type else None,
    }

    with st.spinner("Retrieving evidence and generating answer…"):
        try:
            resp = requests.post(
                f"{API_URL}/ask",
                json=payload,
                params=params,
                timeout=60,
            )
            resp.raise_for_status()
            data = resp.json()
        except requests.HTTPError as exc:
            st.error(f"API error {exc.response.status_code}: {exc.response.text}")
            st.stop()
        except Exception as exc:
            st.error(f"Request failed: {exc}")
            st.stop()

    st.divider()
    st.markdown("### Answer")
    st.write(data["answer"])

    sources = data.get("sources", [])
    if sources:
        st.divider()
        st.markdown(f"### Sources ({len(sources)})")
        for i, src in enumerate(sources, start=1):
            label = (
                f"[{i}] {src.get('company', src.get('ticker', '?'))} — "
                f"{src.get('filing_type', '')} ({src.get('filing_date', '')})"
                + (f" | {src['section']}" if src.get("section") else "")
            )
            with st.expander(label):
                col1, col2 = st.columns(2)
                col1.metric("Ticker", src.get("ticker", ""))
                col2.metric("Filing", src.get("filing_type", ""))
                st.write(f"**Date:** {src.get('filing_date', '')}")
                st.write(f"**Section:** {src.get('section') or '—'}")
                if src.get("source_url"):
                    st.markdown(f"[View on SEC EDGAR]({src['source_url']})")
    else:
        st.info("No sources returned. The database may not have relevant filings.")

    st.caption(f"Retrieval mode: **{retrieval_mode}** | Model: {data.get('model', '?')}")

elif search_clicked and question.strip():
    params = {"mode": retrieval_mode}
    payload = {
        "query": question.strip(),
        "ticker": ticker.upper() if ticker.strip() else None,
        "filing_type": filing_type if filing_type else None,
        "top_k": top_k,
    }

    with st.spinner("Searching…"):
        try:
            resp = requests.post(
                f"{API_URL}/search",
                json=payload,
                params=params,
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()
        except Exception as exc:
            st.error(f"Search failed: {exc}")
            st.stop()

    results = data.get("results", [])
    st.divider()
    st.markdown(f"### {len(results)} results — mode: {data.get('retrieval_mode', '?')}")
    for i, r in enumerate(results, start=1):
        label = (
            f"[{i}] score={r['score']:.3f} | {r.get('company', r['ticker'])} "
            f"| {r['filing_type']} ({r['filing_date']})"
            + (f" | {r['section']}" if r.get("section") else "")
        )
        with st.expander(label):
            st.write(r["text"])
            if r.get("source_url"):
                st.markdown(f"[View on SEC EDGAR]({r['source_url']})")
