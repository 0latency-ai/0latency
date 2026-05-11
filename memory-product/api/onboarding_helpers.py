"""
Onboarding helper utilities for improving first-time user experience.

CP9 Phase 2 Track B3: First-Recall Demo Flow
"""

import re
from typing import List, Optional


# Stop words to filter out (common words with low semantic value)
STOP_WORDS = {
    "the", "is", "at", "which", "on", "and", "or", "but", "in", "with",
    "to", "for", "of", "as", "from", "by", "about", "into", "through",
    "during", "before", "after", "above", "below", "between", "under",
    "again", "further", "then", "once", "here", "there", "when", "where",
    "why", "how", "all", "both", "each", "few", "more", "most", "other",
    "some", "such", "only", "own", "same", "than", "too", "very", "can",
    "will", "just", "should", "now", "was", "were", "been", "being",
    "have", "has", "had", "having", "does", "did", "doing", "would",
    "could", "might", "must", "shall"
}


def extract_keywords_from_headline(headline: str, max_keywords: int = 3) -> str:
    """Extract top keywords from memory headline for suggested recall query.
    
    Uses simple heuristic-based extraction (no LLM):
    1. Prioritize capitalized words (proper nouns, names, places, organizations)
    2. Include longer meaningful words (>4 chars)
    3. Filter out common stop words
    4. Return top N keywords
    
    This is deterministic, latency-free, and has no failure modes.
    
    Args:
        headline: Memory headline to extract keywords from
        max_keywords: Maximum number of keywords to return (default: 3)
        
    Returns:
        Space-separated string of keywords for recall query
        
    Examples:
        >>> extract_keywords_from_headline("Alice Johnson works at TechCorp as a software engineer")
        "Alice Johnson TechCorp"
        
        >>> extract_keywords_from_headline("User prefers Python over JavaScript for backend development")
        "Python JavaScript backend"
        
        >>> extract_keywords_from_headline("The capital of France is Paris")
        "France Paris capital"
    """
    if not headline:
        return ""
    
    # Extract all words (alphanumeric only)
    words = re.findall(r'\b[A-Za-z]+\b', headline)
    
    keywords = []
    seen = set()  # Track to avoid duplicates
    
    # Priority 1: Capitalized words (proper nouns, names, places, organizations)
    # These are often the most important for recall
    for word in words:
        if len(word) > 1 and word[0].isupper() and word.lower() not in STOP_WORDS:
            if word not in seen:
                keywords.append(word)
                seen.add(word)
    
    # Priority 2: Longer meaningful words (>4 chars) not already captured
    # These tend to be more specific and useful for recall
    for word in words:
        if len(word) > 4 and word.lower() not in STOP_WORDS:
            if word not in seen:
                keywords.append(word)
                seen.add(word)
    
    # Priority 3: Medium words (3-4 chars) if we don't have enough yet
    if len(keywords) < max_keywords:
        for word in words:
            if 3 <= len(word) <= 4 and word.lower() not in STOP_WORDS:
                if word not in seen:
                    keywords.append(word)
                    seen.add(word)
                    if len(keywords) >= max_keywords:
                        break
    
    # Return top N keywords
    result = " ".join(keywords[:max_keywords])
    
    # Fallback: if we got nothing, just take first few non-stop words
    if not result:
        fallback_words = [w for w in words if w.lower() not in STOP_WORDS][:max_keywords]
        result = " ".join(fallback_words) if fallback_words else headline[:50]
    
    return result


def should_show_recall_prompt(tenant_id: str, _db_execute_rows) -> bool:
    """Check if this is the tenant's first memory (should show recall prompt).
    
    Uses the onboarding_events table from CP9 P2 T1 to detect first memory.
    
    Args:
        tenant_id: UUID of the tenant
        _db_execute_rows: Database execution function
        
    Returns:
        True if no onboarding event exists (this is first memory), False otherwise
    """
    try:
        rows = _db_execute_rows("""
            SELECT 1 FROM memory_service.onboarding_events
            WHERE tenant_id = %s::UUID AND event_type = 'first_memory_add'
            LIMIT 1
        """, (tenant_id,), tenant_id=tenant_id)
        
        # If no rows returned, this is the first memory
        return len(rows) == 0
    except Exception as e:
        # If table doesn't exist or query fails, don't block the request
        # Just don't show the prompt
        print(f"Warning: Could not check first memory status: {e}")
        return False


def create_next_action_response(headline: str, install_path: str = "sdk") -> dict:
    """Create the next_action object for first-time memory add responses.
    
    Args:
        headline: Headline of the just-added memory
        install_path: Install path (sdk, cli, mcp, web) for path-specific examples
        
    Returns:
        Dictionary with type, suggested_query, and example_command
    """
    suggested_query = extract_keywords_from_headline(headline)
    
    # Path-specific example commands
    if install_path == "cli":
        example_command = f"0latency memory recall '{suggested_query}'"
    elif install_path == "mcp":
        example_command = f"Use the memory_recall tool with query: '{suggested_query}'"
    elif install_path == "web":
        example_command = f"Click 'Recall' and search for: {suggested_query}"
    else:  # sdk or unknown
        example_command = f"client.memory.recall('{suggested_query}')"
    
    return {
        "type": "try_recall",
        "suggested_query": suggested_query,
        "example_command": example_command
    }
