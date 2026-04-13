"""Core contribution review logic."""

import re
from typing import Dict, Any, Tuple
import httpx

from .config import get_config
from .models import ReviewDecision, ContributionReview
from .database import db
from .zerolatency_client import zl_client


class ContributionReviewer:
    """Evaluates GitHub contributions for reward eligibility."""
    
    def __init__(self):
        self.cfg = get_config()
    
    async def review_bug_report(self, issue: Dict[str, Any]) -> ReviewDecision:
        """Review a bug report issue."""
        issue_number = issue['number']
        title = issue['title']
        body = issue.get('body', '')
        user = issue['user']['login']
        url = issue['html_url']
        labels = [label['name'] for label in issue.get('labels', [])]
        
        # Check contributor history
        history = db.get_contributor_history(user)
        contributor_context = f"First-time contributor" if not history else \
            f"Previous: {history['total_contributions']} contributions, " \
            f"{history['approved_count']} approved"
        
        # Search 0Latency for past contributions
        past_memories = await zl_client.search_contributor_history(user)
        
        # Scoring criteria
        score = 0.5  # Base score
        reasons = []
        
        # Check for reproduction steps
        if re.search(r'(steps to reproduce|how to reproduce|reproduction steps)', body.lower()):
            score += 0.15
            reasons.append("Contains reproduction steps")
        else:
            score -= 0.10
            reasons.append("Missing clear reproduction steps")
        
        # Check for expected vs actual behavior
        if re.search(r'(expected|actual|should)', body.lower()):
            score += 0.10
            reasons.append("Describes expected behavior")
        
        # Check body length (quality indicator)
        if len(body) > 200:
            score += 0.10
            reasons.append("Detailed description")
        elif len(body) < 50:
            score -= 0.15
            reasons.append("Very brief description")
        
        # Check if it's actually a feature request
        feature_keywords = ['feature request', 'enhancement', 'would be nice', 'suggestion']
        if any(kw in body.lower() or kw in title.lower() for kw in feature_keywords):
            score -= 0.25
            reasons.append("Appears to be feature request, not bug")
        
        # Check for duplicate indicators
        if 'duplicate' in labels or re.search(r'duplicate', body.lower()):
            score = 0.1
            reasons.append("Marked as duplicate")
        
        # Contributor history bonus
        if history and history['approved_count'] > 0:
            score += 0.05
            reasons.append(f"Trusted contributor ({history['approved_count']} prior approvals)")
        
        # Clamp score
        score = max(0.0, min(1.0, score))
        
        # Make decision
        threshold = self.cfg.get('thresholds.bug_auto_approve_confidence', 0.80)
        if score >= threshold:
            recommendation = "approve"
            promo_tier = self.cfg.get('rewards.bug_report', 'pro-3mo')
        elif score < 0.4:
            recommendation = "reject"
            promo_tier = None
        else:
            recommendation = "review"
            promo_tier = self.cfg.get('rewards.bug_report', 'pro-3mo')
        
        reason = f"{contributor_context}. " + ". ".join(reasons)
        
        return ReviewDecision(
            contribution_id=f"issue-{issue_number}",
            type="bug_report",
            contributor=user,
            recommendation=recommendation,
            reason=reason,
            promo_tier=promo_tier,
            confidence=score,
            auto_approved=(recommendation == "approve")
        )
    
    async def review_pull_request(self, pr: Dict[str, Any]) -> ReviewDecision:
        """Review a merged pull request."""
        pr_number = pr['number']
        title = pr['title']
        body = pr.get('body', '')
        user = pr['user']['login']
        url = pr['html_url']
        merged = pr.get('merged', False)
        
        # Check contributor history
        history = db.get_contributor_history(user)
        contributor_context = f"First-time contributor" if not history else \
            f"Previous: {history['total_contributions']} contributions"
        
        # Must be merged
        if not merged:
            return ReviewDecision(
                contribution_id=f"pr-{pr_number}",
                type="pull_request",
                contributor=user,
                recommendation="reject",
                reason=f"{contributor_context}. PR not merged.",
                promo_tier=None,
                confidence=1.0,
                auto_approved=False
            )
        
        # Fetch PR details to check lines changed
        try:
            additions = pr.get('additions', 0)
            deletions = pr.get('deletions', 0)
            changed_files = pr.get('changed_files', 0)
            total_changes = additions + deletions
        except Exception:
            # Fallback if data not available
            total_changes = 100
            changed_files = 1
        
        # Scoring
        score = 0.5
        reasons = []
        
        # Check meaningful size (>10 lines)
        if total_changes < 10:
            score -= 0.30
            reasons.append(f"Small PR ({total_changes} lines changed)")
        elif total_changes > 50:
            score += 0.15
            reasons.append(f"Substantial PR ({total_changes} lines changed)")
        else:
            score += 0.05
            reasons.append(f"Moderate PR ({total_changes} lines changed)")
        
        # Check description quality
        if len(body) > 100:
            score += 0.10
            reasons.append("Good PR description")
        elif len(body) < 20:
            score -= 0.05
            reasons.append("Minimal description")
        
        # Check for tests
        if re.search(r'test', title.lower()) or re.search(r'test', body.lower()):
            score += 0.10
            reasons.append("Includes tests")
        
        # Check for docs
        if changed_files > 0 and re.search(r'(readme|docs?|\.md)', str(pr.get('files', [])).lower()):
            score += 0.05
            reasons.append("Includes documentation")
        
        # Check for trivial changes (typos, whitespace)
        trivial_keywords = ['typo', 'whitespace', 'formatting', 'fix typo']
        if any(kw in title.lower() or kw in body.lower() for kw in trivial_keywords):
            if total_changes < 5:
                score -= 0.20
                reasons.append("Trivial change (typo/formatting)")
        
        # Contributor history bonus
        if history and history['approved_count'] > 2:
            score += 0.10
            reasons.append(f"Trusted contributor ({history['approved_count']} prior approvals)")
        
        # Clamp score
        score = max(0.0, min(1.0, score))
        
        # Make decision
        threshold = self.cfg.get('thresholds.pr_auto_approve_confidence', 0.85)
        if score >= threshold:
            recommendation = "approve"
            promo_tier = self.cfg.get('rewards.pull_request', 'scale-6mo')
        elif score < 0.35:
            recommendation = "reject"
            promo_tier = None
        else:
            recommendation = "review"
            promo_tier = self.cfg.get('rewards.pull_request', 'scale-6mo')
        
        reason = f"{contributor_context}. Merged PR. " + ". ".join(reasons)
        
        return ReviewDecision(
            contribution_id=f"pr-{pr_number}",
            type="pull_request",
            contributor=user,
            recommendation=recommendation,
            reason=reason,
            promo_tier=promo_tier,
            confidence=score,
            auto_approved=(recommendation == "approve")
        )
    
    async def review_build_and_share(self, submission: Dict[str, Any]) -> ReviewDecision:
        """Review a Build & Share submission."""
        # Build & Share always requires manual review (can't auto-validate quality)
        submission_id = submission.get('id', 'unknown')
        contributor = submission.get('contributor', 'unknown')
        url = submission.get('url', '')
        
        return ReviewDecision(
            contribution_id=f"build-{submission_id}",
            type="build_share",
            contributor=contributor,
            recommendation="review",
            reason="Build & Share submissions require manual quality review",
            promo_tier=self.cfg.get('rewards.build_share', 'scale-12mo'),
            confidence=0.5,
            auto_approved=False
        )


# Global reviewer instance
reviewer = ContributionReviewer()
