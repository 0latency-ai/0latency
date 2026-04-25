"""
Graph + Sentiment Extraction — LLM-powered entity, sentiment, and relationship extraction.

Uses:
- GPT-4o-mini for entity extraction + sentiment analysis (cheap + fast)
- GPT-4o for relationship detection (better reasoning)

Called after memory extraction in the /extract pipeline.
"""

import json
import os
import logging
from typing import Optional
import requests

logger = logging.getLogger("zerolatency")


def _openai_key():
    return os.environ.get("OPENAI_API_KEY", "")

def _google_key():
    return os.environ.get("GOOGLE_API_KEY", "")

def _openrouter_key():
    return os.environ.get("OPENROUTER_API_KEY", "")


def _call_gemini(prompt: str, model: str = "gemini-2.0-flash", max_tokens: int = 2048) -> str:
    """Call Gemini API with JSON output."""
    raise NotImplementedError("Gemini removed 2026-04-21; reintegrate with Anthropic/OpenAI when needed")


def _call_openai(prompt: str, model: str = "gpt-4o-mini", max_tokens: int = 2048) -> str:
    """Call OpenAI API with structured JSON output."""
    url = "https://api.openai.com/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {_openai_key()}",
        "Content-Type": "application/json"
    }
    
    body = {
        "model": model,
        "temperature": 0.1,
        "max_tokens": max_tokens,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": "You analyze text and return structured JSON. Always respond with valid JSON."},
            {"role": "user", "content": prompt}
        ]
    }
    
    resp = requests.post(url, headers=headers, json=body, timeout=30)
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]


def _call_openrouter(prompt: str, model: str = "openai/gpt-4o-mini", max_tokens: int = 2048) -> str:
    """Call OpenRouter API as fallback."""
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {_openrouter_key()}",
        "Content-Type": "application/json"
    }
    
    body = {
        "model": model,
        "temperature": 0.1,
        "max_tokens": max_tokens,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": "You analyze text and return structured JSON. Always respond with valid JSON."},
            {"role": "user", "content": prompt}
        ]
    }
    
    resp = requests.post(url, headers=headers, json=body, timeout=30)
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]


def _call_model_fast(prompt: str) -> str:
    """Call a fast/cheap model for entity extraction and sentiment. Fallback chain."""
    # Prefer Gemini Flash (cheapest + fastest)
    if _google_key():
        try:
            return _call_gemini(prompt, model="gemini-2.0-flash")
        except Exception as e:
            logger.debug(f"Gemini fast call failed: {e}")
    
    # OpenAI GPT-4o-mini
    if _openai_key() and "placeholder" not in _openai_key():
        try:
            return _call_openai(prompt, model="gpt-4o-mini")
        except Exception as e:
            logger.debug(f"OpenAI fast call failed: {e}")
    
    # OpenRouter fallback
    if _openrouter_key():
        try:
            return _call_openrouter(prompt, model="openai/gpt-4o-mini")
        except Exception as e:
            logger.debug(f"OpenRouter fast call failed: {e}")
    
    raise RuntimeError("No LLM API available for graph_sentiment")


def _call_model_smart(prompt: str) -> str:
    """Call a smarter model for relationship detection. Fallback chain."""
    # Prefer Gemini Pro for reasoning
    if _google_key():
        try:
            return _call_gemini(prompt, model="gemini-2.0-flash")  # Flash is fine for this
        except Exception as e:
            logger.debug(f"Gemini smart call failed: {e}")
    
    # OpenAI GPT-4o
    if _openai_key() and "placeholder" not in _openai_key():
        try:
            return _call_openai(prompt, model="gpt-4o")
        except Exception as e:
            logger.debug(f"OpenAI smart call failed: {e}")
    
    # OpenRouter fallback
    if _openrouter_key():
        try:
            return _call_openrouter(prompt, model="openai/gpt-4o")
        except Exception as e:
            logger.debug(f"OpenRouter smart call failed: {e}")
    
    raise RuntimeError("No LLM API available for relationship detection")


# ============================================================
# Entity Extraction (GPT-4o-mini)
# ============================================================

ENTITY_EXTRACTION_PROMPT = """Extract all named entities from this conversation turn. For each entity, identify its type.

Valid entity types: person, organization, concept, technology, location, product, project, event

Rules:
- Only extract concrete, named entities (not generic nouns like "the app" or "the user")
- Merge variations of the same entity (e.g., "React" and "ReactJS" → "React")
- Include proper nouns, product names, company names, technology names, place names
- Do NOT extract pronouns or generic references

Conversation:
Human: {human_message}
Agent: {agent_message}

Return JSON: {{"entities": [{{"text": "entity name", "type": "entity_type"}}]}}
If no entities found, return: {{"entities": []}}"""


def extract_entities(human_message: str, agent_message: str) -> list[dict]:
    """Extract named entities from a conversation turn using fast LLM.
    
    Returns: [{"text": "React", "type": "technology"}, ...]
    """
    # Skip for very short messages
    combined = (human_message or "") + (agent_message or "")
    if len(combined) < 30:
        return []
    
    try:
        prompt = ENTITY_EXTRACTION_PROMPT.format(
            human_message=human_message[:3000],
            agent_message=agent_message[:3000],
        )
        raw = _call_model_fast(prompt)
        result = json.loads(raw)
        
        entities = result.get("entities", [])
        # Validate
        validated = []
        valid_types = {"person", "organization", "concept", "technology", 
                      "location", "product", "project", "event"}
        for e in entities:
            if isinstance(e, dict) and e.get("text"):
                etype = e.get("type", "concept")
                if etype not in valid_types:
                    etype = "concept"
                validated.append({"text": e["text"].strip(), "type": etype})
        
        return validated
    except Exception as e:
        logger.error(f"Entity extraction failed: {e}")
        return []


# ============================================================
# Sentiment Analysis (GPT-4o-mini)
# ============================================================

SENTIMENT_PROMPT = """Analyze the sentiment of each memory statement below. For each one, determine:
- sentiment: 'positive', 'negative', or 'neutral'
- score: -1.0 (most negative) to 1.0 (most positive)
- intensity: 0.0 (very weak/mild) to 1.0 (very strong/passionate)

Guidelines:
- Factual statements with no emotional valence → neutral, score ~0.0, intensity 0.1-0.2
- Preferences/likes → positive, score 0.3-0.8 depending on strength
- Dislikes/complaints → negative, score -0.3 to -0.8
- Strong emotions (love/hate/excited/frustrated) → high intensity (0.7-1.0)
- Mild observations → low intensity (0.1-0.3)

Memory statements:
{statements}

Return JSON: {{"sentiments": [{{"index": 0, "sentiment": "positive", "score": 0.7, "intensity": 0.8}}, ...]}}"""


def analyze_sentiment(memory_headlines: list[str]) -> list[dict]:
    """Analyze sentiment for a batch of memory headlines using fast LLM.
    
    Args:
        memory_headlines: List of memory headline/context strings
    
    Returns: [{"sentiment": "positive", "score": 0.7, "intensity": 0.8}, ...]
             Same length as input, with defaults for failures.
    """
    if not memory_headlines:
        return []
    
    try:
        # Format statements with indices
        statements = "\n".join(f"[{i}] {h}" for i, h in enumerate(memory_headlines))
        prompt = SENTIMENT_PROMPT.format(statements=statements[:4000])
        
        raw = _call_model_fast(prompt)
        result = json.loads(raw)
        
        sentiments = result.get("sentiments", [])
        
        # Build indexed lookup
        sentiment_map = {}
        for s in sentiments:
            if isinstance(s, dict) and "index" in s:
                idx = int(s["index"])
                sentiment_label = s.get("sentiment", "neutral")
                if sentiment_label not in ("positive", "negative", "neutral"):
                    sentiment_label = "neutral"
                sentiment_map[idx] = {
                    "sentiment": sentiment_label,
                    "score": max(-1.0, min(1.0, float(s.get("score", 0.0)))),
                    "intensity": max(0.0, min(1.0, float(s.get("intensity", 0.1)))),
                }
        
        # Return in order, with defaults for missing
        default = {"sentiment": "neutral", "score": 0.0, "intensity": 0.1}
        return [sentiment_map.get(i, default) for i in range(len(memory_headlines))]
        
    except Exception as e:
        logger.error(f"Sentiment analysis failed: {e}")
        return [{"sentiment": "neutral", "score": 0.0, "intensity": 0.1}] * len(memory_headlines)


# ============================================================
# Relationship Detection (GPT-4o)
# ============================================================

RELATIONSHIP_PROMPT = """Given these memories, identify semantic relationships between them.

Valid relationship types:
- causes: Memory A caused or led to memory B
- relates_to: General semantic connection
- contradicts: Memory A contradicts or conflicts with memory B  
- supports: Memory A provides evidence for or reinforces memory B
- requires: Memory A depends on or requires memory B
- implies: Memory A logically implies memory B
- supersedes: Memory A is a newer version/update of memory B

For each relationship, also provide a strength score (0.0-1.0):
- 1.0: Extremely strong, direct connection
- 0.7-0.9: Clear, meaningful connection
- 0.4-0.6: Moderate connection
- 0.1-0.3: Weak/tangential connection

NEW memories (just extracted):
{new_memories}

EXISTING memories (from prior context):
{existing_memories}

Return JSON: {{"relationships": [{{"source_id": "uuid", "target_id": "uuid", "type": "relates_to", "strength": 0.7}}, ...]}}
If no meaningful relationships found, return: {{"relationships": []}}
Only include relationships with strength >= 0.3. Quality over quantity."""


def detect_relationships(
    new_memories: list[dict], 
    existing_memories: list[dict],
) -> list[dict]:
    """Detect relationships between new and existing memories using smart LLM.
    
    Args:
        new_memories: List of newly extracted memories with 'id' and 'headline'
        existing_memories: List of existing similar memories with 'id' and 'headline'
    
    Returns: [{"source_id": "...", "target_id": "...", "type": "relates_to", "strength": 0.7}, ...]
    """
    if not new_memories or not existing_memories:
        return []
    
    try:
        # Format memories for the prompt
        new_strs = "\n".join(f"- [{m.get('id', 'unknown')}] {m.get('headline', '')}" 
                            for m in new_memories[:10])
        existing_strs = "\n".join(f"- [{m.get('id', 'unknown')}] {m.get('headline', '')}" 
                                  for m in existing_memories[:10])
        
        prompt = RELATIONSHIP_PROMPT.format(
            new_memories=new_strs,
            existing_memories=existing_strs,
        )
        
        raw = _call_model_smart(prompt)
        result = json.loads(raw)
        
        relationships = result.get("relationships", [])
        
        # Validate
        valid_types = {"causes", "relates_to", "contradicts", "supports", 
                      "requires", "implies", "supersedes"}
        # Collect valid memory IDs
        valid_ids = set()
        for m in new_memories + existing_memories:
            if m.get("id"):
                valid_ids.add(str(m["id"]))
        
        validated = []
        for r in relationships:
            if not isinstance(r, dict):
                continue
            source_id = str(r.get("source_id", ""))
            target_id = str(r.get("target_id", ""))
            rel_type = r.get("type", "relates_to")
            strength = float(r.get("strength", 0.5))
            
            # Validate IDs exist in our set
            if source_id not in valid_ids or target_id not in valid_ids:
                continue
            if source_id == target_id:
                continue
            if rel_type not in valid_types:
                rel_type = "relates_to"
            strength = max(0.0, min(1.0, strength))
            if strength < 0.3:
                continue
            
            validated.append({
                "source_id": source_id,
                "target_id": target_id,
                "type": rel_type,
                "strength": strength,
            })
        
        return validated
    except Exception as e:
        logger.error(f"Relationship detection failed: {e}")
        return []


# ============================================================
# Confidence Scoring
# ============================================================

def calculate_initial_confidence(memory: dict, existing_memories: list[dict] = None) -> float:
    """Calculate initial confidence score for a newly extracted memory.
    
    Scoring:
    - Base: 0.5
    - +0.2 if extracted from explicit statement ("I prefer", "I want", "I decided")
    - +0.1 if corroborated by existing context
    - +0.1 if related to existing high-confidence memories
    - -0.2 if contradicts existing memories
    """
    confidence = memory.get("confidence", 0.5)
    
    headline = (memory.get("headline", "") + " " + memory.get("full_content", "")).lower()
    
    # Explicit statement indicators
    explicit_markers = [
        "i prefer", "i want", "i need", "i decided", "i chose", "we agreed",
        "i like", "i hate", "i always", "i never", "my name is", "i am",
        "we will", "the plan is", "the decision is"
    ]
    if any(marker in headline for marker in explicit_markers):
        confidence = min(1.0, confidence + 0.2)
    
    # Identity type gets high base confidence
    if memory.get("memory_type") == "identity":
        confidence = max(confidence, 0.85)
    
    # Decision type gets moderate-high confidence
    if memory.get("memory_type") == "decision":
        confidence = max(confidence, 0.7)
    
    # Check against existing memories for corroboration/contradiction
    if existing_memories:
        for existing in existing_memories:
            existing_headline = existing.get("headline", "").lower()
            # Simple corroboration check: shared entities or similar content
            shared_entities = set(memory.get("entities", [])) & set(existing.get("entities", []))
            if shared_entities:
                existing_confidence = existing.get("confidence", 0.5)
                if existing_confidence > 0.7:
                    confidence = min(1.0, confidence + 0.1)
                    break
    
    # Cap at 0.95 for initial extraction (only recall reinforcement reaches 1.0)
    return min(0.95, max(0.1, confidence))


def boost_confidence_on_recall(current_confidence: float, recall_count: int) -> float:
    """Boost confidence when a memory is recalled and used.
    
    +0.05 per recall, capped at 0.95.
    Diminishing returns after 5 recalls.
    """
    if recall_count >= 10:
        return min(0.95, current_confidence)
    
    boost = 0.05 * (1.0 - (recall_count / 10.0))  # Diminishing returns
    return min(0.95, current_confidence + boost)


# ============================================================
# Feature Gating
# ============================================================

def check_feature_access(tenant: dict, feature: str) -> bool:
    """Check if a tenant's plan allows access to a feature.
    
    Free tier: Core memory only
    Pro tier ($19/mo): Graph + Sentiment + Entities
    Scale tier ($89/mo): Everything in Pro + depth=3 graph + batch ops
    Enterprise: Everything
    """
    plan = tenant.get("plan", "free")
    
    # Graph, sentiment, and entity features require Pro or above
    if feature in ("graph", "sentiment", "entities", "sentiment_summary"):
        return plan in ("pro", "scale", "enterprise")
    
    # Deep graph traversal (depth=3) requires Scale
    if feature == "graph_depth_3":
        return plan in ("scale", "enterprise")
    
    # Batch operations require Scale or above
    if feature == "batch_ops":
        return plan in ("scale", "enterprise")
    
    # Everything else is available to all plans
    return True


def get_max_graph_depth(tenant: dict) -> int:
    """Get maximum allowed graph traversal depth for tenant's plan."""
    plan = tenant.get("plan", "free")
    if plan in ("scale", "enterprise"):
        return 3
    if plan == "pro":
        return 2
    return 0  # Free tier has no graph access


# ============================================================
# Pipeline Integration — run after memory extraction
# ============================================================

def run_graph_sentiment_pipeline(
    memories: list[dict],
    stored_ids: list[str],
    agent_id: str,
    tenant_id: str,
    tenant: dict,
    human_message: str = "",
    agent_message: str = "",
):
    """Run the full graph + sentiment pipeline after memory extraction.
    
    This is called from the /extract endpoint after memories are stored.
    Non-blocking — failures here don't affect the core extraction.
    
    Steps:
    1. Entity extraction (GPT-4o-mini) → upsert entities + link to memories
    2. Sentiment analysis (GPT-4o-mini) → update memories with sentiment
    3. Relationship detection (GPT-4o) → create memory relationships
    4. Confidence scoring → update confidence values
    """
    from storage_multitenant import _db_execute_rows
    
    # Check if tenant has access to these features
    if not check_feature_access(tenant, "sentiment"):
        return {"skipped": "plan_not_eligible"}
    
    result = {
        "entities_extracted": 0,
        "sentiments_analyzed": 0,
        "relationships_detected": 0,
    }
    
    # Map stored IDs back to memories
    if len(stored_ids) != len(memories):
        # Best effort — match by index
        for i, mem in enumerate(memories):
            if i < len(stored_ids):
                mem["id"] = stored_ids[i]
    
    # --- Step 1: Entity Extraction ---
    try:
        entities = extract_entities(human_message, agent_message)
        if entities:
            from graph import upsert_entity as graph_upsert_entity
            for entity in entities:
                try:
                    entity_id = graph_upsert_entity(
                        agent_id, 
                        entity["text"], 
                        entity_type=entity.get("type", "concept"),
                        tenant_id=tenant_id,
                    )
                    # Link entity to all memories from this turn
                    for mem_id in stored_ids:
                        try:
                            _db_execute_rows("""
                                INSERT INTO memory_service.entity_index 
                                    (tenant_id, agent_id, entity, memory_id)
                                VALUES (%s::UUID, %s, %s, %s)
                                ON CONFLICT (agent_id, entity, memory_id) DO NOTHING
                            """, (tenant_id, agent_id, entity["text"], mem_id),
                                tenant_id=tenant_id, fetch_results=False)
                        except Exception as e:
                            logger.warning(f"entity_index upsert failed: {e}")
                except Exception as e:
                    logger.debug(f"Entity upsert failed for {entity['text']}: {e}")
            
            result["entities_extracted"] = len(entities)
    except Exception as e:
        logger.error(f"Entity extraction pipeline failed: {e}")
    
    # --- Step 2: Sentiment Analysis ---
    try:
        headlines = [m.get("headline", "") for m in memories if m.get("headline")]
        if headlines:
            sentiments = analyze_sentiment(headlines)
            
            for i, (mem, sent) in enumerate(zip(memories, sentiments)):
                mem_id = stored_ids[i] if i < len(stored_ids) else None
                if not mem_id:
                    continue
                try:
                    _db_execute_rows("""
                        UPDATE memory_service.memories 
                        SET sentiment = %s,
                            sentiment_score = %s,
                            sentiment_intensity = %s
                        WHERE id = %s::UUID AND tenant_id = %s::UUID
                    """, (
                        sent["sentiment"],
                        sent["score"],
                        sent["intensity"],
                        mem_id,
                        tenant_id,
                    ), tenant_id=tenant_id, fetch_results=False)
                except Exception as e:
                    logger.debug(f"Sentiment update failed for {mem_id}: {e}")
            
            result["sentiments_analyzed"] = len(sentiments)
    except Exception as e:
        logger.error(f"Sentiment analysis pipeline failed: {e}")
    
    # --- Step 3: Relationship Detection ---
    try:
        if stored_ids and memories:
            # Get existing similar memories for relationship detection
            from storage_multitenant import _embed_text
            
            # Use the first memory's headline as query
            first_headline = memories[0].get("headline", "")
            if first_headline:
                embedding = _embed_text(first_headline)
                embedding_str = "[" + ",".join(str(v) for v in embedding) + "]"
                
                existing_rows = _db_execute_rows("""
                    SELECT id, headline
                    FROM memory_service.memories
                    WHERE agent_id = %s AND tenant_id = %s::UUID 
                      AND superseded_at IS NULL
                      AND id NOT IN (SELECT unnest(%s::uuid[]))
                    ORDER BY embedding <=> %s::extensions.vector
                    LIMIT 10
                """, (agent_id, tenant_id, stored_ids, embedding_str),
                    tenant_id=tenant_id)
                
                existing_memories = [
                    {"id": str(r[0]), "headline": str(r[1])}
                    for r in (existing_rows or [])
                ]
                
                if existing_memories:
                    new_memory_dicts = [
                        {"id": stored_ids[i], "headline": m.get("headline", "")}
                        for i, m in enumerate(memories) if i < len(stored_ids)
                    ]
                    
                    relationships = detect_relationships(new_memory_dicts, existing_memories)
                    
                    for rel in relationships:
                        try:
                            # Find entity names for the relationship
                            # Use the graph module's relationship system
                            from graph import add_relationship as add_entity_rel
                            
                            # Store as a memory-level edge
                            _db_execute_rows("""
                                INSERT INTO memory_service.memory_edges 
                                    (tenant_id, source_memory_id, target_memory_id, 
                                     relationship, strength)
                                VALUES (%s::UUID, %s::UUID, %s::UUID, %s, %s)
                                ON CONFLICT (source_memory_id, target_memory_id, relationship) 
                                DO UPDATE SET strength = GREATEST(
                                    memory_service.memory_edges.strength, EXCLUDED.strength
                                )
                            """, (
                                tenant_id,
                                rel["source_id"],
                                rel["target_id"],
                                rel["type"],
                                rel["strength"],
                            ), tenant_id=tenant_id, fetch_results=False)
                        except Exception as e:
                            logger.debug(f"Relationship storage failed: {e}")
                    
                    result["relationships_detected"] = len(relationships)
    except Exception as e:
        logger.error(f"Relationship detection pipeline failed: {e}")
    
    # --- Step 4: Confidence Scoring ---
    try:
        for i, mem in enumerate(memories):
            mem_id = stored_ids[i] if i < len(stored_ids) else None
            if not mem_id:
                continue
            
            # Get existing memories for corroboration check
            existing_for_confidence = []
            try:
                rows = _db_execute_rows("""
                    SELECT headline, confidence, entities
                    FROM memory_service.memories
                    WHERE agent_id = %s AND tenant_id = %s::UUID 
                      AND superseded_at IS NULL AND id != %s::UUID
                    ORDER BY created_at DESC LIMIT 20
                """, (agent_id, tenant_id, mem_id), tenant_id=tenant_id)
                existing_for_confidence = [
                    {"headline": str(r[0]), "confidence": float(r[1]) if r[1] else 0.5, 
                     "entities": list(r[2]) if r[2] else []}
                    for r in (rows or [])
                ]
            except Exception:
                pass
            
            new_confidence = calculate_initial_confidence(mem, existing_for_confidence)
            
            try:
                _db_execute_rows("""
                    UPDATE memory_service.memories 
                    SET confidence = %s
                    WHERE id = %s::UUID AND tenant_id = %s::UUID
                """, (new_confidence, mem_id, tenant_id),
                    tenant_id=tenant_id, fetch_results=False)
            except Exception as e:
                logger.debug(f"Confidence update failed for {mem_id}: {e}")
    except Exception as e:
        logger.error(f"Confidence scoring pipeline failed: {e}")
    
    return result
