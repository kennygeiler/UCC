# New York scale scrape strategy

**Date:** May 2026  
**Portal:** [Cenuity lien search](https://ucc-efiling.dos.ny.gov) (`ucc-efiling.dos.ny.gov`)

## Why NY is not Florida-scale in one run

| Dimension | Florida | New York (this strategy) |
|-----------|---------|---------------------------|
| Index model | REST API browses statewide org index with **empty text** | Portal requires **party + org name + match logic** per search |
| Typical run | ~2,000+ filings (3 index profiles × deep pagination) | Hundreds–low thousands **across many profile\|term sweeps** |
| Secured party | Enrich endpoint on every filing | Grid column when present; search term on SP profile; detail fetch fallback |
| Checkpoints | Per API index profile | Per `profile\|term` page index + prefix queue offset |

**Honest parity note:** Matching Florida’s ~2,451 filings in a **single** NY Playwright run is unlikely without **official bulk/subscription data** (UCC filings subscription / legacy `uccfilings.dos.ny.gov`). This strategy maximizes **public search** coverage via secured-party MCA sweeps and debtor prefix lattice, rotated across scheduled manual runs.

## Search profiles

Configured with `NY_SCRAPE_SEARCH_PROFILES` (comma-separated):

| Profile | Party | Logic | Terms |
|---------|-------|-------|-------|
| `secured_party_org_sw` | Secured party | Starts with (`SW`) | `min(mca_funder count, NY_SCRAPE_MCA_TERM_LIMIT)` aliases (default **200**) + `NY_SCRAPE_SEARCH_TERMS` |
| `debtor_org_sw` | Debtor org | Starts with (`SW`) | Prefix queue (`NY_SCRAPE_PREFIX_TERMS` or A–Z, 0–9, LLC, INC, CORP) rotated via checkpoint |
| `debtor_org_bw` | Debtor org | Begins with (`BW`) | Same prefix queue (optional; enable when portal supports `BW`) |

Checkpoints: `scraper_checkpoints.index_profile` = `{profile}|{term}`, `last_row_number` = last completed page.

Dedupe: in-memory per run by `filing_number` + DB upsert on `(state, filing_number)`.

## Environment variables

```bash
NY_SCRAPE_SEARCH_PROFILES=secured_party_org_sw,debtor_org_sw
NY_SCRAPE_MCA_TERM_LIMIT=200
NY_SCRAPE_PREFIX_TERMS=A,B,C,...,Z,0,1,...,9,LLC,INC,CORP   # optional override
NY_SCRAPE_MAX_PAGES=50
NY_SCRAPE_MAX_TERMS=20          # terms per profile per run (prefix batch size)
NY_SCRAPE_PAGE_CAP_PER_RUN=500  # optional global page budget per run
NY_SCRAPE_FETCH_DETAIL=true     # detail when grid lacks secured_party
NY_SCRAPE_SEARCH_TERMS=          # extra comma-separated terms (all profiles)
```

Shared fallbacks: `PLAYWRIGHT_SCRAPE_*`.

## Operator commands

```bash
# Smoke — secured-party profile only
NY_SCRAPE_MAX_TERMS=3 NY_SCRAPE_MAX_PAGES=2 \
NY_SCRAPE_SEARCH_PROFILES=secured_party_org_sw \
python scripts/run_state_scrape.py --state NY

# Filter one profile from CLI
python scripts/run_state_scrape.py --state NY --profile debtor_org_sw --max-terms 5

# Quality check
psql "$DATABASE_URL" -c "
  SELECT COUNT(*) AS n,
         ROUND(100.0 * COUNT(secured_party) / NULLIF(COUNT(*),0), 1) AS pct_secured,
         ROUND(100.0 * COUNT(filing_date) / NULLIF(COUNT(*),0), 1) AS pct_dated
  FROM ucc_filings WHERE state = 'NY';
"
```

## Expected volume (order of magnitude)

- **Secured-party MCA sweep:** up to `min(alias count, NY_SCRAPE_MCA_TERM_LIMIT)` terms (default cap **200** after deBanked import) × up to `NY_SCRAPE_MAX_PAGES` pages each — primary path to MCA-relevant filings.
- **Debtor prefix sweep:** 39 default prefixes × pages — broad debtor discovery; rotate prefixes across runs with `max_terms`.
- **Multi-day:** Run daily with checkpoints; prefix cursor advances automatically.

## NJ / CA / TX

- `NJ_SCRAPE_SEARCH_PROFILES` is wired in settings for future secured-party mode; NJ still uses legacy `search` checkpoint profile until portal recon adds SP search.
- CA/TX unchanged; NY work does not alter Florida REST scraper.

## deBanked alias import

Import the public MCA UCC alias table before large secured-party runs:

```bash
python -m scripts.import_debanked_mca_aliases
```

See [ny-volume-playbook.md](ny-volume-playbook.md) for operator steps.

## Related docs

- [ny-volume-playbook.md](ny-volume-playbook.md)
- [playwright-tier1-scrape-strategy.md](playwright-tier1-scrape-strategy.md)
- [README.md](../README.md) — Tier 1 manual scrape section
