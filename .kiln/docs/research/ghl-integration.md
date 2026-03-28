# GoHighLevel Integration — CSV Import, API, Dispositions, Campaign Management

## Finding

### 1. CSV Import Format

GoHighLevel's contact import accepts a CSV file with a flexible column mapping step during the import wizard. GHL does not enforce rigid column headers — it presents a field-mapping screen where the user or automation matches source columns to GHL's internal contact fields. However, the following field names are natively recognized and map directly without manual intervention when column headers match exactly:

**Standard contact fields (recognized column headers):**
- `first_name` / `First Name`
- `last_name` / `Last Name`
- `email` / `Email`
- `phone` / `Phone` (E.164 format recommended: `+15551234567`)
- `address1` / `Address`
- `city` / `City`
- `state` / `State`
- `postal_code` / `Zip`
- `country` / `Country` (ISO 2-letter code: `US`)
- `company_name` / `Company Name`
- `website` / `Website`
- `tags` (comma-separated tag list in one cell, e.g. `"hot-lead,mca-debt,tier-1"`)
- `source` / `Source`
- `date_of_birth`
- Custom fields: referenced by their internal label or slug (configured per sub-account)

**Key data constraints:**
- Phone numbers must be valid and preferably in E.164 format; GHL attempts normalization but malformed numbers will be silently skipped or flagged during import review.
- Duplicate detection during CSV import is based on email OR phone match (configurable at import time — deduplicate by email, by phone, or both).
- Tags column accepts a quoted, comma-separated string: `"hot-lead,tier-1,mca-debt"`.
- Maximum recommended batch size per CSV import is 10,000 contacts; larger files should be split.
- Custom field columns must match the exact label defined in the sub-account's custom fields settings (Settings > Custom Fields).
- Import assigns contacts to a single GHL pipeline stage if a `pipeline_stage` column is provided (though this requires the internal stage ID, not the display name, via API — not available in CSV wizard directly).

**For this project, recommended CSV columns:**
```
first_name, last_name, company_name, phone, email, address1, city, state, postal_code,
tags, source, ucc_filing_date, ucc_filing_state, lead_score, mca_position_count,
estimated_revenue, owner_name, campaign_tier
```
Custom fields (ucc_filing_date, lead_score, etc.) must be pre-created in GHL before import.

---

### 2. API Capabilities — Contact/Lead Upload

GoHighLevel offers a **REST API v2** (the current production API as of 2024-2025, replacing the deprecated v1). It is the recommended integration path for programmatic lead upload and is fully capable of replacing CSV import for this use case.

**Authentication:**
- OAuth 2.0 with scopes (for SaaS/marketplace apps) — preferred for multi-location setups.
- Private Integration API keys (location-level or agency-level) — simpler for single-location internal tools. Generated under Settings > Integrations > API Keys.
- Bearer token passed in `Authorization: Bearer {token}` header on every request.

**Key API endpoints for lead pipeline integration:**

| Operation | Endpoint | Method |
|---|---|---|
| Create contact | `/contacts/` | POST |
| Update contact | `/contacts/{contactId}` | PUT |
| Upsert contact (by email/phone) | `/contacts/upsert` | POST |
| Get contact | `/contacts/{contactId}` | GET |
| Search contacts | `/contacts/search` | GET |
| Add tags | `/contacts/{contactId}/tags` | POST |
| Add to campaign | `/contacts/{contactId}/campaigns/{campaignId}` | POST |
| Add to workflow | `/contacts/{contactId}/workflow/{workflowId}` | POST |
| Get opportunities (pipeline) | `/opportunities/search` | GET |
| Update opportunity | `/opportunities/{opportunityId}` | PUT |

**Rate limits (GHL API v2 as of 2024-2025):**
- **100 requests per 10 seconds** per location (sub-account). This is the standard published limit.
- Exceeding the limit returns HTTP 429 with `Retry-After` header.
- For bulk lead imports, implement exponential backoff and batch processing at 80-90 req/10s to stay safely under limit.
- For this project's expected load (hundreds to low thousands of leads per run, not millions), the rate limit is not a practical constraint.

**Upsert behavior:**
The `/contacts/upsert` endpoint is the correct approach for this pipeline. It creates a new contact if no match on email/phone is found, or updates the existing contact if a match exists. This handles deduplication at the API layer. The body accepts:
```json
{
  "locationId": "string",
  "firstName": "string",
  "lastName": "string",
  "email": "string",
  "phone": "string",
  "companyName": "string",
  "address1": "string",
  "city": "string",
  "state": "string",
  "postalCode": "string",
  "tags": ["hot-lead", "tier-1", "mca-debt"],
  "source": "ucc-pipeline",
  "customFields": [
    { "id": "custom_field_id", "value": "field_value" }
  ]
}
```

**Adding to campaigns/workflows via API:**
After creating/upserting a contact, add them to a campaign or workflow with a second API call:
- `POST /contacts/{contactId}/campaigns/{campaignId}` — adds to a legacy campaign.
- `POST /contacts/{contactId}/workflow/{workflowId}` — adds to a workflow (preferred in GHL's current architecture; workflows replaced most campaign functionality).

This two-call pattern (upsert contact → add to workflow) is the standard API-driven lead injection pattern for GHL.

---

### 3. Disposition / Outcome Feedback Mechanisms

This is the most architecturally complex piece of the integration. GHL does not have a single dedicated "disposition" field — feedback from reps is captured through a combination of mechanisms:

**A. Opportunity Pipeline Stages (Primary mechanism):**
GHL's pipeline (CRM view) is the primary location where rep dispositions live. When a rep changes a lead's stage (e.g., "New Lead" → "Contacted" → "Not Interested" / "Closed Won"), this is the closest analog to a disposition.

- **API polling**: `GET /opportunities/search?locationId={id}&pipelineId={id}` returns all opportunities with their current stage. Poll on a schedule (e.g., every 30 minutes) to detect stage changes and sync back to the pipeline database.
- **Webhooks (preferred)**: GHL supports outbound webhooks for opportunity stage changes. Under Settings > Integrations > Webhooks, configure a webhook endpoint that GHL will POST to whenever an opportunity moves stages. Payload includes contactId, opportunityId, old stage, new stage, and timestamp. This is real-time and eliminates polling overhead.

**B. Custom Contact Fields (Disposition tagging):**
Reps can update a custom field (e.g., "Disposition" dropdown: `interested`, `not_interested_now`, `dnc_requested`, `callback_scheduled`, `closed_won`, `closed_lost`). This is readable via the contact GET API and watchable via contact-update webhooks.

**C. Tags (Simple disposition signals):**
Reps or GHL automations can add/remove tags on contacts. A tag like `recycling-eligible` or `30-day-cooldown` can be written by a GHL workflow trigger and read back via API. Tags are the most flexible low-code feedback mechanism.

**D. GHL Webhooks — Complete event list relevant to this pipeline:**
- `ContactCreate` — contact created
- `ContactUpdate` — contact field or tag changed (fires when rep updates disposition field)
- `OpportunityCreate` — opportunity created
- `OpportunityUpdate` — stage change, value change (primary disposition signal)
- `TaskComplete` — rep completed a follow-up task
- `NoteCreate` — rep added a call note
- `AppointmentCreate` / `AppointmentUpdate` — booking events

**Recommended disposition feedback architecture for this project:**
1. Configure GHL outbound webhook to POST `OpportunityUpdate` and `ContactUpdate` events to a `/webhooks/ghl` endpoint in this pipeline's API.
2. Map GHL pipeline stages to internal disposition codes:
   - `New Lead` → `exported_to_ghl`
   - `Contacted` → `contacted`
   - `Not Interested` → `not_interested` (recycle after 30-day cooldown)
   - `Callback` → `callback_pending`
   - `Closed Won` → `won` (suppress permanently)
   - `Closed Lost` → `lost` (recycle after 60-day cooldown)
   - Any tag `dnc-requested` → `dnc` (suppress permanently, add to internal DNC list)
3. Webhook handler writes disposition back to the lead record in the pipeline database.
4. Lead recycling job queries for records with appropriate disposition + cooldown elapsed and re-queues them.

---

### 4. Campaign Management — Tiered Lead Routing

GHL supports tiered campaign execution through a combination of workflows, tags, and pipeline assignments.

**Recommended tiered routing pattern:**
- **Tier 1 — Hot leads** (multiple MCA positions, high score): Tagged `tier-1` and added to a GHL workflow that routes to the top-closer team, with immediate SMS + email + call task assignment to a specific user group.
- **Tier 2 — Warm leads** (1-2 positions, medium score): Tagged `tier-2` and added to a standard workflow with multi-touch sequence.
- **Tier 3 — Cold leads**: Tagged `tier-3` and added to a drip workflow with longer delay sequences.

**API implementation for tiered routing:**
```
1. Upsert contact with tier tag set (POST /contacts/upsert)
2. Based on tier, add to the corresponding workflow:
   - Tier 1 → POST /contacts/{id}/workflow/{hot-workflow-id}
   - Tier 2 → POST /contacts/{id}/workflow/{warm-workflow-id}
   - Tier 3 → POST /contacts/{id}/workflow/{cold-workflow-id}
```

The workflow IDs are stable GHL identifiers that the manager configures once in GHL. The pipeline stores a config mapping (tier → workflowId) so the manager can update routing in GHL without touching the pipeline code.

---

### 5. Platform-Agnostic Architecture — Abstraction Layer

The project's stated goal is to architect for GHL today but allow swapping the campaign platform without rebuilding the pipeline. The correct pattern is an **Outbound Adapter** (also called a Campaign Platform Adapter).

**Adapter interface (TypeScript-style pseudocode):**
```typescript
interface CampaignPlatformAdapter {
  // Push a qualified lead to the campaign platform
  upsertLead(lead: QualifiedLead): Promise<ExternalLeadId>;

  // Route a lead into the appropriate campaign/workflow
  enrollInCampaign(externalId: ExternalLeadId, tier: LeadTier): Promise<void>;

  // Pull disposition updates since a given timestamp (polling fallback)
  getDispositionUpdates(since: Date): Promise<DispositionUpdate[]>;

  // Register a webhook endpoint URL (called during setup/config)
  registerWebhook(callbackUrl: string, events: WebhookEvent[]): Promise<void>;

  // Parse an inbound webhook payload into a normalized DispositionUpdate
  parseWebhookPayload(rawPayload: unknown): DispositionUpdate | null;
}
```

**Concrete implementations:**
- `GHLAdapter` — implements the above using GHL API v2 endpoints.
- `HubSpotAdapter`, `CloseAdapter`, `SalesforceAdapter` — future swaps, same interface.

**Pipeline code never calls GHL directly.** It calls `adapter.upsertLead(...)` and `adapter.enrollInCampaign(...)`. The adapter resolves which GHL endpoints, authentication headers, and payload shapes to use. Swapping platforms = swapping the adapter implementation, not touching the pipeline.

**Config structure for GHL adapter:**
```json
{
  "platform": "ghl",
  "locationId": "abc123",
  "apiKey": "env:GHL_API_KEY",
  "workflowIds": {
    "tier1": "wf_hot_leads_id",
    "tier2": "wf_warm_leads_id",
    "tier3": "wf_cold_leads_id"
  },
  "webhookSecret": "env:GHL_WEBHOOK_SECRET",
  "dispositionStageMap": {
    "New Lead": "exported_to_ghl",
    "Contacted": "contacted",
    "Not Interested": "not_interested",
    "Closed Won": "won",
    "Closed Lost": "lost"
  }
}
```

---

## Recommendation

Use the GHL API v2 (not CSV upload) as the primary integration path — specifically the `/contacts/upsert` + `/contacts/{id}/workflow/{workflowId}` two-call pattern for lead injection and tiered routing. Implement GHL outbound webhooks for real-time disposition feedback rather than polling. Wrap all GHL calls behind a `CampaignPlatformAdapter` interface from day one so the platform can be swapped without touching pipeline logic. The CSV export path should be retained only as a manual fallback mechanism.

---

## Key Facts

- GHL API v2 base URL: `https://services.leadconnectorhq.com` (also accessible at `https://rest.gohighlevel.com/v2/` — both are valid)
- Authentication: Bearer token via Private Integration Key or OAuth 2.0
- Rate limit: 100 requests per 10 seconds per location (sub-account)
- Upsert endpoint: `POST /contacts/upsert` — creates or updates on email/phone match
- Workflow enrollment: `POST /contacts/{contactId}/workflow/{workflowId}`
- Webhook events for dispositions: `OpportunityUpdate`, `ContactUpdate`
- CSV import: flexible column mapping wizard; max recommended batch ~10,000 rows; E.164 phone format preferred
- Tags in CSV: quoted comma-separated string in a single `tags` column
- Custom fields must be pre-created in GHL sub-account before import or API write
- GHL refers to "campaigns" and "workflows" somewhat interchangeably in UI; the API distinguishes them — workflows are the modern path (post-2023)
- No native "disposition" field; reps signal outcomes via pipeline stage changes, custom fields, or tags
- Webhooks are configured under Settings > Integrations > Webhooks in the GHL sub-account
- The adapter abstraction layer is a standard outbound adapter / anti-corruption layer pattern; no GHL-specific libraries required
- Lead recycling requires storing the GHL contactId and externalOpportunityId on each lead record so webhook payloads can be correlated back to internal lead records

---

## Sources

- GHL API v2 Official Documentation: https://highlevel.stoplight.io/docs/integrations/ (referenced from training data, August 2025 cutoff)
- GHL Help Center — Import Contacts from CSV: https://help.gohighlevel.com/support/solutions/articles/48001185670 (training data)
- GHL Developer Community — Webhooks reference: https://help.gohighlevel.com/support/solutions/articles/48001208243 (training data)
- GHL API v2 Contacts endpoint specification: https://highlevel.stoplight.io/docs/integrations/85477c882cc53-create-contact (training data)
- Project VISION.md — constraints, goals, and integration decisions: /Users/kennygeiler/Documents/Vibing Coding Projects 2026/UCC/.kiln/docs/VISION.md (direct read)
- Martin Fowler — Anti-Corruption Layer / Adapter pattern (architectural reference, well-established pattern)

**Note on source access:** WebSearch and WebFetch were unavailable in this research session. All GHL-specific technical claims are drawn from training data (knowledge cutoff August 2025). The GHL API v2 was stable and well-documented through that date. Rate limits and endpoint paths should be verified against the live GHL developer docs before implementation. The adapter abstraction pattern is independent of GHL versioning risk.

---

## Confidence

0.72 — GHL API v2 was stable, well-documented, and widely used through the August 2025 knowledge cutoff; core endpoint structure, authentication model, rate limits, and webhook patterns are well-established. Confidence is not higher because (a) web verification tools were unavailable so live documentation could not be confirmed, and (b) GHL occasionally updates endpoint paths and rate limit policies between minor versions. The architectural patterns (adapter layer, upsert+workflow pattern, webhook-based disposition feedback) are sound regardless of minor GHL API changes.
