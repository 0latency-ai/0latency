"""Shared embedder preload module for FastAPI and rq workers.

Consolidates SentenceTransformer model loading to ensure parent processes
preload the model before forking, allowing forked children to inherit via
Linux copy-on-write instead of reloading independently.
"""
import os
import logging

logger = logging.getLogger(__name__)

_embedder = None

def get_embedder():
    """Get or lazy-load the local SentenceTransformer model.

    Returns:
        SentenceTransformer: all-MiniLM-L6-v2 model (384d)
    """
    global _embedder
    if _embedder is None:
        from sentence_transformers import SentenceTransformer
        _embedder = SentenceTransformer("all-MiniLM-L6-v2")
        # Warmup inference to avoid deferred init cost on first real call
        _embedder.encode(["warmup"], show_progress_bar=False)
    return _embedder

def preload_embedder():
    """Preload the embedder in parent process before forking.

    Call this at startup in FastAPI lifespan or rq worker entry point.
    """
    get_embedder()


# --- F1: Voyage voyage-3-large (1024-dim, asymmetric encoding) ---

_voyage_client = None

def _get_voyage_client():
    """Lazy-init Voyage client. Reads VOYAGE_API_KEY from env."""
    global _voyage_client
    if _voyage_client is None:
        import voyageai
        api_key = os.environ.get("VOYAGE_API_KEY")
        if not api_key:
            raise RuntimeError("VOYAGE_API_KEY not set")
        _voyage_client = voyageai.Client(api_key=api_key)
    return _voyage_client


def embed_voyage(texts: list[str], input_type: str = "document") -> list[list[float]]:
    """Generate embeddings via Voyage voyage-3-large.

    Args:
        texts: List of strings to embed (max batch ~128 per Voyage docs).
        input_type: "document" for storage, "query" for retrieval.

    Returns:
        List of 1024-dim float vectors, one per input text.
    """
    client = _get_voyage_client()
    result = client.embed(
        texts=texts,
        model="voyage-3-large",
        input_type=input_type,
        truncation=True,
    )
    return result.embeddings


def embed_voyage_single(text: str, input_type: str = "document") -> list[float]:
    """Embed a single text via Voyage. Convenience wrapper."""
    return embed_voyage([text], input_type=input_type)[0]
