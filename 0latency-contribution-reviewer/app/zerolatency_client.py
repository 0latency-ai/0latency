"""0Latency API client for memory storage and retrieval."""

import httpx
from typing import Dict, List, Any, Optional
from datetime import datetime

from .config import get_config


class ZeroLatencyClient:
    """Client for 0Latency memory API."""
    
    def __init__(self):
        cfg = get_config()
        self.api_key = cfg.get('zerolatency.api_key')
        self.api_url = cfg.get('zerolatency.api_url')
        self.headers = {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json'
        }
    
    async def store_review_decision(
        self, 
        contribution_id: str,
        contributor: str,
        decision: Dict[str, Any],
        context: str
    ) -> Dict[str, Any]:
        """Store review decision as a memory."""
        memory_text = (
            f"Contribution review for {contributor}: "
            f"{decision['recommendation']} with {decision['confidence']:.0%} confidence. "
            f"Reason: {decision['reason']}"
        )
        
        payload = {
            'text': memory_text,
            'context': context,
            'metadata': {
                'contribution_id': contribution_id,
                'contributor': contributor,
                'type': decision['type'],
                'recommendation': decision['recommendation'],
                'confidence': decision['confidence'],
                'promo_tier': decision.get('promo_tier'),
                'timestamp': datetime.utcnow().isoformat()
            }
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f'{self.api_url}/memories',
                headers=self.headers,
                json=payload,
                timeout=10.0
            )
            response.raise_for_status()
            return response.json()
    
    async def store_override(
        self,
        contribution_id: str,
        contributor: str,
        original_decision: str,
        override_decision: str,
        override_reason: str,
        overridden_by: str
    ) -> Dict[str, Any]:
        """Store human override as a correction memory for learning."""
        memory_text = (
            f"OVERRIDE by {overridden_by}: Changed {contributor}'s contribution {contribution_id} "
            f"from '{original_decision}' to '{override_decision}'. "
            f"Reason: {override_reason}"
        )
        
        payload = {
            'text': memory_text,
            'context': f'Contribution review correction - {contribution_id}',
            'metadata': {
                'type': 'override_correction',
                'contribution_id': contribution_id,
                'contributor': contributor,
                'original_decision': original_decision,
                'override_decision': override_decision,
                'override_reason': override_reason,
                'overridden_by': overridden_by,
                'timestamp': datetime.utcnow().isoformat()
            },
            'tags': ['override', 'learning', 'correction']
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f'{self.api_url}/memories',
                headers=self.headers,
                json=payload,
                timeout=10.0
            )
            response.raise_for_status()
            return response.json()
    
    async def search_contributor_history(self, contributor: str) -> List[Dict[str, Any]]:
        """Search for past contributions by this contributor."""
        params = {
            'query': f'contributor:{contributor}',
            'limit': 20
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f'{self.api_url}/memories/search',
                headers=self.headers,
                params=params,
                timeout=10.0
            )
            response.raise_for_status()
            return response.json().get('results', [])
    
    async def learn_from_overrides(self) -> Dict[str, Any]:
        """Query override patterns to improve future decisions."""
        params = {
            'query': 'type:override_correction',
            'limit': 100
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f'{self.api_url}/memories/search',
                headers=self.headers,
                params=params,
                timeout=10.0
            )
            response.raise_for_status()
            results = response.json().get('results', [])
            
            # Analyze patterns
            patterns = {
                'total_overrides': len(results),
                'approve_to_reject': 0,
                'reject_to_approve': 0,
                'review_to_approve': 0,
                'review_to_reject': 0
            }
            
            for result in results:
                metadata = result.get('metadata', {})
                original = metadata.get('original_decision')
                override = metadata.get('override_decision')
                key = f'{original}_to_{override}'
                if key in patterns:
                    patterns[key] += 1
            
            return patterns


# Global client instance
zl_client = ZeroLatencyClient()
