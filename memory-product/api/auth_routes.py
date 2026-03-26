"""
Auth endpoints for 0Latency API.
"""
from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel
import sys
import os

# Add parent directory to path to import src modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from src import auth

router = APIRouter(prefix="/auth", tags=["auth"])


class SignupRequest(BaseModel):
    email: str
    password: str


class SignupResponse(BaseModel):
    email: str
    tenant_id: str
    message: str


class LoginRequest(BaseModel):
    email: str
    password: str


class LoginResponse(BaseModel):
    email: str
    tenant_id: str
    session_token: str
    api_key: str


class UserResponse(BaseModel):
    email: str
    tenant_id: str
    plan: str
    email_verified: bool
    api_key: str


@router.post("/signup", response_model=SignupResponse)
async def signup(req: SignupRequest):
    """
    Create a new account.
    Returns success message (email verification required before login).
    """
    try:
        result = auth.create_user(req.email, req.password)
        
        # In production, send verification email here
        # For now, auto-verify for testing
        tenant_id = result['tenant_id']
        
        return SignupResponse(
            email=result['email'],
            tenant_id=tenant_id,
            message="Account created. Check your email to verify (or login immediately for testing)."
        )
    except ValueError as e:
        raise HTTPException(400, detail=str(e))
    except Exception as e:
        raise HTTPException(500, detail=f"Signup failed: {str(e)}")


@router.post("/login", response_model=LoginResponse)
async def login(req: LoginRequest, request: Request, response: Response):
    """
    Login with email + password.
    Returns session token and API key.
    """
    user = auth.verify_password(req.email, req.password)
    
    if not user:
        raise HTTPException(401, detail="Invalid email or password")
    
    # Create session
    user_agent = request.headers.get('user-agent')
    ip = request.client.host if request.client else None
    session_token = auth.create_session(str(user['id']), user_agent, ip)
    
    # Set cookie
    response.set_cookie(
        key="zl_session",
        value=session_token,
        max_age=30 * 24 * 60 * 60,  # 30 days
        httponly=True,
        secure=True,
        samesite="lax"
    )
    
    return LoginResponse(
        email=user['email'],
        tenant_id=str(user['id']),
        session_token=session_token,
        api_key=user['api_key_live']
    )


@router.get("/me", response_model=UserResponse)
async def get_current_user(request: Request):
    """
    Get current user info from session.
    Requires session token (cookie or Authorization header).
    """
    # Try cookie first
    session_token = request.cookies.get("zl_session")
    
    # Fallback to Authorization header
    if not session_token:
        auth_header = request.headers.get("authorization", "")
        if auth_header.startswith("Bearer "):
            session_token = auth_header[7:]
    
    if not session_token:
        raise HTTPException(401, detail="Not authenticated")
    
    user = auth.verify_session(session_token)
    if not user:
        raise HTTPException(401, detail="Invalid or expired session")
    
    return UserResponse(
        email=user['email'],
        tenant_id=str(user['tenant_id']),
        plan=user['plan'],
        email_verified=user['email_verified'],
        api_key=user['api_key_live']
    )


@router.post("/logout")
async def logout(request: Request, response: Response):
    """Logout (delete session)."""
    session_token = request.cookies.get("zl_session")
    
    if session_token:
        auth.delete_session(session_token)
    
    response.delete_cookie("zl_session")
    
    return {"message": "Logged out successfully"}


@router.post("/verify-email")
async def verify_email(token: str):
    """Verify email with token from verification email."""
    success = auth.verify_email_token(token)
    
    if not success:
        raise HTTPException(400, detail="Invalid or expired verification token")
    
    return {"message": "Email verified successfully"}
