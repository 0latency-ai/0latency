"""Mission Control integration for TODO management."""

import httpx
from typing import Dict, Any, Optional

from .config import get_config
from .models import MissionControlTask


class MissionControlClient:
    """Client for Mission Control TODO API."""
    
    def __init__(self):
        cfg = get_config()
        self.api_url = cfg.get('mission_control.api_url')
        self.api_key = cfg.get('mission_control.api_key')
        self.headers = {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json'
        }
    
    async def create_review_task(
        self,
        contribution_id: str,
        contributor: str,
        github_url: str,
        recommendation: str,
        reason: str,
        confidence: float,
        contribution_type: str
    ) -> Optional[str]:
        """Create a TODO item in Mission Control for manual review."""
        
        # Format confidence as percentage
        confidence_pct = f"{confidence:.0%}"
        
        # Build description with all context
        description = f"""
**Contributor:** {contributor}
**Type:** {contribution_type.replace('_', ' ').title()}
**URL:** {github_url}

**Agent Analysis:**
{reason}

**Agent Recommendation:** {recommendation.upper()}
**Confidence:** {confidence_pct}

**Action Required:**
Review the contribution and decide whether to approve or reject the reward claim.
        """.strip()
        
        # Priority based on recommendation and confidence
        if recommendation == 'approve' and confidence >= 0.85:
            priority = 'low'  # High confidence auto-approve, just FYI
        elif recommendation == 'reject':
            priority = 'medium'  # Review rejection before finalizing
        else:
            priority = 'high'  # Uncertain, needs attention
        
        task = MissionControlTask(
            title=f"🔍 Review {contribution_type.replace('_', ' ').title()}: {contributor}",
            description=description,
            priority=priority,
            url=github_url,
            metadata={
                'contribution_id': contribution_id,
                'contributor': contributor,
                'recommendation': recommendation,
                'confidence': confidence,
                'type': 'contribution_review'
            }
        )
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f'{self.api_url}/todos',
                    headers=self.headers,
                    json=task.dict(),
                    timeout=10.0
                )
                response.raise_for_status()
                result = response.json()
                return result.get('id')
        except Exception as e:
            print(f"Failed to create Mission Control task: {e}")
            return None
    
    async def update_task_status(self, todo_id: str, status: str, resolution: Optional[str] = None) -> bool:
        """Update TODO item status."""
        try:
            payload = {'status': status}
            if resolution:
                payload['resolution'] = resolution
            
            async with httpx.AsyncClient() as client:
                response = await client.patch(
                    f'{self.api_url}/todos/{todo_id}',
                    headers=self.headers,
                    json=payload,
                    timeout=10.0
                )
                response.raise_for_status()
                return True
        except Exception as e:
            print(f"Failed to update Mission Control task: {e}")
            return False


# Global mission control client
mc_client = MissionControlClient()
