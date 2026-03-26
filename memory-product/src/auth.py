"""
Authentication module for 0Latency API.
Handles signup, login, sessions, email verification.
"""
import secrets
import hashlib
import os
from datetime import datetime, timedelta
from typing import Optional
import psycopg2
import psycopg2.extras


def get_db_conn():
    """Get database connection string from environment."""
    return os.environ.get("MEMORY_DB_CONN", "")


def hash_password(password: str) -> str:
    """Hash a password using SHA-256 (production should use bcrypt)."""
    return hashlib.sha256(password.encode()).hexdigest()


def generate_token(length: int = 64) -> str:
    """Generate a random token."""
    return secrets.token_urlsafe(length)[:length]


def create_user(email: str, password: str) -> dict:
    """
    Create a new user account.
    Returns: {tenant_id, api_key, email}
    """
    conn = psycopg2.connect(get_db_conn())
    
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            # Check if user exists
            cur.execute("""
                SELECT id FROM memory_service.tenants WHERE email = %s
            """, (email.lower().strip(),))
            
            existing = cur.fetchone()
            if existing:
                conn.close()
                raise ValueError("Email already registered")
            
            # Generate API key and hash password
            api_key = f"zl_live_{''.join(secrets.choice('abcdefghijklmnopqrstuvwxyz0123456789') for _ in range(32))}"
            api_hash = hashlib.sha256(api_key.encode()).hexdigest()
            password_hash = hash_password(password)
            
            # Create tenant
            cur.execute("""
                INSERT INTO memory_service.tenants 
                (name, email, api_key_live, api_key_hash, password_hash, plan, active, email_verified)
                VALUES (%s, %s, %s, %s, %s, 'free', true, false)
                RETURNING id, email
            """, (
                email.split('@')[0],
                email.lower().strip(),
                api_key,
                api_hash,
                password_hash
            ))
            
            result = cur.fetchone()
            conn.commit()
            
            return {
                'tenant_id': str(result['id']),
                'api_key': api_key,
                'email': result['email']
            }
    finally:
        conn.close()


def verify_password(email: str, password: str) -> Optional[dict]:
    """
    Verify email + password.
    Returns tenant info if valid, None otherwise.
    """
    conn = psycopg2.connect(get_db_conn())
    
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("""
                SELECT id, email, password_hash, api_key_live, plan, email_verified
                FROM memory_service.tenants
                WHERE email = %s AND active = true
            """, (email.lower().strip(),))
            
            user = cur.fetchone()
            if not user or not user['password_hash']:
                return None
            
            # Verify password
            password_hash = hash_password(password)
            if password_hash != user['password_hash']:
                return None
            
            return dict(user)
    finally:
        conn.close()


def create_session(tenant_id: str, user_agent: str = None, ip_address: str = None) -> str:
    """
    Create a new session for a tenant.
    Returns: session token
    """
    conn = psycopg2.connect(get_db_conn())
    
    try:
        with conn.cursor() as cur:
            token = generate_token(64)
            expires_at = datetime.utcnow() + timedelta(days=30)
            
            cur.execute("""
                INSERT INTO memory_service.sessions 
                (tenant_id, token, expires_at, user_agent, ip_address)
                VALUES (%s, %s, %s, %s, %s)
            """, (tenant_id, token, expires_at, user_agent, ip_address))
            
            conn.commit()
            return token
    finally:
        conn.close()


def verify_session(token: str) -> Optional[dict]:
    """
    Verify a session token.
    Returns tenant info if valid, None otherwise.
    """
    conn = psycopg2.connect(get_db_conn())
    
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("""
                SELECT s.tenant_id, s.expires_at, t.email, t.api_key_live, t.plan, t.email_verified
                FROM memory_service.sessions s
                JOIN memory_service.tenants t ON s.tenant_id = t.id
                WHERE s.token = %s AND t.active = true
            """, (token,))
            
            session = cur.fetchone()
            if not session:
                return None
            
            # Check expiration
            if session['expires_at'] < datetime.utcnow():
                return None
            
            # Update last_used_at
            cur.execute("""
                UPDATE memory_service.sessions
                SET last_used_at = NOW()
                WHERE token = %s
            """, (token,))
            conn.commit()
            
            return dict(session)
    finally:
        conn.close()


def delete_session(token: str):
    """Delete a session (logout)."""
    conn = psycopg2.connect(get_db_conn())
    
    try:
        with conn.cursor() as cur:
            cur.execute("""
                DELETE FROM memory_service.sessions WHERE token = %s
            """, (token,))
            conn.commit()
    finally:
        conn.close()


def create_verification_token(tenant_id: str, token_type: str = 'email_verification') -> str:
    """Create an email verification or password reset token."""
    conn = psycopg2.connect(get_db_conn())
    
    try:
        with conn.cursor() as cur:
            token = generate_token(64)
            expires_at = datetime.utcnow() + timedelta(days=7)
            
            cur.execute("""
                INSERT INTO memory_service.verification_tokens
                (tenant_id, token, type, expires_at)
                VALUES (%s, %s, %s, %s)
            """, (tenant_id, token, token_type, expires_at))
            
            conn.commit()
            return token
    finally:
        conn.close()


def verify_email_token(token: str) -> bool:
    """Verify an email verification token and mark email as verified."""
    conn = psycopg2.connect(get_db_conn())
    
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            # Check token
            cur.execute("""
                SELECT tenant_id, expires_at, used_at
                FROM memory_service.verification_tokens
                WHERE token = %s AND type = 'email_verification'
            """, (token,))
            
            result = cur.fetchone()
            if not result:
                return False
            
            if result['used_at']:
                return False  # Already used
            
            if result['expires_at'] < datetime.utcnow():
                return False  # Expired
            
            # Mark token as used
            cur.execute("""
                UPDATE memory_service.verification_tokens
                SET used_at = NOW()
                WHERE token = %s
            """, (token,))
            
            # Mark email as verified
            cur.execute("""
                UPDATE memory_service.tenants
                SET email_verified = true, verified_at = NOW()
                WHERE id = %s
            """, (result['tenant_id'],))
            
            conn.commit()
            return True
    finally:
        conn.close()
