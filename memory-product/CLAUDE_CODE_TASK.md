# Task: Fix Login to Return API Key

## Problem
When users log in via email/password at `/auth/email/login`, the response should include their API key, but it's not being returned.

## Current State
- File: `api/auth.py`
- Login endpoint: `email_login()` function (line ~649)
- Returns `AuthResponse` which has `api_key` field
- Code LOOKS correct but API key is always null/missing in response

## What's Wrong
The backend returns:
```json
{
  "token": "jwt_token_here",
  "user": {...},
  "api_key": null  // <-- This should have the user's actual API key
}
```

## Required Fix
Make `/auth/email/login` endpoint return the user's actual API key from database.

## Files to Check
- `api/auth.py` - login endpoint
- `api/auth.py` - `_USER_SELECT` query (should fetch api_key column)
- `api/auth.py` - `_user_from_row()` function (should include api_key in dict)

## Success Criteria
Test with:
```bash
curl -X POST "https://api.0latency.ai/auth/email/login" \
  -H "Content-Type: application/json" \
  -d '{"email":"justin@pflacademy.co","password":"PASSWORD_HERE"}'
```

Response should include: `"api_key": "zl_live_xxx..."`

## Additional Context
- Database: Supabase PostgreSQL, schema `memory_service.users`
- API runs on port 8420
- Restart with: `pkill -9 python3; cd /root/.openclaw/workspace/memory-product && python3 -m uvicorn api.main:app --host 127.0.0.1 --port 8420 --workers 1 --reload`
