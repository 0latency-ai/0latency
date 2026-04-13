"""FastAPI webhook endpoint for GitHub contribution reviews."""

import hmac
import hashlib
from typing import Dict, Any
from fastapi import FastAPI, Request, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse

from .config import load_config, get_config
from .models import GitHubWebhookPayload, ContributionReview
from .reviewer import reviewer
from .database import db
from .zerolatency_client import zl_client
from .promo import promo_generator, PromoCodeRequest
from .mission_control import mc_client


# Initialize app
app = FastAPI(title="0Latency Contribution Reviewer", version="1.0.0")


@app.on_event("startup")
async def startup_event():
    """Load configuration on startup."""
    load_config()


def verify_github_signature(payload: bytes, signature: str) -> bool:
    """Verify GitHub webhook signature."""
    cfg = get_config()
    secret = cfg.get('github.webhook_secret')
    
    if not secret:
        # If no secret configured, skip verification (dev mode)
        return True
    
    expected_signature = 'sha256=' + hmac.new(
        secret.encode(),
        payload,
        hashlib.sha256
    ).hexdigest()
    
    return hmac.compare_digest(expected_signature, signature)


async def process_review_decision(decision: Dict[str, Any], github_payload: Dict[str, Any]):
    """Process review decision: store to DB, 0Latency, handle approvals."""
    
    # Get contributor email from GitHub payload
    contributor_email = None
    if 'issue' in github_payload:
        contributor_email = github_payload['issue']['user'].get('email')
    elif 'pull_request' in github_payload:
        contributor_email = github_payload['pull_request']['user'].get('email')
    
    # Create review record
    review = ContributionReview(
        contribution_id=decision['contribution_id'],
        type=decision['type'],
        contributor=decision['contributor'],
        contributor_email=contributor_email,
        github_url=github_payload.get('html_url', ''),
        recommendation=decision['recommendation'],
        reason=decision['reason'],
        confidence=decision['confidence'],
        promo_tier=decision.get('promo_tier'),
        webhook_payload=github_payload
    )
    
    # Save to database
    review_id = db.save_review(review)
    
    # Store in 0Latency memory
    await zl_client.store_review_decision(
        contribution_id=decision['contribution_id'],
        contributor=decision['contributor'],
        decision=decision,
        context=f"GitHub {decision['type']} review"
    )
    
    # Handle based on recommendation
    if decision['recommendation'] == 'approve' and decision['auto_approved']:
        # Auto-approve: generate and send promo code
        if contributor_email and decision.get('promo_tier'):
            try:
                promo_request = PromoCodeRequest(
                    tier=decision['promo_tier'],
                    contributor=decision['contributor'],
                    contributor_email=contributor_email,
                    contribution_id=decision['contribution_id'],
                    reason=decision['reason']
                )
                
                promo_result = await promo_generator.generate_promo_code(promo_request)
                
                # Update database with promo code
                db.update_promo_code(review_id, promo_result.code, promo_result.tier)
                
                print(f"✅ Auto-approved and sent promo code to {decision['contributor']}")
                
            except Exception as e:
                print(f"⚠️ Failed to generate/send promo code: {e}")
                # Fall through to manual review
                await _create_manual_review_task(decision, github_payload, review_id)
        else:
            print(f"⚠️ Missing email for {decision['contributor']}, creating manual review task")
            await _create_manual_review_task(decision, github_payload, review_id)
    
    elif decision['recommendation'] == 'review':
        # Manual review needed
        await _create_manual_review_task(decision, github_payload, review_id)
    
    elif decision['recommendation'] == 'reject':
        # Rejection - no promo code, but log for transparency
        print(f"❌ Rejected contribution from {decision['contributor']}: {decision['reason']}")


async def _create_manual_review_task(decision: Dict[str, Any], github_payload: Dict[str, Any], review_id: int):
    """Create Mission Control TODO for manual review."""
    github_url = github_payload.get('html_url', '')
    if 'issue' in github_payload:
        github_url = github_payload['issue']['html_url']
    elif 'pull_request' in github_payload:
        github_url = github_payload['pull_request']['html_url']
    
    todo_id = await mc_client.create_review_task(
        contribution_id=decision['contribution_id'],
        contributor=decision['contributor'],
        github_url=github_url,
        recommendation=decision['recommendation'],
        reason=decision['reason'],
        confidence=decision['confidence'],
        contribution_type=decision['type']
    )
    
    if todo_id:
        db.save_mission_control_todo(review_id, todo_id)
        print(f"📋 Created Mission Control task for {decision['contributor']}")


@app.post("/contribution-review")
async def webhook_handler(request: Request, background_tasks: BackgroundTasks):
    """Handle GitHub webhook events."""
    
    # Get raw body for signature verification
    body = await request.body()
    signature = request.headers.get('X-Hub-Signature-256', '')
    
    # Verify signature
    if not verify_github_signature(body, signature):
        raise HTTPException(status_code=401, detail="Invalid signature")
    
    # Parse payload
    try:
        payload = await request.json()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid JSON: {e}")
    
    event_type = request.headers.get('X-GitHub-Event')
    action = payload.get('action')
    
    print(f"📥 Received webhook: {event_type} - {action}")
    
    # Route to appropriate handler
    decision = None
    
    if event_type == 'issues' and action == 'labeled':
        # Check if bug report label was added
        labels = [label['name'] for label in payload.get('issue', {}).get('labels', [])]
        if 'bug' in labels or 'bug report' in labels:
            decision = await reviewer.review_bug_report(payload['issue'])
    
    elif event_type == 'pull_request' and action == 'closed':
        # Check if PR was merged
        pr = payload.get('pull_request', {})
        if pr.get('merged'):
            decision = await reviewer.review_pull_request(pr)
    
    elif event_type == 'ping':
        return JSONResponse(content={'status': 'pong'})
    
    else:
        # Ignore other events
        return JSONResponse(content={'status': 'ignored', 'event': event_type, 'action': action})
    
    # Process decision in background
    if decision:
        background_tasks.add_task(
            process_review_decision, 
            decision.dict(), 
            payload
        )
        
        return JSONResponse(content={
            'status': 'processing',
            'contribution_id': decision.contribution_id,
            'recommendation': decision.recommendation,
            'confidence': decision.confidence
        })
    
    return JSONResponse(content={'status': 'no_action'})


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {'status': 'healthy', 'service': 'contribution-reviewer'}


@app.get("/stats")
async def get_stats():
    """Get review statistics."""
    try:
        pending_reviews = db.get_pending_reviews()
        return {
            'pending_reviews': len(pending_reviews),
            'status': 'operational'
        }
    except Exception as e:
        return {
            'error': str(e),
            'status': 'error'
        }


if __name__ == '__main__':
    import uvicorn
    cfg = get_config()
    uvicorn.run(
        app,
        host=cfg.get('server.host', '0.0.0.0'),
        port=cfg.get('server.port', 8765)
    )
