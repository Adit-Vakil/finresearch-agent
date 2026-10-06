"""
Embedding layer.

Wraps sentence-transformers so the rest of the codebase never imports
it directly.  Batch encoding is used throughout; single-string encoding
is a thin wrapper.  The model is loaded once and reused.
"""

import logging
from typing import Optional

import numpy as np

from app.core.config import settings

logger = logging.getLogger(__name__)

_model = None


def _get_model():
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer

        logger.info("Loading embedding model: %s", settings.EMBEDDING_MODEL)
        _model = SentenceTransformer(settings.EMBEDDING_MODEL)
        dim = _model.get_embedding_dimension()
        logger.info("Embedding model loaded (dim=%d)", dim)
    return _model


def embed_texts(texts: list[str], batch_size: int = 64) -> list[list[float]]:
    """Embed a list of strings. Returns a list of float vectors."""
    if not texts:
        return []
    model = _get_model()
    vectors: np.ndarray = model.encode(
        texts,
        batch_size=batch_size,
        show_progress_bar=False,
        normalize_embeddings=True,
    )
    return vectors.tolist()


def embed_query(query: str) -> list[float]:
    """Embed a single query string."""
    return embed_texts([query])[0]


def embedding_dim() -> int:
    """Return the dimension of vectors produced by the current model."""
    return _get_model().get_embedding_dimension()
