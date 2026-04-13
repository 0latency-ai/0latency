#!/usr/bin/env python3
"""Admin script to manually override review decisions."""

import sys
import asyncio
from app.config import load_config
from app.database import db
from app.zerolatency_client import zl_client
from app.promo import promo_generator, PromoCodeRequest


async def override_decision(contribution_id: str, new_decision: str, reason: str, admin_user: str):
    """Override a review decision."""
    
    # Load config
    load_config()
    
    # Get existing review
    review = db.get_review_by_contribution_id(contribution_id)
    
    if not review:
        print(f"❌ Review not found: {contribution_id}")
        return
    
    original_decision = review['recommendation']
    
    print(f"📝 Overriding {contribution_id}:")
    print(f"   Original: {original_decision}")
    print(f"   New: {new_decision}")
    print(f"   Reason: {reason}")
    
    # Save override
    db.save_override(
        review_id=review['id'],
        original=original_decision,
        override=new_decision,
        reason=reason,
        overridden_by=admin_user
    )
    
    # Store in 0Latency for learning
    await zl_client.store_override(
        contribution_id=contribution_id,
        contributor=review['contributor'],
        original_decision=original_decision,
        override_decision=new_decision,
        override_reason=reason,
        overridden_by=admin_user
    )
    
    # If overriding to approve, send promo code
    if new_decision == 'approve' and review['contributor_email']:
        print("🎁 Generating promo code...")
        
        try:
            promo_request = PromoCodeRequest(
                tier=review['promo_tier'],
                contributor=review['contributor'],
                contributor_email=review['contributor_email'],
                contribution_id=contribution_id,
                reason=reason
            )
            
            promo_result = await promo_generator.generate_promo_code(promo_request)
            
            # Update database
            db.update_promo_code(review['id'], promo_result.code, promo_result.tier)
            
            print(f"✅ Promo code sent: {promo_result.code}")
            
        except Exception as e:
            print(f"⚠️ Failed to send promo code: {e}")
    
    print("✅ Override complete")


def main():
    """CLI for manual overrides."""
    
    if len(sys.argv) < 5:
        print("Usage: python admin_override.py <contribution_id> <decision> <reason> <admin_user>")
        print("  decision: approve | reject | review")
        print("  Example: python admin_override.py pr-123 approve 'High quality fix' justin")
        sys.exit(1)
    
    contribution_id = sys.argv[1]
    decision = sys.argv[2]
    reason = sys.argv[3]
    admin_user = sys.argv[4]
    
    if decision not in ['approve', 'reject', 'review']:
        print(f"❌ Invalid decision: {decision}")
        print("   Must be: approve, reject, or review")
        sys.exit(1)
    
    asyncio.run(override_decision(contribution_id, decision, reason, admin_user))


if __name__ == '__main__':
    main()
