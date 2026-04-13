"""Database operations for contribution reviews."""

import psycopg2
import psycopg2.extras
from typing import Optional, List, Dict, Any
from datetime import datetime
from contextlib import contextmanager

from .config import get_config
from .models import ContributionReview


class Database:
    """PostgreSQL database interface."""
    
    def __init__(self):
        self.connection_params = None
    
    def _ensure_config(self):
        """Lazy-load database configuration."""
        if self.connection_params is None:
            cfg = get_config()
            self.connection_params = {
                'host': cfg.get('database.host'),
                'port': cfg.get('database.port'),
                'dbname': cfg.get('database.name'),
                'user': cfg.get('database.user'),
                'password': cfg.get('database.password')
            }
    
    @contextmanager
    def get_connection(self):
        """Get database connection context manager."""
        self._ensure_config()
        conn = psycopg2.connect(**self.connection_params)
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
    
    def save_review(self, review: ContributionReview) -> int:
        """Save contribution review to database."""
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO contribution_reviews 
                    (contribution_id, type, contributor, contributor_email, github_url, 
                     recommendation, reason, confidence, promo_tier, webhook_payload)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (contribution_id) 
                    DO UPDATE SET 
                        recommendation = EXCLUDED.recommendation,
                        reason = EXCLUDED.reason,
                        confidence = EXCLUDED.confidence,
                        updated_at = NOW()
                    RETURNING id
                """, (
                    review.contribution_id,
                    review.type,
                    review.contributor,
                    review.contributor_email,
                    review.github_url,
                    review.recommendation,
                    review.reason,
                    review.confidence,
                    review.promo_tier,
                    psycopg2.extras.Json(review.webhook_payload) if review.webhook_payload else None
                ))
                review_id = cur.fetchone()[0]
                
                # Update contributor stats
                self._update_contributor_stats(cur, review.contributor, review.recommendation)
                
                return review_id
    
    def _update_contributor_stats(self, cur, contributor: str, recommendation: str):
        """Update contributor statistics."""
        cur.execute("""
            INSERT INTO contributor_stats (contributor, total_contributions, first_contribution_at, last_contribution_at)
            VALUES (%s, 1, NOW(), NOW())
            ON CONFLICT (contributor) 
            DO UPDATE SET
                total_contributions = contributor_stats.total_contributions + 1,
                last_contribution_at = NOW(),
                updated_at = NOW()
        """, (contributor,))
        
        # Update counters based on recommendation
        if recommendation == 'approve':
            cur.execute("""
                UPDATE contributor_stats 
                SET approved_count = approved_count + 1 
                WHERE contributor = %s
            """, (contributor,))
        elif recommendation == 'reject':
            cur.execute("""
                UPDATE contributor_stats 
                SET rejected_count = rejected_count + 1 
                WHERE contributor = %s
            """, (contributor,))
        elif recommendation == 'review':
            cur.execute("""
                UPDATE contributor_stats 
                SET manual_review_count = manual_review_count + 1 
                WHERE contributor = %s
            """, (contributor,))
    
    def get_contributor_history(self, contributor: str) -> Optional[Dict[str, Any]]:
        """Get contributor's historical stats."""
        with self.get_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute("""
                    SELECT * FROM contributor_stats WHERE contributor = %s
                """, (contributor,))
                result = cur.fetchone()
                return dict(result) if result else None
    
    def get_review_by_contribution_id(self, contribution_id: str) -> Optional[Dict[str, Any]]:
        """Get review by contribution ID."""
        with self.get_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute("""
                    SELECT * FROM contribution_reviews WHERE contribution_id = %s
                """, (contribution_id,))
                result = cur.fetchone()
                return dict(result) if result else None
    
    def update_promo_code(self, review_id: int, promo_code: str, promo_tier: str):
        """Update review with promo code information."""
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE contribution_reviews 
                    SET promo_code = %s, promo_tier = %s, promo_sent_at = NOW()
                    WHERE id = %s
                """, (promo_code, promo_tier, review_id))
                
                # Update contributor stats
                cur.execute("""
                    UPDATE contributor_stats 
                    SET total_rewards_sent = total_rewards_sent + 1 
                    WHERE contributor = (
                        SELECT contributor FROM contribution_reviews WHERE id = %s
                    )
                """, (review_id,))
    
    def save_override(self, review_id: int, original: str, override: str, reason: str, overridden_by: str):
        """Save human override for learning."""
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO review_overrides 
                    (review_id, original_recommendation, override_recommendation, override_reason, overridden_by)
                    VALUES (%s, %s, %s, %s, %s)
                """, (review_id, original, override, reason, overridden_by))
                
                # Update the review itself
                cur.execute("""
                    UPDATE contribution_reviews 
                    SET human_override = %s, override_reason = %s
                    WHERE id = %s
                """, (override, reason, review_id))
    
    def save_mission_control_todo(self, review_id: int, todo_id: str):
        """Save Mission Control TODO reference."""
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO mission_control_todos (review_id, todo_id)
                    VALUES (%s, %s)
                """, (review_id, todo_id))
    
    def get_pending_reviews(self) -> List[Dict[str, Any]]:
        """Get all reviews pending manual review."""
        with self.get_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute("""
                    SELECT * FROM contribution_reviews 
                    WHERE recommendation = 'review' 
                    AND human_override IS NULL
                    ORDER BY created_at DESC
                """)
                return [dict(row) for row in cur.fetchall()]


# Global database instance
db = Database()
