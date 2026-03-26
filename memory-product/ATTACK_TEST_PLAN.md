# 0Latency Security Attack Test Plan

## Objective
Break the API. Find every weakness. Fix it. Repeat until 10/10.

## Test Categories

### 1. Authentication Attacks
- [x] Brute force login (10+ attempts)
- [ ] SQL injection in login email field
- [ ] JWT token manipulation
- [ ] Expired token handling
- [ ] API key enumeration
- [ ] Session fixation

### 2. Rate Limiting Attacks
- [x] Registration spam (5+ per minute)
- [ ] API endpoint flooding (/extract, /recall)
- [ ] Distributed attack simulation (multiple IPs)
- [ ] Rate limit bypass attempts
- [ ] Redis failure scenario

### 3. Injection Attacks
- [ ] SQL injection in search queries
- [ ] NoSQL injection in memory content
- [ ] Command injection in user input
- [ ] XSS in memory content
- [ ] Path traversal

### 4. Data Attacks
- [ ] Memory limit bypass (concurrent writes)
- [ ] Tenant isolation breach attempts
- [ ] Bulk import memory exhaustion
- [ ] Malformed JSON payloads
- [ ] Oversized payloads

### 5. Infrastructure Attacks
- [ ] Database connection exhaustion
- [ ] Redis connection exhaustion
- [ ] Memory exhaustion (large memories)
- [ ] CPU exhaustion (complex queries)
- [ ] Disk space exhaustion (logs)

## Success Criteria
- All attacks either blocked or logged with alerts
- No 500 errors without Telegram alert
- No tenant data leakage
- No service crashes
- All attacks recorded in audit logs
