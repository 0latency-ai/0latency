#!/usr/bin/env python3
"""
Attack Testing Suite for 0Latency API
Tests DDoS, brute force, injection, rate limits, and token manipulation
"""
import requests
import time
import json
from concurrent.futures import ThreadPoolExecutor, as_completed

BASE_URL = "https://api.0latency.ai"
TEST_API_KEY = "zl_live_4g3p1xvln45k1zq2y3c2l4ihcak7foa2"  # test-isolation-b

def test_ddos_protection():
    """Test IP rate limiting under concurrent load"""
    print("\n=== DDoS Protection Test ===")
    
    def make_request(i):
        try:
            resp = requests.get(f"{BASE_URL}/health", timeout=5)
            return i, resp.status_code
        except Exception as e:
            return i, str(e)
    
    # Send 150 requests in parallel (global limit is 100/min per IP)
    with ThreadPoolExecutor(max_workers=50) as executor:
        futures = [executor.submit(make_request, i) for i in range(150)]
        results = [f.result() for f in as_completed(futures)]
    
    status_codes = {}
    for _, code in results:
        status_codes[code] = status_codes.get(code, 0) + 1
    
    print(f"Results: {status_codes}")
    if 429 in status_codes:
        print("✅ Rate limiting triggered (429 responses)")
    else:
        print("⚠️  No rate limiting observed")

def test_brute_force_protection():
    """Test login brute force protection"""
    print("\n=== Brute Force Protection Test ===")
    
    email = f"brute-test-{int(time.time())}@example.com"
    
    for i in range(12):
        resp = requests.post(f"{BASE_URL}/auth/email/login", json={
            "email": email,
            "password": "wrong"
        })
        
        if resp.status_code == 429:
            print(f"✅ Account locked after {i} attempts (expected: 10)")
            return
    
    print("⚠️  Brute force protection did not trigger")

def test_sql_injection():
    """Test SQL injection protection"""
    print("\n=== SQL Injection Test ===")
    
    payloads = [
        "' OR '1'='1",
        "admin'--",
        "' UNION SELECT * FROM users--",
        "'; DROP TABLE users;--"
    ]
    
    for payload in payloads:
        resp = requests.post(f"{BASE_URL}/recall", 
            headers={"X-API-Key": TEST_API_KEY},
            json={"query": payload, "limit": 10}
        )
        
        if resp.status_code == 500:
            print(f"⚠️  SQL injection may have caused error: {payload}")
            return
    
    print("✅ All SQL injection attempts handled safely")

def test_token_manipulation():
    """Test JWT token manipulation"""
    print("\n=== Token Manipulation Test ===")
    
    # Try invalid JWT
    fake_token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyfQ.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"
    
    resp = requests.get(f"{BASE_URL}/auth/me",
        headers={"Authorization": f"Bearer {fake_token}"}
    )
    
    if resp.status_code == 401:
        print("✅ Invalid JWT rejected")
    else:
        print(f"⚠️  Invalid JWT accepted (status: {resp.status_code})")

def test_memory_exhaustion():
    """Test memory limit enforcement"""
    print("\n=== Memory Exhaustion Test ===")
    
    # Try to store 15,000 memories (limit is 10,000 for free tier)
    print("Attempting to exceed 10,000 memory limit...")
    
    # First check current count
    resp = requests.get(f"{BASE_URL}/memories",
        headers={"X-API-Key": TEST_API_KEY}
    )
    
    if resp.status_code == 200:
        current = len(resp.json())
        print(f"Current memories: {current}")
        
        if current >= 10000:
            print("✅ Already at limit - trying to add more...")
            resp = requests.post(f"{BASE_URL}/extract",
                headers={"X-API-Key": TEST_API_KEY},
                json={"text": "This should be rejected"}
            )
            
            if resp.status_code in [400, 403, 429]:
                print(f"✅ Memory limit enforced (status: {resp.status_code})")
            else:
                print(f"⚠️  Memory limit not enforced (status: {resp.status_code})")
        else:
            print(f"⚠️  Account has {current} memories - can't test limit enforcement")

def test_registration_abuse():
    """Test registration rate limiting"""
    print("\n=== Registration Abuse Test ===")
    
    for i in range(7):
        resp = requests.post(f"{BASE_URL}/auth/email/register", json={
            "email": f"abuse-{int(time.time())}-{i}@example.com",
            "password": "TestPassword123!",
            "name": "Test"
        })
        
        if resp.status_code == 429:
            print(f"✅ Registration blocked at attempt {i+1} (limit: 5/min)")
            return
    
    print("⚠️  Registration rate limiting did not trigger")

if __name__ == "__main__":
    print("0Latency API Attack Testing Suite")
    print("=" * 50)
    
    tests = [
        test_registration_abuse,
        test_brute_force_protection,
        test_sql_injection,
        test_token_manipulation,
        test_ddos_protection,
        test_memory_exhaustion,
    ]
    
    for test in tests:
        try:
            test()
        except Exception as e:
            print(f"❌ Test failed with exception: {e}")
        time.sleep(2)  # Cool down between tests
    
    print("\n" + "=" * 50)
    print("Attack testing complete")
