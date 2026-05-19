# Florida Suppress-Tier Concentration Analysis

**Date:** May 2026  
**Database:** `postgresql://localhost:5433/ucc_dev`  
**Scrape snapshot:** 2,451 FL filings, run status `completed` (2026-05-19)

---

## Executive summary

Of **1,946** Florida `business_accounts`, **1,903 (97.8%)** are **`suppress`** tier and only **43 (2.2%)** reach **monitor**, **work**, or **priority**. That pattern is **real for this dataset and the current consolidation scorer**—not a pipeline bug. The model optimizes for **stacked, recent MCA-style UCC activity** on a **broad whole-state org index** where most secured parties are unknown, banks, government, or agents, and **84%** of accounts have last filing activity **>365 days** ago. For **general debt consolidation** prospecting, there is a **product mismatch**: 338 accounts have material lenders but **317** remain suppress; only **8** strict MCA **leads** exist on 2,451 filings. The tool is **useful today as a narrow MCA-stack filter** (~17 work+priority accounts) with manual QA; it is **not yet** a broad consolidation lead list without classifier, recency, collateral, or scrape-strategy changes.

---

## Key metrics

### Account tier distribution

| `consolidation_tier` | Accounts | % | Avg score | Min | Max |
|----------------------|----------|---|-----------|-----|-----|
| **suppress** | 1,903 | 97.8% | 3.3 | 0.0 | 29.0 |
| **monitor** | 26 | 1.3% | 30.9 | 30.0 | 36.0 |
| **work** | 5 | 0.3% | 50.0 | 50.0 | 50.0 |
| **priority** | 12 | 0.6% | 70.0 | 70.0 | 70.0 |
| **Total** | **1,946** | | | | |

### Score thresholds and MCA signals

| Metric | Count | % of accounts |
|--------|-------|----------------|
| `consolidation_score >= 30` (monitor+) | 43 | 2.2% |
| `consolidation_score >= 50` (work+) | 17 | 0.9% |
| `mca_funder_count >= 1` | 169 | 8.7% |
| `mca_funder_count >= 2` | 12 | 0.6% |
| `material_ucc_count >= 1` | 338 | 17.4% |
| MCA (`mca_funder_count >= 1`) but still **suppress** | 149 | 7.6% |

**Filings:** 2,451 (100% with `filing_date`).

### Average `score_components` (JSON on account)

| Component | Suppress (1,903) | Non-suppress (43) |
|-----------|------------------|-------------------|
| mca_stack | 0.94 | 9.44 |
| recency | 1.26 | 17.35 |
| velocity | 0.16 | 3.84 |
| material_stack | 1.09 | 5.05 |
| collateral | **0.00** | **0.00** |
| noise_penalty | −1.65 | −0.27 |
| match_trust_penalty | 0.00 | 0.00 |

**Score histogram:** 1,629 accounts at 0–6; 177 at 10–19; 97 at 20–29; 26 at 30–36; 5 at 50; 12 at 70 (tier floors pin some scores).

### Filing-level `lender_class` (FL)

| `lender_class` | Filings | % |
|----------------|---------|---|
| **unknown** | 1,737 | **70.9%** |
| government | 203 | 8.3% |
| mca_funder (heuristic) | 201 | 8.2% |
| bank | 193 | 7.9% |
| registered_agent | 101 | 4.1% |
| insurance | 16 | 0.7% |

### MCA detector vs classifier

| Signal | Count |
|--------|-------|
| `is_mca = true` (strict lead pipeline) | **8** |
| `lender_class = mca_funder` but `is_mca ≠ true` | **197** |
| FL **leads** rows | **8** (4 shell, 4 fuzzy) |

---

## Why suppress dominates

Tiers map to score floors in `app/consolidation/scorer.py`: **priority ≥70**, **work ≥50**, **monitor ≥30**, else **suppress**.

### Positive components (max ~100 before penalties)

| Component | Max | Typical suppress gap |
|-----------|-----|----------------------|
| MCA stack | 35 | 0 (no MCA funders) |
| Recency | 25 | 0–4 (stale; **1,632 accounts** last filing **>365d**) |
| Velocity (90d) | 15 | ~0 |
| Material stack (bank/alt/mca) | 15 | ~1 |
| Collateral keywords | 10 | **0 everywhere** (0 FL filings with collateral text) |

Penalties reduce score further: **noise** (registered agents, government) and **match trust** (fuzzy/low-confidence matches).

### Tier floors (escape hatches from deep suppress)

- **2+ MCA funders** → score floored to **≥70** (priority), even when filings are years old (**8 of 12** priority accounts have last filing **>365 days**).
- **1 MCA + filing ≤60 days** → score floored to **≥50** (work).

**Typical suppress profile:** no MCA stack + old filings + no 90-day velocity. **149 accounts** have `mca_funder_count ≥ 1` but stay suppress as **stale single-MCA** (score tops out ~28–29: recency 10 + mca_stack 12 + material ~6–15).

**Sample patterns:**

- **Suppress + heuristic MCA** (score 28–29): one MCA funder, **105–243 days** since last filing.
- **Monitor, often no MCA:** e.g. score 35 with **mca_stack 0**, recency 25, velocity 10 — recent activity without MCA stack.
- **Work (5 accounts):** one MCA funder, **6–54 days** since last filing — recent single-MCA floor.
- **Priority (12 accounts):** two or more MCA funders → score floored to **70** regardless of staleness.

---

## Filings vs leads vs accounts

Three layers measure different things:

| Layer | What it is | FL snapshot |
|-------|------------|---------------|
| **Filings** | Every scraped UCC row | 2,451 |
| **Accounts** | Debtor rollup + consolidation score/tier | 1,946 |
| **Leads** | Strict MCA detector (`is_mca=true`) | 8 |

**Leads ≠ consolidation queue.** Account tiers use **`lender_class`** / `is_mca` on filings; leads use the stricter `detect_mca` path with lender guard blocks. Hence **169 accounts** with `mca_funder_count ≥ 1` but only **8 leads**.

Heuristic MCA tagging uses broad keywords (`capital`, `funding`, `advance`, `merchant`) — e.g. **"MERCHANTS AND SOUTHERN BANK"** as `mca_funder` with `is_mca=false`.

### Filing count vs tier

| Filings / account | Total accounts | Non-suppress |
|-------------------|----------------|--------------|
| 1 | 1,656 | 18 (1.1%) |
| 2 | 198 | 10 |
| 3 | 51 | 5 |
| 4–10 | 34 | 8 |
| 11+ | 7 | 2 |

More filings alone rarely escapes suppress without MCA + recency signals. **1-filing accounts:** 1,638 suppress vs 15 monitor + 3 work. **2–3 filings:** most priority (5) and some monitor. **4–10 filings:** 7 priority, 1 monitor.

### Recency vs tier

| Recency bucket | Dominant pattern |
|----------------|------------------|
| **>365d** | **1,632 accounts** — vast majority suppress |
| **181–365d** | Almost all suppress |
| **61–180d** | Mostly suppress; rare monitor |
| **≤60d** | Mix of suppress, work (recent single-MCA floor), some monitor |

---

## Is this true reality?

**Yes, for this product definition and broad FL scrape** — not evidence the scrape failed.

The whole-state org index is mostly:

- **Old activity** (~84% of accounts: last filing >365 days)
- **71% unknown** secured parties (names miss bank/gov/agent heuristics and the small `mca_aliases` list — **20 rows**)
- **Strict `is_mca`** on only **8** filings (`is_mca` null = 0 remaining)

**~98% suppress is expected** given scorer rules + data shape. It does **not** mean only ~2% of Florida businesses have debt worth consolidating; it means ~2% match **stacked/recent MCA distress** as currently scored.

**Cross-check:** README “Understanding the numbers” documents the same tier shape (~12 priority, ~5 work, ~26 monitor on ~1,946 accounts). **Operator leads** are now [MCA funder accounts](../README.md#leads-mca-funder-accounts) (`mca_funder_count >= 1`, ~169 FL) — not the small filing-level `leads` table (~8).

---

## Product fit for debt consolidation

| If you mean… | This tool measures… |
|--------------|---------------------|
| Any business with multiple liens / bank debt / refinance opportunity | **No** — 338 material-lender accounts; **317** still suppress |
| Stacked MCA, recent distress, consolidation outreach | **Yes** — tier rules optimize this |
| Confirmed MCA filings (`leads` table) | **Thin** — **8** rows on 2,451 filings |

**Collateral gap:** 0 FL filings with `collateral_description` populated today, so the +10 collateral component never fires. MCA collateral heuristics cannot contribute until enrichment improves.

### Usefulness today

| Use case | Useful today? |
|----------|----------------|
| **Narrow:** 2+ heuristic MCA funders or very recent single MCA | **Somewhat** — ~17 work+priority; verify secured parties manually |
| **Broad:** Florida debt consolidation lead list from UCC | **Not yet** — most bank stacks, SBA, equipment, single old MCA never reach work/priority |
| **Confirmed MCA opportunities** | **Thin** — 8 leads; strict detector + broad scrape |

**Bottom line:** For **MCA-stack consolidation outreach**, the **43-account** monitor+ queue (especially **17** work+priority) is a small but usable starting list with manual QA. For **general debt consolidation**, the proxy is wrong unless signals widen (banks/material lenders, recency, confirmed MCA, collateral) or scrape strategy shifts (Exact MCA lender terms, targeted profiles).

---

## Recommendations

1. **Align MCA signals** — Expand `mca_aliases` and MCA pipeline coverage; score on **`is_mca=true`** or alias-confirmed funders, not keyword `capital`/`merchant` alone (reduces false priority on old “MERCHANTS … BANK” stacks).

2. **Require recency on tier floors** — e.g. dual-MCA → priority only if `days_since_last_filing ≤ 180`; addresses **8/12** priority accounts stale **>1 year**.

3. **Separate product lanes** — Keep MCA stack queue strict; add a **bank / multi-lien / recent** lane (material lenders + recency, no MCA required). Many monitor-tier accounts already show recent activity **without** MCA.

4. **Enrich FL filing detail** — Secured party is populated; collateral is not. Enable collateral from `/Filings/{ucc}` for scoring signal and stricter MCA detection.

5. **Targeted scrape mode** — Broad index for coverage; **Exact lender-term searches** (`FL_SCRAPE_EXACT_TERMS`) for lead volume. Lowering `MONITOR_MIN` from 30 → 25 adds only **~18** accounts — modest gain, more noise.

---

## Appendix: SQL queries used

Run against `ucc_dev` on port 5433. Replace `business_account_id` with `account_id` if your schema uses that FK name.

### Tier distribution and score stats

```sql
SELECT consolidation_tier, COUNT(*) AS cnt,
       ROUND(AVG(consolidation_score)::numeric, 1) AS avg_score,
       ROUND(MIN(consolidation_score)::numeric, 1) AS min_s,
       ROUND(MAX(consolidation_score)::numeric, 1) AS max_s
FROM business_accounts WHERE state = 'FL'
GROUP BY 1 ORDER BY cnt DESC;

SELECT COUNT(*) FROM business_accounts WHERE state = 'FL';
SELECT COUNT(*) FROM business_accounts WHERE state = 'FL' AND consolidation_score >= 30;
SELECT COUNT(*) FROM business_accounts WHERE state = 'FL' AND consolidation_score >= 50;
SELECT COUNT(*) FROM business_accounts WHERE state = 'FL' AND mca_funder_count >= 1;
SELECT COUNT(*) FROM business_accounts WHERE state = 'FL' AND mca_funder_count >= 2;
SELECT COUNT(*) FROM business_accounts WHERE state = 'FL' AND consolidation_tier != 'suppress';
```

### Score component averages

```sql
SELECT
  ROUND(AVG((score_components->>'mca_stack')::numeric), 2) AS mca_stack,
  ROUND(AVG((score_components->>'recency')::numeric), 2) AS recency,
  ROUND(AVG((score_components->>'velocity')::numeric), 2) AS velocity,
  ROUND(AVG((score_components->>'material_stack')::numeric), 2) AS material_stack,
  ROUND(AVG((score_components->>'collateral')::numeric), 2) AS collateral,
  ROUND(AVG((score_components->>'noise_penalty')::numeric), 2) AS noise_pen,
  ROUND(AVG((score_components->>'match_trust_penalty')::numeric), 2) AS trust_pen
FROM business_accounts
WHERE state = 'FL' AND consolidation_tier = 'suppress';

-- Repeat with: consolidation_tier != 'suppress'
```

### Filing `lender_class` distribution

```sql
SELECT COALESCE(lender_class, 'null') AS lc, COUNT(*) AS c,
       ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 2) AS pct
FROM ucc_filings WHERE state = 'FL'
GROUP BY 1 ORDER BY c DESC;

SELECT is_mca, COUNT(*) FROM ucc_filings WHERE state = 'FL' GROUP BY 1 ORDER BY 2 DESC;
SELECT COUNT(*) FROM ucc_filings WHERE state = 'FL' AND lender_class = 'mca_funder' AND (is_mca IS NOT TRUE);
```

### Filing count vs tier

```sql
SELECT filing_bucket, consolidation_tier, COUNT(*) AS accounts FROM (
  SELECT ba.consolidation_tier,
    CASE
      WHEN fc.c = 1 THEN '1 filing'
      WHEN fc.c BETWEEN 2 AND 3 THEN '2-3 filings'
      WHEN fc.c BETWEEN 4 AND 10 THEN '4-10 filings'
      ELSE '11+ filings'
    END AS filing_bucket
  FROM business_accounts ba
  JOIN (
    SELECT account_id, COUNT(*) AS c
    FROM ucc_filings WHERE state = 'FL' AND account_id IS NOT NULL
    GROUP BY 1
  ) fc ON fc.account_id = ba.id
  WHERE ba.state = 'FL'
) x
GROUP BY 1, 2 ORDER BY 1, 2;
```

### Recency buckets

```sql
SELECT CASE
  WHEN days_since_last_filing IS NULL THEN 'null'
  WHEN days_since_last_filing <= 60 THEN '<=60d'
  WHEN days_since_last_filing <= 180 THEN '61-180d'
  WHEN days_since_last_filing <= 365 THEN '181-365d'
  ELSE '>365d'
END AS bucket, consolidation_tier, COUNT(*)
FROM business_accounts WHERE state = 'FL'
GROUP BY 1, 2 ORDER BY 1, 3 DESC;
```

### Supplemental checks

```sql
SELECT COUNT(*) FROM business_accounts
WHERE state = 'FL' AND mca_funder_count >= 1 AND consolidation_tier = 'suppress';

SELECT COUNT(*) FROM business_accounts
WHERE state = 'FL' AND material_ucc_count >= 1;

SELECT COUNT(*) FROM business_accounts
WHERE state = 'FL' AND consolidation_score >= 25 AND consolidation_score < 30;

SELECT COUNT(*) FROM ucc_filings WHERE state = 'FL' AND collateral_description IS NOT NULL AND collateral_description != '';
```

---

*Source: investigation subagent report (2026-05-19), live queries on `ucc_dev`, logic from `app/consolidation/scorer.py`.*
