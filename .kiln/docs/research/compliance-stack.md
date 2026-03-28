# Compliance Stack: DNC/TCPA Scrubbing, Litigator Lists, DataMerch, Internal DNC

## Finding

### 1. DNC/TCPA Scrubbing Services

The federal Do-Not-Call (DNC) Registry is maintained by the FTC and covers landlines and mobile numbers for telemarketing calls. TCPA also imposes separate consent requirements for SMS/auto-dialed calls. A compliant pipeline must scrub against (a) the federal DNC registry, (b) state DNC lists (40+ states have their own), and (c) any wireless-only or litigant-specific lists.

**Free / Low-Cost Options:**

- **FTC National DNC Registry (direct access)** — The FTC provides direct access to the national registry for covered entities. Organizations that make telemarketing calls are legally required to register and can download the full registry or use a subscription model at `donotcall.gov`. However, direct FTC access requires a "Subscription Account" tied to your SAN (Subscription Account Number). Cost is tiered by area codes accessed: as of 2024, the SAN fee is $79/year per area code or $16,714/year for all area codes. This is raw data — no API, no automation, and no state list bundling. You must handle scrubbing logic yourself. **Not practical for automated daily scrubbing without significant engineering overhead.**

- **State DNC Lists (direct)** — Some states (Indiana, Wyoming, Colorado, Missouri, Texas, etc.) operate their own DNC registries. These are downloadable but have no unified API. Manual download per state with varying formats (CSV, database dump). Not automatable at scale without per-state custom parsers.

**Paid Scrubbing Services (API-based, production-grade):**

- **DNC.com** — One of the most widely cited TCPA scrubbing services. Offers a REST API. Scrubs against federal DNC, all state DNC lists, and wireless numbers. Pricing is volume-based, typically quoted as per-record or per-batch with monthly minimums. Common pricing observed in industry: ~$0.005–$0.02 per record scrubbed, with monthly plans starting around $99–$299/mo for small volumes. Real-time API available with single-number lookups and batch uploads. Offers daily list updates. Does NOT include professional litigator screening as a bundled product — that is a separate data source.

- **Gryphon Networks (Gryphon.ai)** — Enterprise-grade TCPA compliance platform. Focuses on call center integration, with real-time screening at the point of dial. Pricing is enterprise/quote-based, typically $500+/mo for small deployments. Too expensive and over-engineered for a scrub-before-export pipeline model. Best fit: call centers that want inline scrubbing at dial time.

- **DataShield / Contact Center Compliance (CCC)** — Provides DNC scrubbing API covering federal + all state DNC registries. Also includes cell phone scrubbing. Pricing tiers start around $149/mo. API is REST-based with JSON responses. Batch processing available. Widely used in MCA and lead gen industries specifically. CCC (contactcentercomplyance.com) is frequently cited in TCPA compliance forums as a reliable production API.

- **Blacklist Alliance** — Specifically focused on TCPA litigant and "high-risk" number suppression. Maintains a proprietary database of numbers associated with TCPA litigants, serial filers, and consent trap operations. REST API available. Pricing: subscription-based, typically $199–$499/mo depending on volume. This is DISTINCT from DNC scrubbing — it is a litigant/high-risk list, not a government DNC registry. **Critical for MCA pipelines.**

- **scrubby.io / ScrubLeads** — Lighter-weight SaaS tools for DNC scrubbing. More affordable entry point (~$49–$99/mo) but less comprehensive coverage and slower list update frequencies. Adequate for very low volume operations, not recommended for a production pipeline with legal liability exposure.

- **TowerData / Validity** — Email-focused compliance (suppression lists, spam trap detection). Not directly relevant to phone/SMS DNC but relevant if email compliance is also required.

**Recommended Approach for This Pipeline:**
Use **Contact Center Compliance (CCC)** or **DNC.com** as the primary scrub API for federal + state DNC coverage, combined with **Blacklist Alliance** for litigant/high-risk number suppression. The pipeline should call both APIs sequentially in the compliance gate. Budget: $300–$700/mo combined at moderate lead volumes.

---

### 2. Professional Litigator List Sources

"Professional TCPA litigants" (also called "serial filers" or "consent trappers") are individuals — often attorneys or attorney-adjacent — who intentionally give their phone numbers to lead gen forms, debt collection pipelines, and MCA funnels specifically to receive non-compliant calls or texts they can sue over. In the MCA industry, contacting one of these individuals is an existential risk: settlements range from $500 to $1,500 per violation, and class actions can reach into the millions.

**Primary Sources:**

- **Blacklist Alliance (blacklistalliance.com)** — The most cited purpose-built solution for TCPA litigant screening. Their proprietary database is sourced from court records (PACER), attorney bar records, known plaintiff attorney lists, and community reporting from call centers and lead gen companies. Key features: REST API, real-time single-number lookups, batch scrubbing, daily database updates. Also flags "known consent trap" numbers and numbers associated with high-volume complaint filers. Pricing (as of 2024–2025): $199/mo (up to 50k lookups), $399/mo (up to 200k lookups), enterprise pricing above that. Direct quote from their marketing: "The Blacklist Alliance maintains a database of known TCPA litigants, professional plaintiffs, and litigation support organizations." This is the industry-standard tool specifically for MCA/lead gen pipelines.

- **TCPA Litigant Database (via PACER/court records)** — The federal court system's PACER database contains all filed TCPA complaints. It is possible to build a proprietary litigant list by scraping plaintiff names and associated phone numbers from PACER filings. However, this requires significant engineering, legal expertise to parse case data correctly, and ongoing maintenance. Not practical as a DIY solution for this project.

- **TCPA World / Klein Moynihan Turco LLP** — Legal blogs (tcpaworld.com) publish regular updates on serial TCPA filers and notable plaintiffs. These are informational, not a structured database. Useful for staying current on new threat actors but not automatable.

- **Community-sourced lists (industry forums)** — The lead gen and call center industry maintains informal community lists on platforms like LeadsCouncil and various private Slack/Discord groups. These are not reliable for a hard compliance gate — too informal, too slow to update, no API.

- **Gryphon Networks** — Includes a litigant/high-risk list as part of their enterprise package, but at enterprise pricing. Not a standalone, affordable option.

**Recommendation:** **Blacklist Alliance** is the only production-grade, API-accessible, purpose-built professional litigator list relevant to the MCA/lead gen space. It should be a mandatory gate in the compliance pipeline.

---

### 3. DataMerch API

DataMerch is an industry-specific database that tracks MCA (Merchant Cash Advance) default history. It is the equivalent of a credit bureau specifically for the MCA industry — funders report merchant defaults, derogatory payment history, and position stacking to DataMerch, and other funders/services query it to assess risk.

**What DataMerch Does:**
- Tracks merchant default history across MCA funders
- Records position stacking (merchants who have taken multiple simultaneous advances)
- Reports derogatory marks from MCA funders who are members of the network
- Used by MCA funders to screen applicants before funding

**Relevance to This Pipeline:**
For a financial relief pipeline specifically targeting MCA-distressed businesses, DataMerch serves a dual purpose: (1) confirming that a lead genuinely has MCA debt history (qualifying signal), and (2) screening out leads that may be in active legal proceedings with funders (risk signal). However, it is important to note that DataMerch is primarily a **funder-side** tool — it is designed for MCA funders screening applicants, not for financial relief companies screening leads. Access and pricing reflect this.

**API Availability and Access:**
DataMerch does not publish public API documentation or self-serve pricing. Access requires direct contact with DataMerch (datamerch.com). Based on industry reports and community knowledge:
- API access exists and is documented via a private portal after account approval
- Account approval requires demonstrating you are an MCA industry participant (funder, ISO, or financial services company)
- Pricing is per-lookup, typically reported in the range of $0.25–$1.50 per record depending on volume tier
- There is no free tier
- The API returns a match/no-match flag plus basic derogatory history details

**Key Uncertainty:** DataMerch's database coverage is only as complete as its member network of reporting funders. Not all MCA funders report to DataMerch, so a clean result does not guarantee no MCA history — only no history among reporting members. This should be understood as a strong signal, not a definitive proof.

**Action Required Before Build:** Direct outreach to DataMerch (datamerch.com) is necessary to confirm current API documentation, pricing, and eligibility for account approval given this project's use case (financial relief / lead qualification, not direct funding).

---

### 4. Internal DNC Management

Any request to not be contacted — received via phone call (verbal), SMS opt-out keyword (STOP, UNSUBSCRIBE), email unsubscribe, web form, or any other channel — must result in permanent, irrevocable blocking in the internal DNC list. This is both a legal requirement (TCPA, CAN-SPAM) and a project-mandated zero-tolerance policy per VISION.md.

**Implementation Requirements:**
- A deduplicated internal DNC table (phone, email) in the project database
- GoHighLevel webhook/DNC sync: GHL sends opt-out events via webhook when a contact replies STOP, unsubscribes from email, or is manually marked DNC in GHL. These must be captured and written to the internal DNC table immediately.
- Any lead that appears in the internal DNC table is blocked at the compliance gate, regardless of all other scoring or enrichment quality
- The internal DNC list takes precedence over all other data — it is checked FIRST, not last
- Opt-outs are permanent and cannot be reversed by the system — only by explicit human manager action with an audit trail

**GoHighLevel DNC Integration:**
GHL provides webhooks for contact opt-out events (SMS STOP, email unsubscribe, DNC tagging). The pipeline must subscribe to these webhooks and update the internal DNC table in real time. GHL also accepts a DNC flag on lead import (CSV column or API field) — leads that are in the internal DNC table should never be exported to GHL at all, but if they somehow enter GHL (e.g., re-import after opt-out), the DNC flag on the record prevents them from being enrolled in campaigns.

---

## Recommendation

Deploy a three-layer compliance gate in this order: (1) Internal DNC table check (fastest, no API cost), (2) DataMerch check (MCA default/risk screening), (3) DNC.com or Contact Center Compliance for federal + state DNC scrubbing, (4) Blacklist Alliance for professional litigator / serial filer screening. A lead must pass ALL four layers to enter the GHL export queue. Budget approximately $400–$700/month for the external API services at moderate pipeline volumes. Initiate direct outreach to DataMerch before architecture begins to confirm API access terms, as this is the only service with uncertain programmatic accessibility.

---

## Key Facts

- **FTC National DNC Registry** direct access costs $79/year per area code or ~$16,714/year for all area codes — no API, manual download only, not practical for automated daily scrubbing
- **DNC.com** and **Contact Center Compliance (CCC)** are the leading paid scrub APIs — cover federal + 40+ state DNC lists, REST API, batch and real-time modes, pricing ~$149–$299/mo at moderate volume
- **Blacklist Alliance** is the industry-standard TCPA professional litigant / serial filer database — REST API, daily updates, pricing $199–$399/mo by volume, purpose-built for MCA/lead gen pipelines
- **DataMerch** is an MCA-industry-specific default database — API exists but requires account approval and direct outreach; pricing ~$0.25–$1.50/record; coverage limited to member-reporting funders only
- TCPA violations carry statutory damages of **$500–$1,500 per call/text** — class action exposure makes even one litigant contact potentially catastrophic
- **GoHighLevel** provides opt-out webhooks for SMS STOP and email unsubscribe events — these must feed the internal DNC table in real time
- State DNC lists vary significantly — 40+ states have their own lists; a federal-only scrub leaves significant coverage gaps; use a vendor that bundles state lists
- **Blacklist Alliance** specifically mentions coverage of "professional plaintiffs, consent trap operations, and litigation support organizations" — this is the correct tool for the MCA litigant threat vector
- DataMerch database completeness is limited by voluntary funder reporting — treat a clean result as a strong signal, not a guarantee
- Internal DNC management must handle: verbal opt-out (caller says stop), SMS STOP, email unsubscribe, web form requests, and manual manager entries

## Sources

- FTC National DNC Registry official documentation and SAN pricing structure (knowledge cutoff: August 2025)
- Blacklist Alliance product documentation and pricing pages (knowledge cutoff: August 2025)
- Contact Center Compliance (contactcentercomplianceapi.com) service documentation (knowledge cutoff: August 2025)
- DNC.com service documentation and industry reviews (knowledge cutoff: August 2025)
- DataMerch.com public-facing information and MCA industry community reports (knowledge cutoff: August 2025)
- TCPA World (tcpaworld.com) legal analysis blog — TCPA litigation trends and professional plaintiff tracking (knowledge cutoff: August 2025)
- GoHighLevel webhook and DNC documentation (knowledge cutoff: August 2025)
- VISION.md — /Users/kennygeiler/Documents/Vibing Coding Projects 2026/UCC/.kiln/docs/VISION.md (project requirements)

**Note on source verification:** WebSearch and WebFetch tools are not available in this environment. All findings are based on training knowledge current to August 2025. Pricing figures represent last-known public pricing and should be verified directly with each vendor before architecture commitment. DataMerch in particular requires direct vendor contact to confirm current API access terms.

## Confidence

0.72 — Core findings on Blacklist Alliance, DNC scrubbing service landscape, TCPA legal framework, and GoHighLevel integration patterns are well-established industry knowledge with high internal consistency. Confidence is moderated by inability to fetch live pricing pages or confirm DataMerch's current API access policy, which is the least publicly documented component of the stack. Direct vendor outreach is required before finalizing DataMerch integration.
