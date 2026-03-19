# Sheila HubSpot Import Summary

**Date:** 2026-03-12 01:03 UTC  
**Operator:** Reed (subagent)  

## HubSpot Pull

| Metric | Count |
|--------|-------|
| Total contacts pulled | 6,215 |
| Contacts with email | 6,178 |
| Contacts without email (skipped) | 37 |

## Supabase Insert

| Metric | Count |
|--------|-------|
| **Inserted into thomas.contacts** | **6,157** |
| Skipped — PFL Academy protected | 21 |
| Skipped — no email | 37 |
| Errors | 0 |

## Breakdown by Relationship Type (SS contacts)

| Type | Count |
|------|-------|
| prospect | 5,582 |
| warm_lead | 347 |
| customer | 228 |

## Tagging

All inserted contacts have:
- `business = 'startup_smartup'`
- `source = 'hubspot'`
- `tags = ['sheila']`
- `hubspot_id` set from HubSpot contact ID

## Relationship Type Mapping

- HubSpot `lifecyclestage = customer` → `customer`
- HubSpot `lifecyclestage` in (opportunity, salesqualifiedlead, marketingqualifiedlead) OR `hs_lead_status` in (OPEN, IN_PROGRESS, OPEN_DEAL) → `warm_lead`
- Everything else → `prospect`

## PFL Protection

21 HubSpot contacts had emails matching existing PFL Academy contacts. These were **skipped** — PFL data was not touched.

## Total thomas.contacts After Import

| Business | Source | Count |
|----------|--------|-------|
| pfl_academy | (Scout) | 2,332 |
| startup_smartup | hubspot | 6,157 |
| **Total** | | **8,489** |

## Files

- Raw HubSpot data: `/root/logs/hubspot_contacts_raw.json`
- Import log: `/root/logs/sheila_hubspot_import_2026-03-12.log`
- Import stats: `/root/logs/hubspot_import_stats.json`

## Next Steps

- Thomas will run ZeroBounce verification + dedup separately
- Sheila can now query `thomas.contacts WHERE business = 'startup_smartup'` for outreach
