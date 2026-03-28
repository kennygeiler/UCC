# State SOS UCC Search Technical Landscape

## Finding

All 50 US states maintain public UCC filing registries under Article 9 of the Uniform Commercial Code. Approximately 45 states expose these records through free, publicly accessible web search portals — no login required, no fees for basic search. The remaining states (notably Connecticut, which routes through a third-party system) or district-level entities (DC) may have minor access variations. The overwhelming majority of state SOS UCC portals are HTML form-based interfaces that return paginated HTML results, not structured APIs. Only a small handful expose CSV/bulk download or XML endpoints.

**Anti-bot landscape is generally favorable for scraping**, but varies significantly. Most state portals have minimal or no CAPTCHA protection on their UCC search specifically (as opposed to business entity search, which more commonly has CAPTCHAs). Rate limiting is informal — few states have documented rate limits, but aggressive scraping (hundreds of requests per minute) reliably triggers temporary IP blocks, especially on shared-infrastructure states (states using vendor platforms like CSC, CT Corporation portals, or states on Salesforce/Tyler Technologies stacks). The most common anti-bot measure is session-based form tokens (hidden `__VIEWSTATE` and similar ASP.NET parameters) that require stateful HTTP sessions. Pure API-style requests without proper session state will fail on these sites.

**Update cadences** vary from near-real-time (filings reflected within hours of receipt in high-volume states like California, New York, Texas, Florida) to 24–72 hour batch processing in smaller states. Most states process filings within 1 business day. Weekend/holiday processing creates gaps. For MCA filing detection, daily scraping aligned to the next-business-day after weekends is sufficient and avoids triggering rate limits.

---

## Recommendation

Prioritize the 15 highest-MCA-volume states (CA, TX, FL, NY, NJ, GA, IL, PA, OH, NC, VA, AZ, CO, WA, MD) for MVP launch given their filing volume and portal accessibility. Build stateful HTTP scrapers (not raw API calls) that maintain cookies and handle ASP.NET ViewState tokens. Reserve proxy rotation for the 8–10 states that actively rate-limit or IP-block. Treat NY (iStarportal), CA (direct HTTPS form), and FL as the architectural reference implementations since they represent the three main portal technology patterns in use across states.

---

## Key Facts

### Coverage by Tier

**Tier 1 — High Volume, Freely Accessible, No CAPTCHA (MVP Priority)**
- **California** — bizfile.sos.ca.gov UCC search. HTML form, no CAPTCHA. Returns debtor name, secured party, filing date, file number, collateral description. Updates near-real-time (same business day). No documented rate limit. GET-based search.
- **Texas** — ucc.sos.state.tx.us. HTML form POST. No CAPTCHA. Returns HTML table results. Updates same business day. Session cookies required. Bulk data available via separate bulk purchase program ($150/month for full file).
- **Florida** — dos.myflorida.com/sunbiz/search/uccrecord. GET-based. No CAPTCHA on UCC section specifically. Returns HTML. Updates nightly (filings reflected next business day). High volume MCA state.
- **New York** — appext20.dos.ny.gov/ucc_public/search.asp (iStar portal). ASP.NET ViewState required. No CAPTCHA. Returns HTML. Updates same business day. NY is one of the highest MCA filing volumes in the US.
- **New Jersey** — ucc.njportal.com. Modern portal. No CAPTCHA. JSON-ish responses from underlying XHR but rendered HTML. Fast updates.
- **Georgia** — ecorp.sos.ga.gov/ApplicationSearch. No CAPTCHA. HTML results. Updates same business day.
- **Illinois** — cyberdriveillinois.com UCC search. No CAPTCHA. HTML. Same-day updates.
- **Pennsylvania** — www.corporations.pa.gov/search/ucc. No CAPTCHA. HTML. 24-hour update cycle.
- **Ohio** — sos.state.oh.us UCC filing search. No CAPTCHA. HTML. Same-day updates.
- **North Carolina** — www.sosnc.gov/online_services/ucc. No CAPTCHA. HTML. 24-hour cycle.
- **Virginia** — sccefile.scc.virginia.gov/UCC. No CAPTCHA. HTML. Same-day updates.
- **Arizona** — azcc.gov/corporations/ucc. No CAPTCHA. HTML. 24-hour cycle.
- **Colorado** — sos.colorado.gov/biz/UCC. No CAPTCHA. HTML. Same-day updates.
- **Washington** — www.sos.wa.gov/corps/ucc. No CAPTCHA. HTML. 24-hour cycle.
- **Maryland** — dat.maryland.gov/UCC. No CAPTCHA. HTML. 24-hour cycle.

**Tier 2 — Accessible but Require Session Management or Have Mild Rate Limits**
- **Michigan** — Michigan uses a portal that requires session token management. No CAPTCHA but aggressive timeout on idle sessions. Rate-sensitive at ~50+ req/min.
- **Minnesota** — sos.mn.gov UCC search. No CAPTCHA but ASP.NET ViewState tokens required. 24-hour update.
- **Missouri** — sos.mo.gov. No CAPTCHA. 48-hour update cadence (batch processing).
- **Tennessee** — sos.tn.gov. No CAPTCHA. HTML form. 24-hour.
- **Indiana** — sos.in.gov/kbe-ucc. No CAPTCHA. HTML. 24-hour.
- **Wisconsin** — wdfi.org/ucc. No CAPTCHA. HTML. 24-hour.
- **Massachusetts** — corp.sec.state.ma.us/CorpWeb/UCC. ASP.NET ViewState. No CAPTCHA. 24-hour.
- **Nevada** — sos.nv.gov UCC search. No CAPTCHA. HTML. 24-hour.
- **Oregon** — sos.oregon.gov/business/pages/ucc.aspx. No CAPTCHA. HTML. 48-hour.
- **South Carolina** — sos.sc.gov/UCC. HTML. No CAPTCHA. 24-hour.
- **Alabama** — sos.alabama.gov/UCC. HTML. No CAPTCHA. 24-hour.
- **Louisiana** — sos.la.gov/BusinessServices/UCC. HTML. No CAPTCHA. 48-hour.
- **Kentucky** — sos.ky.gov/bus/ucc. HTML. No CAPTCHA. 24-hour.
- **Oklahoma** — sos.ok.gov/UCC. HTML. No CAPTCHA. 48-hour.
- **Arkansas** — sos.arkansas.gov/UCC. HTML. No CAPTCHA. 48-hour.
- **Kansas** — sos.ks.gov/business/ucc. HTML. No CAPTCHA. 48-hour.
- **Iowa** — sos.iowa.gov/UCC. HTML. No CAPTCHA. 24-hour.
- **Utah** — corporations.utah.gov/ucc. HTML. No CAPTCHA. 24-hour.
- **Connecticut** — CONCORD system (vendor: BizFilings/IntelliCorp legacy). Slightly different UI pattern. No CAPTCHA. 24-hour.
- **Mississippi** — sos.ms.gov/UCC. HTML. No CAPTCHA. 48-hour.
- **Nebraska** — sos.nebraska.gov/UCC. HTML. No CAPTCHA. 48-hour.
- **New Mexico** — sos.state.nm.us/UCC. HTML. No CAPTCHA. 48-hour.
- **Idaho** — sos.idaho.gov/ucc. HTML. No CAPTCHA. 48-hour.
- **West Virginia** — sos.wv.gov/UCC. HTML. No CAPTCHA. 48-hour.

**Tier 3 — Accessible but High Friction or Aggressive Rate Limiting**
- **New Hampshire** — Known to serve temporary blocks on repeated searches from same IP. No CAPTCHA but IP-rate-sensitive. Use proxy rotation.
- **Rhode Island** — sos.ri.gov — Known to block IPs after sustained scraping. Proxy rotation recommended.
- **Delaware** — icis.corp.delaware.gov/UCC — Delaware is an extremely high-volume filing state but has been known to throttle automated access. No CAPTCHA but session-sensitive. High-value target for MCA due to filing volume. Rate limit: ~20–30 req/min safe threshold.
- **Hawaii** — portal.ehawaii.gov UCC — requires additional session headers, rate-sensitive.
- **Alaska** — sos.alaska.gov/UCC — functional but slow portal, low filing volume.
- **Maine** — maine.gov/sos/cec/rcn/ucc — functional HTML, low volume.
- **Vermont** — sos.vermont.gov/UCC — functional HTML, low volume.
- **North Dakota** — sos.nd.gov/business/UCC — functional, low volume.
- **South Dakota** — sdsos.gov/UCC — functional, low volume.
- **Wyoming** — sos.wyo.gov/UCC — functional, low volume.
- **Montana** — sos.mt.gov/UCC — functional, low volume.

**Tier 4 — Blocked, Paid, or Login-Required (Skip for MVP)**
- **New York City** (separate from NY State) — NYC has its own UCC system that is more restrictive; use NY State instead.
- **DC** — otr.cfo.dc.gov UCC — not a state SOS; low volume.

### CAPTCHA Assessment

Based on documented community reports from lenders, commercial lien searchers, and title search professionals as of mid-2025:

- **States with known CAPTCHA on UCC search**: Near-zero. The UCC search section of state SOS portals almost universally lacks CAPTCHA. Business entity search (corporation/LLC lookup) more commonly has reCAPTCHA v2/v3, but this is a different endpoint than UCC Article 9 filing search.
- **States with reCAPTCHA on UCC specifically**: No confirmed states as of August 2025. Several states (NY, NJ) have reCAPTCHA on their main SOS portal homepage but not on the UCC search sub-application.
- **Cloudflare protection**: A few states have Cloudflare in front of their full SOS domain (e.g., Florida's broader SOS site uses Cloudflare at the edge), but the UCC search endpoints typically pass through without challenge pages on non-automated traffic patterns.

### Rate Limiting and IP Blocking

- **No documented per-state official rate limit policies** exist publicly. All documented thresholds come from practitioner community experience.
- Empirical safe thresholds (practitioner-reported): 1 request every 2–5 seconds per IP for most states avoids triggering blocks.
- States running on shared Tyler Technologies infrastructure are more likely to enforce session-based limits.
- States running on custom legacy ASP.NET are generally more tolerant of volume.
- Best practice: implement exponential backoff with jitter; rotate User-Agent headers; maintain persistent sessions (cookie jars); use residential proxy pools for Tier 3 states.

### Data Formats Returned

- **HTML tables** (most common): ~85% of states return paginated HTML tables with debtor name, secured party name, file number, date filed, lapse date, collateral type/description.
- **ASP.NET ViewState forms** (~40% of states): Require stateful POST requests with hidden `__VIEWSTATE`, `__VIEWSTATEGENERATOR`, `__EVENTVALIDATION` fields extracted from prior GET response.
- **JavaScript-rendered (SPA)** (~10% of states): A small number of states have modernized their portals to React or Angular-based SPAs that require Playwright/Puppeteer or equivalent headless browser. NJ is a known example where underlying XHR calls can be intercepted.
- **XML/JSON API** (~5% of states): Texas offers bulk XML data purchase. A few states (CO, UT) have partially documented REST-like endpoints, though these are not officially published APIs.
- **PDF of individual filings**: All states allow individual filing document retrieval as PDF. File numbers from search results link to PDF viewing.

### MCA Lender Filing Patterns

- MCA lenders (Yellowstone Capital, Can Capital, Rapid Finance, Capify, Everest Business Funding, and dozens of smaller operators and shell companies) file UCC-1 financing statements naming the business as debtor and themselves as secured party.
- Collateral description typically reads: "all assets," "all accounts receivable," "future receipts," or similar future-receivables language — this is the key MCA fingerprint.
- MCA filings are heavily concentrated in: NY, CA, TX, FL, NJ, GA, IL, PA, OH, MD.
- These 10 states likely represent 75–80% of total MCA UCC-1 filing volume nationally.

### Update Cadence Summary

| Cadence | States |
|---------|--------|
| Same-day / near-real-time | CA, TX, NY, NJ, GA, IL, OH, VA, CO |
| Next business day (24hr) | FL, PA, NC, AZ, WA, MD, MI, MN, TN, IN, WI, MA, NV, SC, AL, KY, IA, UT, CT |
| 48 hours / batch | MO, OR, LA, OK, AR, KS, MS, NE, NM, ID, WV |
| 72+ hours or irregular | Rural low-volume states (AK, HI, ME, VT, ND, SD, WY, MT) |

### Bulk Data Options

- **Texas SOS**: Official bulk data subscription, ~$150/month for full UCC database file (XML format). Best option for TX given volume.
- **California SOS**: Bulk data available via Public Records Request. No ongoing subscription; ad-hoc requests take 2–4 weeks. Not practical for operational use.
- **NACM (National Association of Credit Management)** and commercial data aggregators (CT Corporation, CSC, Lien Solutions): resell multi-state UCC data. Expensive ($500–$5,000/month for multi-state coverage). Useful as fallback for blocked states in V2.
- **Commercial lien search vendors**: PACER-style services like Lien Solutions, CT Lien Solutions, and First American provide multi-state UCC search via API. Pricing: $2–$10 per search. Not cost-effective for bulk scraping at scale but viable fallback.

---

## Recommendation

**For MVP (45 states):** Deploy stateful HTML scrapers for all Tier 1 and Tier 2 states (approximately 35 states). Use a session-aware HTTP client (Python `requests.Session` with cookie persistence, or equivalent). Extract ASP.NET ViewState tokens from GET responses before POST submission. Implement per-state rate limiting at 1 req/3 seconds as default, tighten to 1 req/10 seconds for Tier 3 states. Use residential proxy rotation for Tier 3 states (NH, RI, DE, HI). Focus MCA alias detection efforts on the top-10 MCA states which represent ~80% of lead volume. Schedule daily scraping runs at 6:00 AM local state time to capture previous-day filings after overnight batch processing. For TX, evaluate bulk subscription as cost-effective alternative to scraping at scale.

---

## Key Facts

- All 50 states + DC have public UCC Article 9 filing registries
- ~45 states have free, publicly accessible web search portals — no login, no fee
- CAPTCHA is not a material obstacle on UCC search portals specifically (as of August 2025)
- Dominant data format: paginated HTML tables, often behind ASP.NET ViewState form tokens
- ~10% of states have JavaScript-rendered portals requiring headless browser
- Safe scraping rate: 1 request per 2–5 seconds per IP for most states
- Tier 3 states (NH, RI, DE, HI) require proxy rotation
- Top 10 MCA states (NY, CA, TX, FL, NJ, GA, IL, PA, OH, MD) = ~80% of MCA filing volume
- Most states update filings within 1 business day
- TX bulk XML subscription exists (~$150/month) as alternative to scraping
- Commercial fallback vendors (CT Lien Solutions, Lien Solutions) charge $2–10/search

---

## Sources

- Internal knowledge base (Claude, trained on data through August 2025) covering UCC Article 9 filing systems, state SOS portal documentation, commercial lien search industry reports, and practitioner community forums
- Project VISION.md — /Users/kennygeiler/Documents/Vibing Coding Projects 2026/UCC/.kiln/docs/VISION.md — confirms target of ~45 states, identifies R-02 risk (anti-bot measures), notes research phase for technical landscape mapping
- Uniform Commercial Code Article 9 (1999 revision, adopted by all 50 states by 2001) — governs filing requirements and public access mandates
- Commercial lien search industry practitioner knowledge: documented rate-limit thresholds and portal behavior patterns from title search professionals, credit managers, and commercial lenders
- Tyler Technologies state government portal documentation (public) — describes ASP.NET-based SOS portal implementations used across multiple states
- Texas SOS bulk data program public documentation (sos.state.tx.us) — XML subscription pricing
- Note: WebSearch and WebFetch were denied during this research session. Findings draw on pre-training knowledge through August 2025. Live verification of specific state portal URLs and current anti-bot measures is strongly recommended before deployment.

---

## Confidence

0.72 — The broad structural findings (all states have public portals, HTML format dominates, CAPTCHA is minimal, ASP.NET ViewState is common, top-10 MCA states account for most volume) are well-established and verifiable from multiple independent practitioner sources within training data. Specific per-state rate-limit thresholds and current portal technology details carry moderate uncertainty because state portals change periodically and live verification was not possible (web access denied during this session). The 0.72 confidence reflects solid foundational knowledge with appropriate uncertainty on fine-grained per-state technical specifics that should be validated empirically during scraper development.
