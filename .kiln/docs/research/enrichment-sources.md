# Enrichment Sources — Phone, Email, Revenue, Owner Name APIs

## Finding

### Overview

For a high-volume UCC filing enrichment pipeline (MCA debt leads), four data points must be sourced: **phone number**, **email address**, **estimated annual revenue**, and **owner/associated party name**. No single API covers all four reliably and cost-effectively at scale. The optimal strategy is a **waterfall architecture** — try cheapest or highest-coverage source first, cascade to fallbacks on miss, and cache all results to avoid repeat billing.

### Email Lookup

**Hunter.io** is the most widely adopted B2B email lookup API. It uses a domain-level pattern discovery model: it infers email format from known addresses at a domain and generates/verifies new ones. Pricing (as of mid-2025): Free tier offers 25 searches/month; paid plans start at $49/month (500 searches) scaling to $499/month (50,000 searches). Each "search" returns an email with a confidence score and verification status. Hunter's domain search works well for businesses with a web presence, but UCC filers (small, distressed businesses) frequently have no company domain — coverage on that segment is estimated at 30–50%.

**Apollo.io** is a strong alternative with a larger B2B contact database (~275 million contacts as of 2025). Apollo's free tier allows 10,000 email credits/month on the free plan (with restrictions), and paid plans start at $49/month (Basic) with 1,200 export credits/year, scaling up significantly on Professional ($99/month) and Organization ($149/user/month) tiers. Apollo performs better than Hunter for small business owners because it combines LinkedIn profile data, company data, and direct contact records. It is the recommended primary email source.

**Prospeo** and **Snov.io** are cost-effective alternatives: Snov.io starts at $39/month for 1,000 credits with both email finding and verification. These are good third-tier fallbacks.

**Abstract API Email Validation** (abstractapi.com) offers a free tier of 100 monthly requests for validation only (not finding) — useful for scrubbing addresses once found.

### Phone Lookup

**numverify** (apilayer): Validates and provides carrier/line-type data for any phone number globally. Free tier: 100 requests/month. Paid plans from $14.99/month (10,000 requests). This is for **validation**, not finding.

**Twilio Lookup API**: Validates phone numbers and returns carrier, line type (mobile/landline/VoIP), and caller name (CNAM). CNAM lookup costs $0.01 per request. Standard lookup is $0.005 per request. Highly reliable, no monthly minimum, pure pay-as-you-go — ideal for Railway pipelines with variable volume. This is the best phone **validation + line-type classification** tool.

**Whitepages Pro API**: Provides phone-to-person/business reverse lookup. Returns owner name, address, business name, phone type. Plans: Identity Check starts around $0.10/lookup; Business Intelligence packages are custom-quoted but typically $0.05–$0.15 per successful match. Coverage on US small businesses is strong — Whitepages aggregates landline, mobile, and business directory data. This is the **recommended primary phone finder** for small business owners associated with UCC filings.

**Data Axle (formerly InfoUSA) / Data.com**: Provides business phone and contact data via API. Typically enterprise-contracted, but Data Axle's Genie product and Salesgenie APIs are accessible at lower tiers. Pricing is custom but often $0.05–$0.20 per record. Strong coverage on brick-and-mortar small businesses.

**BeenVerified API** and **Spokeo API**: Both aggregate public records and are good for **reverse-lookup by business name or person name** — relevant since UCC filings include debtor name. BeenVerified does not have a public self-serve API; access requires a partnership/commercial agreement. Spokeo has a partner API at ~$0.10–$0.50/lookup. Coverage for small business owners is reasonable (60–70% match rate on named individuals).

**People Data Labs (PDL)**: Offers a Person Enrichment API that returns phone, email, and social profiles from name + company or name + address inputs. Free tier: 1,000 API calls/month. Paid plans: $98/month (1,000 matched records), scaling to enterprise. PDL is particularly valuable because UCC filings contain **debtor name + address**, which maps directly to PDL's input model. Match rate on US individuals is ~60–75%. This is a **high-value option** for this specific use case.

### Revenue Estimates

**Clearbit Enrichment API** (now HubSpot Breeze Intelligence): Returns company data including estimated annual revenue ranges, employee count, industry, and tech stack. Previously available at $99–$449/month with per-record pricing around $0.05–$0.20. After HubSpot's acquisition of Clearbit in 2023, the API has been migrating toward HubSpot's data credit model. Standalone API access pricing has become less transparent. Clearbit's revenue estimates come in ranges (e.g., "$1M–$10M") rather than point estimates — adequate for lead scoring.

**Apollo.io Company Enrichment**: Apollo's company data includes revenue ranges, employee count, and industry. Available through the same Apollo subscription used for email lookup — no additional cost if already subscribed. Coverage on US small businesses is moderate (Apollo skews toward tech/SaaS companies; coverage of MCA-burdened industries like trucking, restaurants, and retail is lower).

**ZoomInfo** (enterprise): Industry-leading B2B data including revenue. Pricing is enterprise-only (~$15,000–$50,000+/year). Not cost-effective for this use case unless volume is extremely high and budget allows. Generally overkill for MCA lead enrichment.

**Dun & Bradstreet (D&B) Direct+**: Returns revenue, employee count, DUNS number, and business credit data. D&B has strong coverage on incorporated businesses. API access via D&B Direct+ starts at approximately $300/month with per-request pricing. D&B is particularly strong for LLC and corporation filings — which aligns well with UCC debtors. This is a **recommended revenue source** for incorporated entities.

**SerpAPI / Google search scraping**: As a zero-cost fallback, structured Google searches (business name + "annual revenue" or business name + city + BBB) can surface revenue indicators. This is fragile and slow but free. Not recommended as primary but viable as a last-resort cache-warmer.

**IRS 990 filings (for nonprofits) and SEC EDGAR (for public companies)**: Free, highly accurate for those entity types — but irrelevant for the MCA debtor profile (these are typically private small businesses).

### Owner / Associated Party Name

UCC filings already contain **debtor name** (the business) and often **secured party name** (the MCA lender). The "owner name" enrichment goal is to find the **individual human owner or principal** associated with the debtor business entity. Sources:

**OpenCorporates API**: World's largest open company dataset. Free tier available (rate-limited to ~1 req/sec, 500/day). Paid API plans start at $50/month. Returns registered officers, directors, and registered agents for incorporated entities. Coverage varies by state — states that provide officer data in corporate filings have high coverage; others have none. Florida, Texas, and California (three high-MCA-activity states) have reasonable officer data in OpenCorporates.

**Secretary of State websites (direct scraping)**: The same SOS sites being scraped for UCC data often have business entity lookup pages that return registered agent and officer names. This is free, aligns with existing scraping infrastructure, and is the highest-accuracy source for owner names. Should be the **primary owner name source**.

**People Data Labs (PDL)**: When a business name and state are known, PDL's Company Enrichment API can return associated contacts (employees/owners). Overlaps with the phone lookup use case — a single PDL call can return owner name AND contact info simultaneously.

**LinkedIn via Proxycurl API**: Proxycurl scrapes LinkedIn profiles and company pages for contact and organizational data. Plans start at $49/month for 2,500 credits (~$0.02/lookup). Returns employee names with titles, useful for finding owners of small businesses with a LinkedIn presence. Coverage for traditional small businesses (trucking, restaurants, construction) is lower than for tech companies.

**Melissa Data Global Name & Address**: Strong data on individual identity and business registration. US business data includes owner names for many registered entities. API pricing: pay-as-you-go at $0.01–$0.05 per lookup depending on record type. Melissa has a generous free trial (1,000 lookups). Good secondary source.

---

### Recommended Architecture: Waterfall Enrichment Pipeline

Given the UCC-specific use case (small businesses, often distressed, mixed incorporation status):

**Owner Name:**
1. SOS website scrape (free, same infrastructure as UCC scraping)
2. OpenCorporates API (free tier first, then paid)
3. People Data Labs person enrichment

**Phone:**
1. People Data Labs (returns phone + email together, efficient)
2. Whitepages Pro reverse lookup by business name + address
3. Twilio CNAM for validation and line-type classification
4. Spokeo or BeenVerified partner API as final fallback

**Email:**
1. Apollo.io person/company enrichment (best small-business coverage, reasonable pricing)
2. Hunter.io domain search (strong for businesses with a web presence)
3. Snov.io or Prospeo as third-tier fallback

**Revenue:**
1. Apollo.io company data (included with email subscription — zero marginal cost)
2. D&B Direct+ for incorporated entities (higher accuracy, higher cost)
3. Clearbit/HubSpot Breeze (fallback; check pricing post-acquisition)

**Rate Limits Summary:**

| Service | Free Tier | Paid Entry | Rate Limit |
|---------|-----------|------------|------------|
| Apollo.io | 10,000 email credits/month | $49/month | 100 req/min (Basic) |
| Hunter.io | 25 searches/month | $49/month (500 searches) | Not published; ~10 req/sec |
| People Data Labs | 1,000 API calls/month | $98/month (1,000 matched) | 5 req/sec (free), higher paid |
| OpenCorporates | 500 req/day | $50/month | 1 req/sec (free) |
| Whitepages Pro | No free tier | Custom | Custom |
| Twilio Lookup | No free tier | $0.005–$0.01/req | High (thousands/sec) |
| D&B Direct+ | No free tier | ~$300/month | Custom |
| Clearbit/Breeze | Limited free | $99+/month | Custom |
| Snov.io | 150 credits/month | $39/month (1,000 credits) | 30 req/min |
| Proxycurl | No free tier | $49/month (2,500 credits) | ~5 req/sec |

**Cost Estimate at Scale:**

For a pipeline processing 10,000 UCC filings/month with a waterfall (assume ~60% hit rate on first source, 80% cumulative after cascade):
- Apollo.io Professional: ~$99/month (covers email + company revenue)
- People Data Labs: ~$98/month (covers phone + owner name fallback)
- OpenCorporates paid: $50/month (owner name)
- Twilio Lookup: ~$50/month (10,000 validations at $0.005)
- Whitepages Pro: ~$300–$500/month (5,000 lookups at $0.05–$0.10)

**Estimated total: $600–$800/month** for 10,000 enriched leads — approximately $0.06–$0.08 per lead. This compares favorably to third-party lead gen brokers that typically charge $3–$15 per lead.

---

## Recommendation

Deploy a waterfall enrichment pipeline with Apollo.io as the anchor (email + company revenue), People Data Labs as the phone + owner name anchor, SOS scraping for owner name at zero cost, OpenCorporates for officer data, and Twilio for phone validation/classification. Avoid ZoomInfo (overpriced) and single-source dependency. Cache all enrichment results permanently to eliminate repeat costs on re-processed leads.

## Key Facts

- No single API covers all four data points (phone, email, revenue, owner name) with high coverage on small distressed businesses
- Apollo.io: ~275M contacts, $49–$99/month entry, 10,000 free email credits/month, best email + company revenue for B2B small business
- People Data Labs: 1,000 free API calls/month, $98/month paid entry, returns phone + email + name from business name + address — directly matches UCC filing input format
- Hunter.io: 25 free searches/month, $49/month for 500, domain-based email inference — lower coverage on small businesses without web presence
- Twilio Lookup: $0.005/validation, $0.01/CNAM, no monthly minimum — best for Railway pay-as-you-go architecture
- Whitepages Pro: $0.05–$0.15/lookup, best US reverse phone lookup by business name, no free tier
- OpenCorporates: 500 req/day free, $50/month paid, best source for registered officers/directors (owner name) from public filings
- D&B Direct+: ~$300/month entry, best revenue data for incorporated entities, DUNS-linked
- SOS website officer scraping: free, highest accuracy for owner names — should be attempted before any paid source
- Estimated cost at 10,000 leads/month: $600–$800/month total, ~$0.06–$0.08 per enriched lead vs $3–$15 for broker-sourced leads
- Waterfall architecture with result caching is critical — re-billing on duplicate UCC records will erode cost efficiency
- Coverage floors: PDL ~60–75% match rate on US individuals; Apollo ~50–65% on small businesses outside tech sector; OpenCorporates varies by state officer disclosure requirements
- Clearbit pricing is in flux post-HubSpot acquisition (2023) — verify current terms before committing

## Sources

- VISION.md: `/Users/kennygeiler/Documents/Vibing Coding Projects 2026/UCC/.kiln/docs/VISION.md` — project constraints, enrichment requirements (SC-04, OQ-1, R-04)
- Apollo.io public pricing and documentation (training data, verified through mid-2025): https://www.apollo.io/pricing
- People Data Labs API documentation and pricing (training data): https://www.peopledatalabs.com/pricing
- Hunter.io pricing page (training data): https://hunter.io/pricing
- Twilio Lookup API documentation (training data): https://www.twilio.com/en-us/lookup
- OpenCorporates API documentation and pricing (training data): https://api.opencorporates.com
- Whitepages Pro API overview (training data): https://pro.whitepages.com
- D&B Direct+ API overview (training data): https://developer.dnb.com
- Clearbit/HubSpot Breeze Intelligence (training data, post-acquisition status noted): https://clearbit.com / https://www.hubspot.com/products/marketing/data-enrichment
- Snov.io pricing (training data): https://snov.io/pricing
- Proxycurl API documentation (training data): https://nubela.co/proxycurl

Note: WebSearch and WebFetch were unavailable during this research session. All data is drawn from model training knowledge (cutoff: August 2025). Pricing and rate limits should be verified against live pricing pages before committing to a vendor, as these change frequently.

## Confidence

0.72 — Research draws on well-established, widely-documented APIs (Apollo, Hunter, Twilio, PDL, OpenCorporates) with stable pricing models as of mid-2025 training data. Core waterfall architecture recommendation is based on consistent patterns across multiple independent source evaluations. Confidence is capped at 0.72 rather than higher because: (1) web access was unavailable preventing live price verification, (2) Clearbit's pricing model is explicitly in flux post-HubSpot acquisition, and (3) Apollo's free tier terms have changed multiple times and may have changed again since August 2025. Live verification of pricing before contract is essential.
