#!/usr/bin/env python3
"""ZeroBounce email verification for education contacts."""

import json
import time
import sys
import urllib.request
import urllib.error
import os

API_KEY = "27d1697ee7274de7addb6af1cbb1d97c"
VALIDATE_URL = "https://api.zerobounce.net/v2/validate"
CREDITS_URL = f"https://api.zerobounce.net/v2/getcredits?api_key={API_KEY}"
INPUT_FILE = "/root/.openclaw/workspace/research/contact-scrub/education_only.json"
OUTPUT_DIR = "/root/.openclaw/workspace/research/zerobounce-results"
CHECKPOINT_FILE = os.path.join(OUTPUT_DIR, "checkpoint.json")

RATE_LIMIT = 5  # requests per second
DELAY = 1.0 / RATE_LIMIT

def get_credits():
    resp = urllib.request.urlopen(CREDITS_URL)
    return int(json.loads(resp.read())["Credits"])

def validate_email(email):
    url = f"{VALIDATE_URL}?api_key={API_KEY}&email={urllib.parse.quote(email)}&ip_address="
    for attempt in range(3):
        try:
            resp = urllib.request.urlopen(url, timeout=15)
            return json.loads(resp.read())
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as e:
            if attempt < 2:
                wait = (attempt + 1) * 5
                print(f"  Error on {email}: {e}. Retrying in {wait}s...")
                time.sleep(wait)
            else:
                print(f"  FAILED after 3 attempts: {email}: {e}")
                return {"status": "unknown", "sub_status": f"api_error: {e}", "did_you_mean": ""}

import urllib.parse
sys.path.insert(0, '/root/scripts')
from contact_quality_filter import filter_contacts

def main():
    with open(INPUT_FILE) as f:
        contacts = json.load(f)

    print(f"Loaded {len(contacts)} contacts")

    # MANDATORY: Vision test before ZB (added March 12, 2026)
    # Filters out generic emails, non-edu domains, construction workers, etc.
    contacts, trash = filter_contacts(contacts)
    if trash:
        trash_file = os.path.join(OUTPUT_DIR, "pre_zb_rejected.json")
        with open(trash_file, 'w') as f:
            json.dump(trash, f, indent=2)
        print(f"Vision test: {len(trash)} rejected (saved to {trash_file})")
    print(f"Vision test: {len(contacts)} passed, proceeding to ZeroBounce")

    # Filter out empty emails
    with_email = [c for c in contacts if c.get("email", "").strip()]
    no_email = [c for c in contacts if not c.get("email", "").strip()]
    print(f"Contacts with email: {len(with_email)}, without email (skipped): {len(no_email)}")

    # MANDATORY: Master registry dedup (added March 12, 2026)
    # Cross-reference against master registry to avoid wasting ZB credits
    MASTER_REGISTRY = "/root/.openclaw/workspace/research/zerobounce-master-registry.json"
    if os.path.exists(MASTER_REGISTRY):
        with open(MASTER_REGISTRY) as f:
            registry = json.load(f)
        already_checked = []
        need_checking = []
        for c in with_email:
            email = c["email"].strip().lower()
            if email in registry:
                c["zerobounce_status"] = registry[email]
                already_checked.append(c)
            else:
                need_checking.append(c)
        print(f"Registry dedup: {len(already_checked)} already verified (skipped), {len(need_checking)} new")
        if already_checked:
            # Save the already-known results
            dedup_file = os.path.join(OUTPUT_DIR, "already_verified.json")
            with open(dedup_file, 'w') as f:
                json.dump(already_checked, f, indent=2)
        with_email = need_checking
        if not with_email:
            print("All contacts already verified. Nothing to do.")
            return
    else:
        print("WARNING: No master registry found. All contacts will be sent to ZeroBounce.")

    # Check for checkpoint (resume support)
    results = []
    start_idx = 0
    if os.path.exists(CHECKPOINT_FILE):
        with open(CHECKPOINT_FILE) as f:
            cp = json.load(f)
        results = cp.get("results", [])
        start_idx = cp.get("next_idx", 0)
        print(f"Resuming from checkpoint at index {start_idx} ({len(results)} already done)")

    initial_credits = get_credits()
    print(f"Credits available: {initial_credits}")

    if initial_credits < 50:
        print("ERROR: Less than 50 credits remaining. Aborting.")
        sys.exit(1)

    total = len(with_email)
    for i in range(start_idx, total):
        contact = with_email[i]
        email = contact["email"].strip()

        # Credit check every 100
        if i > 0 and i % 100 == 0:
            credits = get_credits()
            print(f"--- Progress: {i}/{total} verified | Credits remaining: {credits} ---")
            if credits < 50:
                print(f"STOPPING: Only {credits} credits left. Saving checkpoint.")
                with open(CHECKPOINT_FILE, "w") as f:
                    json.dump({"results": results, "next_idx": i}, f)
                break

        resp = validate_email(email)
        
        result = {
            "email": email,
            "name": contact.get("name", ""),
            "organization": contact.get("organization", ""),
            "title": contact.get("title", ""),
            "state": contact.get("state", ""),
            "zerobounce_status": resp.get("status", "unknown"),
            "zerobounce_sub_status": resp.get("sub_status", ""),
            "did_you_mean": resp.get("did_you_mean", ""),
        }
        results.append(result)

        time.sleep(DELAY)

        # Checkpoint every 200
        if (i + 1) % 200 == 0:
            with open(CHECKPOINT_FILE, "w") as f:
                json.dump({"results": results, "next_idx": i + 1}, f)

    # Final credit check
    final_credits = get_credits()
    credits_used = initial_credits - final_credits
    print(f"\nDone! Verified {len(results)} emails. Credits used: {credits_used}. Remaining: {final_credits}")

    # Write results
    with open(os.path.join(OUTPUT_DIR, "results.json"), "w") as f:
        json.dump(results, f, indent=2)

    # Categorize
    safe = [r for r in results if r["zerobounce_status"] in ("valid", "catch-all")]
    do_not = [r for r in results if r["zerobounce_status"] in ("invalid", "spamtrap", "abuse", "do_not_mail")]
    unknown = [r for r in results if r["zerobounce_status"] == "unknown"]

    with open(os.path.join(OUTPUT_DIR, "safe_to_send.json"), "w") as f:
        json.dump(safe, f, indent=2)

    with open(os.path.join(OUTPUT_DIR, "do_not_send.json"), "w") as f:
        json.dump(do_not, f, indent=2)

    # Stats
    status_counts = {}
    state_breakdown = {}
    for r in results:
        s = r["zerobounce_status"]
        status_counts[s] = status_counts.get(s, 0) + 1
        
        st = r["state"]
        if st not in state_breakdown:
            state_breakdown[st] = {}
        state_breakdown[st][s] = state_breakdown[st].get(s, 0) + 1

    # Write findings.md
    with open(os.path.join(OUTPUT_DIR, "findings.md"), "w") as f:
        f.write("# ZeroBounce Email Verification Results\n\n")
        f.write(f"**Date:** 2026-03-11\n")
        f.write(f"**Total contacts in file:** {len(contacts)}\n")
        f.write(f"**Contacts with email:** {len(with_email)}\n")
        f.write(f"**Contacts without email (skipped):** {len(no_email)}\n")
        f.write(f"**Emails verified:** {len(results)}\n")
        f.write(f"**Credits used:** {credits_used}\n")
        f.write(f"**Credits remaining:** {final_credits}\n\n")

        f.write("## Summary by Status\n\n")
        f.write("| Status | Count | % |\n")
        f.write("|--------|-------|---|\n")
        for status in ["valid", "catch-all", "invalid", "unknown", "spamtrap", "abuse", "do_not_mail"]:
            count = status_counts.get(status, 0)
            pct = (count / len(results) * 100) if results else 0
            f.write(f"| {status} | {count} | {pct:.1f}% |\n")
        f.write(f"| **TOTAL** | **{len(results)}** | **100%** |\n\n")

        f.write(f"## Safe to Send: {len(safe)} contacts\n")
        f.write(f"- Valid: {status_counts.get('valid', 0)}\n")
        f.write(f"- Catch-all: {status_counts.get('catch-all', 0)}\n\n")

        f.write(f"## Do Not Send: {len(do_not)} contacts\n")
        f.write(f"- Invalid: {status_counts.get('invalid', 0)}\n")
        f.write(f"- Spamtrap: {status_counts.get('spamtrap', 0)}\n")
        f.write(f"- Abuse: {status_counts.get('abuse', 0)}\n")
        f.write(f"- Do Not Mail: {status_counts.get('do_not_mail', 0)}\n\n")

        f.write(f"## Unknown/Risky: {status_counts.get('unknown', 0)} contacts\n\n")

        f.write("## Per-State Breakdown\n\n")
        f.write("| State | Valid | Catch-All | Invalid | Unknown | Spamtrap | Abuse | Do Not Mail | Total |\n")
        f.write("|-------|-------|-----------|---------|---------|----------|-------|-------------|-------|\n")
        for state in sorted(state_breakdown.keys()):
            sb = state_breakdown[state]
            total_st = sum(sb.values())
            f.write(f"| {state} | {sb.get('valid',0)} | {sb.get('catch-all',0)} | {sb.get('invalid',0)} | {sb.get('unknown',0)} | {sb.get('spamtrap',0)} | {sb.get('abuse',0)} | {sb.get('do_not_mail',0)} | {total_st} |\n")
        f.write("\n")

        f.write("## Do Not Send List\n\n")
        f.write("These emails should be removed from all outreach lists:\n\n")
        for r in do_not:
            f.write(f"- **{r['email']}** ({r['name']}, {r['organization']}) — Status: {r['zerobounce_status']}, Sub: {r['zerobounce_sub_status']}\n")
        f.write("\n")

        f.write("## Recommendations\n\n")
        valid_pct = (status_counts.get('valid', 0) / len(results) * 100) if results else 0
        safe_pct = (len(safe) / len(results) * 100) if results else 0
        f.write(f"1. **Safe to send ({len(safe)} contacts, {safe_pct:.1f}%):** Use `safe_to_send.json` for outreach.\n")
        f.write(f"2. **Remove {len(do_not)} contacts** from all lists — these will hard bounce or worse.\n")
        f.write(f"3. **Unknown ({status_counts.get('unknown', 0)}):** Consider excluding from initial sends; retry verification later.\n")
        f.write(f"4. **Catch-all domains** accept any email — delivery works but engagement may be lower.\n")
        f.write(f"5. **{len(no_email)} contacts had no email** — consider enrichment or manual lookup.\n")

    # Clean up checkpoint
    if os.path.exists(CHECKPOINT_FILE):
        os.remove(CHECKPOINT_FILE)

    print(f"\nFiles written:")
    print(f"  results.json: {len(results)} entries")
    print(f"  safe_to_send.json: {len(safe)} entries")  
    print(f"  do_not_send.json: {len(do_not)} entries")
    print(f"  findings.md: summary report")

if __name__ == "__main__":
    main()
