import os
import logging
from typing import List, Optional

logger = logging.getLogger("ai_os.embeddings")

_model = None
_model_lock = None


def _get_model():
    """
    Lazy-load the sentence-transformers model.
    Uses all-MiniLM-L6-v2 (384 dimensions) for local embedding generation.
    """
    global _model
    if _model is not None:
        return _model

    try:
        from sentence_transformers import SentenceTransformer
        model_name = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")
        logger.info(f"Loading embedding model: {model_name}...")
        _model = SentenceTransformer(model_name)
        logger.info(f"Embedding model loaded. Dimension: {_model.get_sentence_embedding_dimension()}")
        return _model
    except ImportError:
        logger.error(
            "sentence-transformers not installed. "
            "Install with: pip install sentence-transformers"
        )
        return None
    except Exception as e:
        logger.error(f"Failed to load embedding model: {e}")
        return None


def get_embedding_dimension() -> int:
    """Returns the dimension of the embedding model vectors."""
    model = _get_model()
    if model is not None:
        return model.get_sentence_embedding_dimension()
    return 384


def embed_text(text: str) -> List[float]:
    """
    Generates a 384-dimensional embedding vector for a single text string.
    Returns a list of floats suitable for Qdrant upsert.
    """
    model = _get_model()
    if model is None:
        import random
        logger.warning("Embedding model unavailable. Returning random vector (DEGRADED MODE).")
        return [random.uniform(-0.1, 0.1) for _ in range(384)]

    try:
        vector = model.encode(text, normalize_embeddings=True)
        return vector.tolist()
    except Exception as e:
        logger.error(f"Embedding generation failed for text (len={len(text)}): {e}")
        import random
        return [random.uniform(-0.1, 0.1) for _ in range(384)]


def embed_batch(texts: List[str], batch_size: int = 64) -> List[List[float]]:
    """
    Generates embeddings for a batch of text strings.
    Uses sentence-transformers native batching for efficiency.
    """
    model = _get_model()
    if model is None:
        import random
        logger.warning("Embedding model unavailable. Returning random vectors (DEGRADED MODE).")
        return [[random.uniform(-0.1, 0.1) for _ in range(384)] for _ in texts]

    try:
        vectors = model.encode(
            texts,
            normalize_embeddings=True,
            batch_size=batch_size,
            show_progress_bar=False
        )
        return [v.tolist() for v in vectors]
    except Exception as e:
        logger.error(f"Batch embedding failed for {len(texts)} texts: {e}")
        import random
        return [[random.uniform(-0.1, 0.1) for _ in range(384)] for _ in texts]


def chunk_text(text: str, max_chunk_size: int = 512, overlap: int = 64) -> List[str]:
    """
    Splits text into overlapping chunks by character count.
    Respects word boundaries to avoid cutting mid-word.
    Target: ~512 characters per chunk with ~64 character overlap.
    """
    if len(text) <= max_chunk_size:
        return [text]

    words = text.split()
    chunks = []
    current_chunk = []
    current_size = 0

    for word in words:
        word_size = len(word) + 1  # +1 for space

        if current_size + word_size > max_chunk_size and current_chunk:
            chunk_str = " ".join(current_chunk)
            chunks.append(chunk_str)

            overlap_words = []
            overlap_size = 0
            for w in reversed(current_chunk):
                if overlap_size + len(w) + 1 > overlap:
                    break
                overlap_words.insert(0, w)
                overlap_size += len(w) + 1

            current_chunk = overlap_words
            current_size = overlap_size

        current_chunk.append(word)
        current_size += word_size

    if current_chunk:
        chunks.append(" ".join(current_chunk))

    return chunks
