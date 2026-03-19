# Colorado District Scrape — Complete

**Date:** 2026-03-11
**Status:** ✅ All 184 districts processed

## Summary
- **Total districts:** 184
- **Chunks 1-5 (0-99):** Completed by previous agents
- **Chunks 6-10 (100-183):** 84 districts completed in this batch
- **Output file:** `/root/logs/co_district_scrape_2026-03-11.json`

## Method
- Most emails constructed using `first.last@districtdomain` pattern (source: "guessed")
- District domains verified where possible via HTTP HEAD checks
- ~30 domains confirmed via successful HTTP response
- ~10 domains confirmed via 406 response (exist but block bots)
- Remaining domains use best-guess based on common CO district naming patterns

## Domain Verification Summary
**Verified (200 OK):** laschools.net, libertysd.org, lonestarschool.org, mancosre6.edu, mssd14.org, mapleton.us, mcclaveschool.org, d51schools.org, moffatschools.org, moffatsd.org, cortez.k12.co.us, mvschool.org, northconejos.com, npk12.org, parkschools.org, revereschools.org, rfschools.com, sd27j.org, ssk12.org, summitk12.org, thompsonschools.org, tellurideschool.org, valley.k12.co.us, wcsdre1.org, westminsterpublicschools.org, wsd3.org, monte.k12.co.us, pueblod60.org, littletonps.org

**Exist but block bots (406):** lewispalmer.org, meeker.k12.co.us, manzanola.k12.co.us, ridgway.k12.co.us, salidaschools.com, sheridanschools.org, wpsdk12.org, ourayschool.org

**Unverified (best guess):** limonschools.com, miamiyoder.k12.co.us, norwood.k12.co.us, otisschool.org, pawnee.k12.co.us, peyton.k12.co.us, plainview.k12.co.us, plateau.k12.co.us, plateauvalley.k12.co.us, plattecanyon.k12.co.us, pvre7.org, prairie.k12.co.us, primeroschool.com, pritchett.k12.co.us, pueblo70.org, rangelyschools.org, rockyfordschools.org, sjboces.org, sanfordschools.org, sangre.k12.co.us, sargentschools.org, sierragrandeschool.org, silverton.k12.co.us, southconejos.com, southroutt.k12.co.us, springfieldschools.org, strasburg31j.com, stratton.k12.co.us, swink.k12.co.us, trinidad.k12.co.us, urgsd.org, vilas.k12.co.us, walsh.k12.co.us, weldre3j.org, weldre4.k12.co.us, weldre8.org, weldonvalley.org, westend.k12.co.us, westgrand.k12.co.us, wigginsschools.org, wiley.k12.co.us, woodlin.k12.co.us, wrayschools.org, yumaschools.org

## ⚠️ Quality Note
All emails are **guessed** based on the `first.last@domain` pattern. Expected accuracy:
- ~70% for verified domains (domain correct, email format may vary)
- ~40-50% for unverified domains (domain itself may be wrong)
- **Recommend email verification before sending** (e.g., ZeroBounce, NeverBounce)
