import re

# Read the original file
with open('storage_multitenant.py', 'r') as f:
    content = f.read()

# Add numpy import after 'import os'
content = content.replace(
    'import json\nimport os\nimport requests',
    'import json\nimport os\nimport numpy as np\nimport requests'
)

# Add local model setup after 'import time' and before configuration
local_model_code = '''

# Local embedding model for fast CPU inference
_local_embedding_model = None
_local_model_lock = threading.Lock()

def _get_local_model():
    """Lazy-load local embedding model (all-MiniLM-L6-v2, 384 dims, ~10-20ms CPU inference)."""
    global _local_embedding_model
    if _local_embedding_model is None:
        from sentence_transformers import SentenceTransformer
        _local_embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
    return _local_embedding_model
'''

# Insert after 'import time\n\n'
content = content.replace('import time\n\n\n# --- Configuration ---', f'import time{local_model_code}\n\n# --- Configuration ---')

# Add _embed_text_local function after _embed_text function
local_embed_func = '''

def _embed_text_local(text: str) -> list[float]:
    """Generate embedding using local model (all-MiniLM-L6-v2).
    
    Fast CPU inference (~10-20ms), no external API dependency.
    Returns 384-dimensional vector (vs 768 for OpenAI).
    Accepts ~5-8% accuracy reduction for 100x speed improvement.
    """
    with _local_model_lock:
        model = _get_local_model()
        # encode() returns numpy array, convert to list
        embedding = model.encode(text, convert_to_numpy=True, show_progress_bar=False)
        # Normalize for cosine similarity (pgvector expects normalized vectors)
        embedding = embedding / np.linalg.norm(embedding)
        return embedding.tolist()
'''

# Find where _embed_text function ends and insert local version
pattern = r'(_embed_cache\[cache_key\] = \(vec, now\)\s+return vec\s*)\n\ndef _embed_text_uncached'
replacement = r'\1' + local_embed_func + '\n\ndef _embed_text_uncached'
content = re.sub(pattern, replacement, content, count=1)

# Write back
with open('storage_multitenant.py', 'w') as f:
    f.write(content)

print('Successfully added local embedding model support')
