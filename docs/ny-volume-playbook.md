# New York volume playbook

Operator steps to maximize NY UCC filing volume after importing the deBanked MCA alias list.

## 1. Import deBanked aliases

```bash
# Bundled CSV (recommended — reproducible)
python -m scripts.import_debanked_mca_aliases

# Live fetch from debanked.com
python -m scripts.import_debanked_mca_aliases --live

# Dashboard: MCA Lenders → Import deBanked list
```

Verify:

```sql
SELECT COUNT(*) FROM mca_aliases WHERE source = 'debanked';
SELECT COUNT(*) FROM mca_aliases WHERE source = 'debanked' AND lender_class = 'mca_funder';
```

Expect roughly **100+** `mca_funder` aliases and a handful of `registered_agent` rows (CSC / CT Corporation variants). First Data and Lending Club are **not** imported.

## 2. Configure NY secured-party sweep

In `.env` (see `.env.example`):

```bash
NY_SCRAPE_SEARCH_PROFILES=secured_party_org_sw,debtor_org_sw
NY_SCRAPE_MCA_TERM_LIMIT=200          # min(alias count, 200) for secured_party
NY_SCRAPE_MAX_TERMS=20                # debtor prefix batch size only
NY_SCRAPE_MAX_PAGES=50
NY_SCRAPE_FETCH_DETAIL=true
# NY_SCRAPE_PAGE_CAP_PER_RUN=500      # optional daily page budget
# NY_SCRAPE_PAGE_ORDER=forward        # forward | reverse | recent_only
# NY_SCRAPE_RECENT_PAGES=10           # last K pages when recent_only
```

**Profile order:** `secured_party_org_sw` runs first (MCA aliases from DB), then `debtor_org_sw` (prefix queue).

**Variant secured-party terms:** `NY_SCRAPE_MCA_TERM_LIMIT` caps **funders** (canonical lenders), not raw alias rows. Each funder expands to multiple portal queries: every distinct `mca_aliases` name for that lender, plus a **first significant token** (e.g. `YELLOWSTONE` from `YELLOWSTONE CAPITAL LLC`). Optional `NY_SCRAPE_VARIANT_LIMIT` caps variants per funder. Add `secured_party_org_bw` to profiles for **begins with** (`BW`) in addition to **starts with** (`SW`). Checkpoints use `{profile}|{term}` so variants do not collide.

**Pagination order:** `NY_SCRAPE_PAGE_ORDER` controls grid direction per term:

| Value | Behavior |
|-------|----------|
| `forward` | Page 1 → N (default; checkpoint = last forward page) |
| `reverse` | Last page → first until `NY_SCRAPE_MAX_PAGES` budget |
| `recent_only` | Last `NY_SCRAPE_RECENT_PAGES` pages only (default 10) |

Reverse/recent checkpoints store **pages scraped from the end** (resume jumps to `last - completed`).

## 3. Run secured-party full scrape

```bash
# Full MCA secured-party sweep (funders × variants; SW + optional BW)
NY_SCRAPE_SEARCH_PROFILES=secured_party_org_sw,secured_party_org_bw \
python scripts/run_state_scrape.py --state NY

# SW only (default profile list omits BW unless you add it)
NY_SCRAPE_SEARCH_PROFILES=secured_party_org_sw \
python scripts/run_state_scrape.py --state NY

# Smoke — 3 MCA terms, 2 pages
NY_SCRAPE_SEARCH_PROFILES=secured_party_org_sw \
NY_SCRAPE_MCA_TERM_LIMIT=3 NY_SCRAPE_MAX_PAGES=2 \
python scripts/run_state_scrape.py --state NY --quick

# Daily incremental — newest filings only (last 10 pages per term)
NY_SCRAPE_PAGE_ORDER=recent_only NY_SCRAPE_RECENT_PAGES=10 \
NY_SCRAPE_SEARCH_PROFILES=secured_party_org_sw \
python scripts/run_state_scrape.py --state NY
```

Logs include per-term `pager_total`, `page_order`, `pages_fetched`, `filing_date_min`/`max`, `rows_parsed`, and `inserts` (new unique filings).

## 4. Multi-day checkpoint strategy

| Checkpoint | Key | Purpose |
|------------|-----|---------|
| Page index | `{profile}\|{term}` | Forward: last completed page 1→N. Reverse/recent: pages scraped from end |
| Prefix offset | `debtor_org_sw` | Rotate A–Z / 0–9 / LLC prefix batch |

Run daily:

1. **Day 1–N:** `secured_party_org_sw` — one run can cover up to 200 MCA terms × `NY_SCRAPE_MAX_PAGES` pages each (subject to `NY_SCRAPE_PAGE_CAP_PER_RUN`).
2. **Rotate debtor prefixes:** `debtor_org_sw` with `NY_SCRAPE_MAX_TERMS=20` advances the prefix queue automatically.
3. Re-run after import or alias edits; checkpoints skip completed pages.

## 5. What volume to expect

| Path | Rough order of magnitude |
|------|---------------------------|
| Secured-party MCA (post-deBanked) | Up to **200 terms** × up to **50 pages** / term (portal caps apply per query) |
| Debtor prefix sweep | **20 prefixes** / run × pages (rotates across days) |
| Single run total | Hundreds–low thousands **unique** filings (deduped by filing number) |

**Honest limits:** deBanked improves *what you search for* (MCA funders as secured party). The NY Cenuity portal still limits pages per query and requires one search per term — there is no Florida-style empty-text statewide index.

## 6. Reclassify after import (optional)

```bash
python -m scripts.sync_mca_leads   # or dashboard Reclassify FL filings
# NY filings: set state=NY on reclassify form when supported
```

## Related

- [new-york-scale-strategy.md](new-york-scale-strategy.md)
- [playwright-tier1-scrape-strategy.md](playwright-tier1-scrape-strategy.md)
