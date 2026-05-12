"""Shared embedder preload module for FastAPI and rq workers.

Consolidates SentenceTransformer model loading to ensure parent processes
preload the model before forking, allowing forked children to inherit via
Linux copy-on-write instead of reloading independently.
"""

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
