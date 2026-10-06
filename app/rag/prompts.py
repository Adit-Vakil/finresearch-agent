"""
Prompt templates for the RAG workflow.
"""

SYSTEM_PROMPT = """\
You are a financial research assistant that answers questions strictly from \
the SEC filing excerpts provided below.

Rules you must follow:
1. Base your answer ONLY on the provided excerpts.
2. If the excerpts do not contain enough information to answer, say so clearly \
   — do not speculate or use general knowledge.
3. Cite sources using [N] notation where N is the excerpt number.
4. Keep the answer factual, concise, and professional.
5. Do not invent filing dates, URLs, company names, or financial figures.
"""

def build_user_message(question: str, context_excerpts: list[dict]) -> str:
    """Format retrieved chunks into a numbered context block."""
    excerpts = []
    for i, chunk in enumerate(context_excerpts, start=1):
        header = (
            f"[{i}] {chunk.get('company', '')} | "
            f"{chunk.get('filing_type', '')} | "
            f"{chunk.get('filing_date', '')} | "
            f"Section: {chunk.get('section') or 'Unknown'}"
        )
        excerpts.append(f"{header}\n{chunk['text']}")

    context_block = "\n\n---\n\n".join(excerpts)
    return (
        f"Context excerpts:\n\n{context_block}\n\n"
        f"Question: {question}\n\n"
        "Answer (cite relevant excerpts with [N]):"
    )
