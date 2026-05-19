#!/usr/bin/env python3
"""Local web dashboard for the UCC lead-gen pipeline.

Replaces the terminal e2e script with a browser UI.
Start with:  .venv/bin/python scripts/dashboard_local.py
Then open:   http://localhost:8080
"""

import asyncio
import json
import os
import subprocess
import sys
import traceback
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# Bootstrap: load .env from project root before any app imports
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv

load_dotenv(PROJECT_ROOT / ".env")

# SENTRY_DSN optional — pipeline skips Sentry init when unset

# ---------------------------------------------------------------------------
# Now safe to import app modules
# ---------------------------------------------------------------------------
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from sqlalchemy import func, select
import uvicorn

from app.db import get_session
from app.models.filing import UCCFiling
from app.models.lead import Lead
from app.models.operations import ScraperRun
from app.scrapers.registry import SCRAPER_REGISTRY

# ---------------------------------------------------------------------------
# State for active pipeline runs (in-memory, single-process)
# ---------------------------------------------------------------------------
pipeline_runs: dict[str, dict] = {}

# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Run alembic migrations on startup
    print("Running alembic migrations...")
    result = subprocess.run(
        ["alembic", "upgrade", "head"],
        capture_output=True, text=True, timeout=60,
        cwd=str(PROJECT_ROOT),
    )
    if result.returncode != 0:
        print(f"WARN: Alembic migration issue: {result.stderr.strip()}")
    else:
        print("Migrations applied.")
    yield


app = FastAPI(title="UCC Pipeline Dashboard", lifespan=lifespan)

# ---------------------------------------------------------------------------
# All 40 states sorted, with tier info
# ---------------------------------------------------------------------------
STATES = sorted(SCRAPER_REGISTRY.keys())
STATE_TIERS = {k: v["tier"] for k, v in SCRAPER_REGISTRY.items()}

# ---------------------------------------------------------------------------
# Config keys to check
# ---------------------------------------------------------------------------
CONFIG_KEYS = {
    "Core": ["DATABASE_URL", "SENTRY_DSN"],
    "GoHighLevel": [
        "GHL_API_KEY", "GHL_LOCATION_ID", "GHL_WEBHOOK_SECRET",
        "GHL_WORKFLOW_TIER1", "GHL_WORKFLOW_TIER2", "GHL_WORKFLOW_TIER3",
    ],
    "Enrichment": [
        "PDL_API_KEY", "APOLLO_API_KEY", "OPENCORPORATES_API_KEY",
        "WHITEPAGES_API_KEY", "TWILIO_ACCOUNT_SID", "TWILIO_AUTH_TOKEN",
    ],
    "Compliance": ["DATAMERCH_API_KEY", "DNC_SCRUB_API_KEY", "BLACKLIST_API_KEY"],
    "Other": [
        "PROXY_URL", "ANTHROPIC_API_KEY", "GITHUB_TOKEN", "GITHUB_REPO",
        "SENDGRID_API_KEY", "MANAGER_EMAIL",
    ],
}


# ===================================================================
# HTML TEMPLATES
# ===================================================================

def page_shell(content: str, active_tab: str = "pipeline") -> str:
    tabs = [
        ("pipeline", "Pipeline", "/"),
        ("leads", "Leads", "/leads"),
        ("scrapers", "Scrapers", "/scrapers"),
        ("config", "Config", "/config"),
    ]
    tab_html = ""
    for tid, label, href in tabs:
        active_cls = "border-indigo-500 text-indigo-600" if tid == active_tab else "border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300"
        tab_html += f'<a href="{href}" class="whitespace-nowrap py-4 px-1 border-b-2 font-medium text-sm {active_cls}">{label}</a>'

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>UCC Pipeline Dashboard</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script src="https://unpkg.com/htmx.org@2.0.4"></script>
    <script src="https://unpkg.com/htmx-ext-sse@2.2.2/sse.js"></script>
    <style>
        [hx-indicator] .htmx-indicator {{ display: none; }}
        [hx-indicator].htmx-request .htmx-indicator {{ display: inline-block; }}
        .fade-in {{ animation: fadeIn 0.3s ease-in; }}
        @keyframes fadeIn {{ from {{ opacity: 0; }} to {{ opacity: 1; }} }}
        .pulse {{ animation: pulse 1.5s infinite; }}
        @keyframes pulse {{ 0%, 100% {{ opacity: 1; }} 50% {{ opacity: 0.5; }} }}
    </style>
</head>
<body class="bg-gray-50 min-h-screen">
    <nav class="bg-white shadow-sm border-b border-gray-200">
        <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            <div class="flex justify-between h-16">
                <div class="flex items-center">
                    <div class="flex-shrink-0 flex items-center">
                        <span class="text-xl font-bold text-gray-900">UCC Pipeline</span>
                        <span class="ml-2 text-xs font-medium bg-indigo-100 text-indigo-700 px-2 py-0.5 rounded-full">Local</span>
                    </div>
                    <div class="ml-10 flex space-x-8">
                        {tab_html}
                    </div>
                </div>
                <div class="flex items-center text-xs text-gray-400">
                    {datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")}
                </div>
            </div>
        </div>
    </nav>
    <main class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {content}
    </main>
</body>
</html>"""


def status_badge(status: str) -> str:
    colors = {
        "pending": "bg-yellow-100 text-yellow-800",
        "complete": "bg-green-100 text-green-800",
        "cleared": "bg-green-100 text-green-800",
        "exported": "bg-blue-100 text-blue-800",
        "running": "bg-blue-100 text-blue-800",
        "completed": "bg-green-100 text-green-800",
        "failed": "bg-red-100 text-red-800",
        "retry_queued": "bg-orange-100 text-orange-800",
    }
    # Handle blocked:* statuses
    if status and status.startswith("blocked"):
        color = "bg-red-100 text-red-800"
    else:
        color = colors.get(status or "pending", "bg-gray-100 text-gray-800")
    return f'<span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium {color}">{status or "—"}</span>'


def tier_badge(tier: int) -> str:
    colors = {1: "bg-red-100 text-red-700", 2: "bg-yellow-100 text-yellow-700", 3: "bg-gray-100 text-gray-600"}
    return f'<span class="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium {colors.get(tier, "bg-gray-100 text-gray-600")}">Tier {tier}</span>'


# ===================================================================
# ROUTES
# ===================================================================

@app.get("/", response_class=HTMLResponse)
async def pipeline_page():
    state_options = ""
    for s in STATES:
        tier = STATE_TIERS[s]
        state_options += f'<option value="{s}">{s} (Tier {tier})</option>'

    content = f"""
    <div class="space-y-6">
        <!-- Run Pipeline Card -->
        <div class="bg-white shadow rounded-lg p-6">
            <h2 class="text-lg font-semibold text-gray-900 mb-4">Run Pipeline</h2>
            <div class="flex items-end gap-4">
                <div>
                    <label for="state" class="block text-sm font-medium text-gray-700 mb-1">State</label>
                    <select id="state-select" class="block w-40 rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 text-sm px-3 py-2 border">
                        {state_options}
                    </select>
                </div>
                <div>
                    <label class="flex items-center gap-2 text-sm text-gray-700">
                        <input type="checkbox" id="dry-run-check" class="rounded border-gray-300 text-indigo-600 focus:ring-indigo-500">
                        Dry run
                    </label>
                </div>
                <button
                    id="run-btn"
                    onclick="startPipeline()"
                    class="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md text-white bg-indigo-600 hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500 transition-colors"
                >
                    <svg class="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z"></path><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg>
                    Run Pipeline
                </button>
            </div>
        </div>

        <!-- Progress Card -->
        <div id="progress-card" class="hidden bg-white shadow rounded-lg p-6">
            <h2 class="text-lg font-semibold text-gray-900 mb-4">Progress</h2>
            <div id="progress-stages" class="space-y-3"></div>
        </div>

        <!-- Results Card -->
        <div id="results-card" class="hidden bg-white shadow rounded-lg p-6">
            <h2 class="text-lg font-semibold text-gray-900 mb-4">Results</h2>
            <div id="results-content"></div>
        </div>
    </div>

    <script>
    let eventSource = null;

    function startPipeline() {{
        const state = document.getElementById('state-select').value;
        const dryRun = document.getElementById('dry-run-check').checked;
        const btn = document.getElementById('run-btn');

        // Disable button
        btn.disabled = true;
        btn.classList.add('opacity-50', 'cursor-not-allowed');
        btn.innerHTML = '<svg class="animate-spin w-4 h-4 mr-2" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path></svg> Running...';

        // Show progress card, hide results
        document.getElementById('progress-card').classList.remove('hidden');
        document.getElementById('results-card').classList.add('hidden');
        document.getElementById('progress-stages').innerHTML = '';

        // Start SSE
        if (eventSource) eventSource.close();
        eventSource = new EventSource(`/api/run?state=${{state}}&dry_run=${{dryRun}}`);

        eventSource.addEventListener('stage', function(e) {{
            const data = JSON.parse(e.data);
            updateStage(data);
        }});

        eventSource.addEventListener('complete', function(e) {{
            const data = JSON.parse(e.data);
            showResults(data);
            eventSource.close();
            eventSource = null;
            btn.disabled = false;
            btn.classList.remove('opacity-50', 'cursor-not-allowed');
            btn.innerHTML = '<svg class="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z"></path><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg> Run Pipeline';
        }});

        eventSource.addEventListener('error_msg', function(e) {{
            const data = JSON.parse(e.data);
            const stages = document.getElementById('progress-stages');
            stages.innerHTML += `<div class="flex items-center gap-3 text-red-600"><svg class="w-5 h-5" fill="currentColor" viewBox="0 0 20 20"><path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clip-rule="evenodd"></path></svg><span class="text-sm font-medium">${{data.error}}</span></div>`;
            eventSource.close();
            eventSource = null;
            btn.disabled = false;
            btn.classList.remove('opacity-50', 'cursor-not-allowed');
            btn.innerHTML = '<svg class="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z"></path><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg> Run Pipeline';
        }});

        eventSource.onerror = function() {{
            eventSource.close();
            eventSource = null;
            btn.disabled = false;
            btn.classList.remove('opacity-50', 'cursor-not-allowed');
            btn.innerHTML = '<svg class="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z"></path><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg> Run Pipeline';
        }};
    }}

    function updateStage(data) {{
        const stages = document.getElementById('progress-stages');
        const existingStage = document.getElementById('stage-' + data.stage_num);

        let icon = '';
        let textColor = '';
        if (data.status === 'running') {{
            icon = '<div class="w-5 h-5 rounded-full border-2 border-indigo-500 border-t-transparent animate-spin"></div>';
            textColor = 'text-indigo-600';
        }} else if (data.status === 'done') {{
            icon = '<svg class="w-5 h-5 text-green-500" fill="currentColor" viewBox="0 0 20 20"><path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clip-rule="evenodd"></path></svg>';
            textColor = 'text-green-700';
        }} else if (data.status === 'skipped') {{
            icon = '<svg class="w-5 h-5 text-gray-400" fill="currentColor" viewBox="0 0 20 20"><path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM7 9a1 1 0 000 2h6a1 1 0 100-2H7z" clip-rule="evenodd"></path></svg>';
            textColor = 'text-gray-500';
        }} else if (data.status === 'error') {{
            icon = '<svg class="w-5 h-5 text-red-500" fill="currentColor" viewBox="0 0 20 20"><path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clip-rule="evenodd"></path></svg>';
            textColor = 'text-red-600';
        }}

        const html = `<div id="stage-${{data.stage_num}}" class="flex items-center gap-3 fade-in">
            ${{icon}}
            <div class="flex-1">
                <span class="text-sm font-medium ${{textColor}}">Stage ${{data.stage_num}}: ${{data.name}}</span>
                ${{data.detail ? `<span class="ml-2 text-xs text-gray-500">${{data.detail}}</span>` : ''}}
            </div>
        </div>`;

        if (existingStage) {{
            existingStage.outerHTML = html;
        }} else {{
            stages.innerHTML += html;
        }}
    }}

    function showResults(data) {{
        document.getElementById('results-card').classList.remove('hidden');
        const rc = document.getElementById('results-content');
        const s = data.summary;

        let leadsHtml = '';
        if (data.leads && data.leads.length > 0) {{
            leadsHtml = `
            <div class="mt-6">
                <h3 class="text-sm font-semibold text-gray-700 mb-2">Lead Details</h3>
                <div class="overflow-x-auto">
                    <table class="min-w-full divide-y divide-gray-200 text-sm">
                        <thead class="bg-gray-50">
                            <tr>
                                <th class="px-4 py-2 text-left font-medium text-gray-500">Debtor</th>
                                <th class="px-4 py-2 text-left font-medium text-gray-500">Score</th>
                                <th class="px-4 py-2 text-left font-medium text-gray-500">Tier</th>
                                <th class="px-4 py-2 text-left font-medium text-gray-500">Positions</th>
                                <th class="px-4 py-2 text-left font-medium text-gray-500">Enrichment</th>
                                <th class="px-4 py-2 text-left font-medium text-gray-500">Compliance</th>
                                <th class="px-4 py-2 text-left font-medium text-gray-500">Export</th>
                            </tr>
                        </thead>
                        <tbody class="divide-y divide-gray-200">
                            ${{data.leads.map((l, i) => `
                                <tr class="cursor-pointer hover:bg-gray-50" onclick="toggleDetail(this, ${{i}})">
                                    <td class="px-4 py-2 font-medium text-gray-900">${{l.debtor_name}}</td>
                                    <td class="px-4 py-2">${{l.lead_score != null ? l.lead_score.toFixed(1) : '—'}}</td>
                                    <td class="px-4 py-2">${{l.tier || '—'}}</td>
                                    <td class="px-4 py-2">${{l.mca_position_count != null ? l.mca_position_count : '—'}}</td>
                                    <td class="px-4 py-2">${{l.enrichment_status || '—'}}</td>
                                    <td class="px-4 py-2">${{l.compliance_status || '—'}}</td>
                                    <td class="px-4 py-2">${{l.export_status || '—'}}</td>
                                </tr>
                                <tr id="detail-${{i}}" class="hidden bg-gray-50">
                                    <td colspan="7" class="px-4 py-3">
                                        <div class="grid grid-cols-2 gap-2 text-xs text-gray-600">
                                            <div><strong>State:</strong> ${{l.state}}</div>
                                            <div><strong>Phone:</strong> ${{l.phone || '—'}}</div>
                                            <div><strong>Email:</strong> ${{l.email || '—'}}</div>
                                            <div><strong>Owner:</strong> ${{l.owner_name || '—'}}</div>
                                            <div><strong>Revenue:</strong> ${{l.estimated_revenue ? '$' + l.estimated_revenue.toLocaleString() : '—'}}</div>
                                            <div><strong>GHL ID:</strong> ${{l.ghl_contact_id || '—'}}</div>
                                        </div>
                                    </td>
                                </tr>
                            `).join('')}}
                        </tbody>
                    </table>
                </div>
            </div>`;
        }}

        rc.innerHTML = `
        <div class="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div class="bg-gray-50 rounded-lg p-4 text-center">
                <div class="text-2xl font-bold text-gray-900">${{s.filings_scraped}}</div>
                <div class="text-xs text-gray-500 mt-1">Filings Scraped</div>
            </div>
            <div class="bg-gray-50 rounded-lg p-4 text-center">
                <div class="text-2xl font-bold text-gray-900">${{s.leads_detected}}</div>
                <div class="text-xs text-gray-500 mt-1">Leads Detected</div>
            </div>
            <div class="bg-gray-50 rounded-lg p-4 text-center">
                <div class="text-2xl font-bold text-gray-900">${{s.leads_scored}}</div>
                <div class="text-xs text-gray-500 mt-1">Leads Scored</div>
            </div>
            <div class="bg-gray-50 rounded-lg p-4 text-center">
                <div class="text-2xl font-bold text-gray-900">${{s.leads_enriched}}</div>
                <div class="text-xs text-gray-500 mt-1">Leads Enriched</div>
            </div>
            <div class="bg-gray-50 rounded-lg p-4 text-center">
                <div class="text-2xl font-bold ${{s.leads_compliant > 0 ? 'text-green-600' : 'text-gray-900'}}">${{s.leads_compliant}}</div>
                <div class="text-xs text-gray-500 mt-1">Compliant</div>
            </div>
            <div class="bg-gray-50 rounded-lg p-4 text-center">
                <div class="text-2xl font-bold ${{s.leads_blocked > 0 ? 'text-red-600' : 'text-gray-900'}}">${{s.leads_blocked}}</div>
                <div class="text-xs text-gray-500 mt-1">Blocked</div>
            </div>
            <div class="bg-gray-50 rounded-lg p-4 text-center">
                <div class="text-2xl font-bold text-blue-600">${{s.leads_exported}}</div>
                <div class="text-xs text-gray-500 mt-1">Exported</div>
            </div>
            <div class="bg-gray-50 rounded-lg p-4 text-center">
                <div class="text-sm font-semibold text-gray-700">${{s.export_method || '—'}}</div>
                <div class="text-xs text-gray-500 mt-1">Export Method</div>
            </div>
        </div>
        ${{leadsHtml}}
        `;
    }}

    function toggleDetail(row, idx) {{
        const detail = document.getElementById('detail-' + idx);
        detail.classList.toggle('hidden');
    }}
    </script>
    """
    return HTMLResponse(page_shell(content, "pipeline"))


# ===================================================================
# Pipeline SSE endpoint
# ===================================================================

@app.get("/api/run")
async def run_pipeline_sse(state: str = "CA", dry_run: bool = False):
    state = state.upper()

    async def event_stream():
        summary = {
            "filings_scraped": 0, "leads_detected": 0, "leads_scored": 0,
            "leads_enriched": 0, "leads_compliant": 0, "leads_blocked": 0,
            "leads_exported": 0, "export_method": None,
        }
        lead_dicts = []

        def sse(event: str, data: dict) -> str:
            return f"event: {event}\ndata: {json.dumps(data)}\n\n"

        try:
            # Stage 1: Scrape
            yield sse("stage", {"stage_num": 1, "name": "Scrape", "status": "running", "detail": f"Scraping {state}..."})
            try:
                from app.scrapers.registry import get_scraper_class
                scraper_class = get_scraper_class(state)
                if scraper_class is None:
                    yield sse("stage", {"stage_num": 1, "name": "Scrape", "status": "error", "detail": f"No scraper for {state}"})
                    yield sse("error_msg", {"error": f"No scraper registered for state '{state}'"})
                    return
                scraper = scraper_class()
                count = await scraper.scrape()
                summary["filings_scraped"] = count
                yield sse("stage", {"stage_num": 1, "name": "Scrape", "status": "done", "detail": f"{count} filings"})
            except Exception as exc:
                yield sse("stage", {"stage_num": 1, "name": "Scrape", "status": "error", "detail": str(exc)[:100]})
                yield sse("error_msg", {"error": f"Scrape failed: {exc}"})
                return

            # Stage 2: Detect
            yield sse("stage", {"stage_num": 2, "name": "MCA Detection", "status": "running", "detail": "Analyzing filings..."})
            try:
                from app.mca.detector import detect_mca, check_collateral_keywords

                async with get_session() as session:
                    result = await session.execute(
                        select(UCCFiling).where(UCCFiling.state == state)
                    )
                    filings = list(result.scalars().all())

                detected = []
                for f in filings:
                    is_mca, canonical, confidence, _match_type = await detect_mca(
                        f.secured_party, f.collateral_description
                    )
                    if is_mca:
                        detected.append({
                            "debtor_name": f.debtor_name,
                            "state": f.state,
                            "filing_date": f.filing_date,
                            "secured_party": canonical,
                            "confidence": confidence,
                            "has_mca_collateral": check_collateral_keywords(f.collateral_description),
                            "filing_id": f.id,
                        })
                summary["leads_detected"] = len(detected)
                yield sse("stage", {"stage_num": 2, "name": "MCA Detection", "status": "done", "detail": f"{len(detected)} leads"})
            except Exception as exc:
                yield sse("stage", {"stage_num": 2, "name": "MCA Detection", "status": "error", "detail": str(exc)[:100]})
                yield sse("error_msg", {"error": f"Detection failed: {exc}"})
                return

            if not detected:
                yield sse("stage", {"stage_num": 3, "name": "Score", "status": "skipped", "detail": "No leads to score"})
                yield sse("stage", {"stage_num": 4, "name": "Enrich", "status": "skipped", "detail": "No leads"})
                yield sse("stage", {"stage_num": 5, "name": "Compliance", "status": "skipped", "detail": "No leads"})
                yield sse("stage", {"stage_num": 6, "name": "Export", "status": "skipped", "detail": "No leads"})
                yield sse("complete", {"summary": summary, "leads": []})
                return

            # Stage 3: Score
            yield sse("stage", {"stage_num": 3, "name": "Score", "status": "running", "detail": f"Scoring {len(detected)} leads..."})
            try:
                from app.mca.scorer import score_lead

                scored = []
                for lead in detected:
                    result = await score_lead(
                        debtor_name=lead["debtor_name"],
                        state=lead["state"],
                        filing_date=lead["filing_date"],
                        has_mca_collateral=lead["has_mca_collateral"],
                    )
                    lead.update(result)
                    scored.append(lead)
                scored.sort(key=lambda x: x["lead_score"], reverse=True)
                summary["leads_scored"] = len(scored)
                yield sse("stage", {"stage_num": 3, "name": "Score", "status": "done", "detail": f"{len(scored)} scored"})
            except Exception as exc:
                yield sse("stage", {"stage_num": 3, "name": "Score", "status": "error", "detail": str(exc)[:100]})
                yield sse("error_msg", {"error": f"Scoring failed: {exc}"})
                return

            # Create lead records in DB
            leads = []
            async with get_session() as session:
                for s in scored:
                    lead = Lead(
                        debtor_name=s["debtor_name"],
                        state=s["state"],
                        lead_score=s["lead_score"],
                        mca_position_count=s["mca_position_count"],
                        enrichment_status="pending",
                        compliance_status="pending",
                        export_status="pending",
                    )
                    session.add(lead)
                    await session.flush()
                    leads.append(lead)

            # Stage 4: Enrich
            if dry_run:
                yield sse("stage", {"stage_num": 4, "name": "Enrich", "status": "skipped", "detail": "Dry run"})
            elif not os.environ.get("PDL_API_KEY"):
                yield sse("stage", {"stage_num": 4, "name": "Enrich", "status": "skipped", "detail": "PDL_API_KEY not set"})
            else:
                yield sse("stage", {"stage_num": 4, "name": "Enrich", "status": "running", "detail": "Enriching top 5..."})
                try:
                    from app.enrichment.pipeline import build_enrichment_waterfall, enrich_lead

                    waterfall = build_enrichment_waterfall()
                    enriched = 0
                    for lead in leads[:5]:
                        try:
                            ok = await enrich_lead(lead, waterfall)
                            if ok:
                                enriched += 1
                        except Exception:
                            pass
                    summary["leads_enriched"] = enriched
                    yield sse("stage", {"stage_num": 4, "name": "Enrich", "status": "done", "detail": f"{enriched} enriched"})
                except Exception as exc:
                    yield sse("stage", {"stage_num": 4, "name": "Enrich", "status": "error", "detail": str(exc)[:100]})

            # Stage 5: Compliance
            yield sse("stage", {"stage_num": 5, "name": "Compliance", "status": "running", "detail": "Running compliance gate..."})
            try:
                from app.compliance.gate import run_compliance_gate

                passed = blocked = 0
                for lead in leads:
                    try:
                        ok = await run_compliance_gate(lead)
                        if ok:
                            passed += 1
                        else:
                            blocked += 1
                    except Exception:
                        passed += 1  # fail-open for unconfigured layers
                summary["leads_compliant"] = passed
                summary["leads_blocked"] = blocked
                yield sse("stage", {"stage_num": 5, "name": "Compliance", "status": "done", "detail": f"{passed} passed, {blocked} blocked"})
            except Exception as exc:
                yield sse("stage", {"stage_num": 5, "name": "Compliance", "status": "error", "detail": str(exc)[:100]})

            # Stage 6: Export
            if dry_run:
                yield sse("stage", {"stage_num": 6, "name": "Export", "status": "skipped", "detail": "Dry run"})
                summary["export_method"] = "skipped (dry-run)"
            else:
                yield sse("stage", {"stage_num": 6, "name": "Export", "status": "running", "detail": "Exporting..."})
                try:
                    ghl_key = os.environ.get("GHL_API_KEY")
                    if ghl_key:
                        from app.export.ghl_adapter import GHLAdapter
                        adapter = GHLAdapter()
                        method = "GHL"
                    else:
                        from app.export.csv_fallback import CSVFallbackAdapter
                        adapter = CSVFallbackAdapter()
                        method = "CSV"

                    exported = 0
                    for lead in leads:
                        if lead.compliance_status != "cleared":
                            continue
                        lead_data = {
                            "phone": lead.phone,
                            "email": lead.email,
                            "owner_name": lead.owner_name,
                            "debtor_name": lead.debtor_name,
                            "tier": "hot" if (lead.mca_position_count or 0) >= 3
                                   else "warm" if (lead.mca_position_count or 0) == 2
                                   else "cold",
                        }
                        try:
                            await adapter.upsert_lead(lead_data)
                            exported += 1
                        except Exception:
                            pass
                    summary["leads_exported"] = exported
                    summary["export_method"] = method
                    yield sse("stage", {"stage_num": 6, "name": "Export", "status": "done", "detail": f"{exported} via {method}"})
                except Exception as exc:
                    yield sse("stage", {"stage_num": 6, "name": "Export", "status": "error", "detail": str(exc)[:100]})

            # Re-read leads from DB to get final state
            lead_ids = [l.id for l in leads]
            async with get_session() as session:
                result = await session.execute(
                    select(Lead).where(Lead.id.in_(lead_ids))
                )
                final_leads = list(result.scalars().all())

            lead_dicts = [
                {
                    "debtor_name": l.debtor_name,
                    "state": l.state,
                    "lead_score": l.lead_score,
                    "mca_position_count": l.mca_position_count,
                    "tier": "hot" if (l.mca_position_count or 0) >= 3
                           else "warm" if (l.mca_position_count or 0) == 2
                           else "cold",
                    "phone": l.phone,
                    "email": l.email,
                    "owner_name": l.owner_name,
                    "estimated_revenue": l.estimated_revenue,
                    "enrichment_status": l.enrichment_status,
                    "compliance_status": l.compliance_status,
                    "export_status": l.export_status,
                    "ghl_contact_id": l.ghl_contact_id,
                }
                for l in final_leads
            ]

            yield sse("complete", {"summary": summary, "leads": lead_dicts})

        except Exception as exc:
            yield sse("error_msg", {"error": f"Pipeline error: {traceback.format_exc()}"})

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ===================================================================
# Leads tab
# ===================================================================

@app.get("/leads", response_class=HTMLResponse)
async def leads_page(
    status: str = "",
    state: str = "",
    page: int = 1,
):
    per_page = 50
    offset = (page - 1) * per_page

    async with get_session() as session:
        query = select(Lead).order_by(Lead.id.desc())
        count_query = select(func.count(Lead.id))

        if status:
            if status == "blocked":
                query = query.where(Lead.compliance_status.like("blocked%"))
                count_query = count_query.where(Lead.compliance_status.like("blocked%"))
            elif status == "detected":
                query = query.where(
                    Lead.enrichment_status == "pending",
                    Lead.compliance_status == "pending",
                )
                count_query = count_query.where(
                    Lead.enrichment_status == "pending",
                    Lead.compliance_status == "pending",
                )
            elif status == "scored":
                query = query.where(Lead.lead_score.isnot(None))
                count_query = count_query.where(Lead.lead_score.isnot(None))
            elif status == "enriched":
                query = query.where(Lead.enrichment_status == "complete")
                count_query = count_query.where(Lead.enrichment_status == "complete")
            elif status == "compliant":
                query = query.where(Lead.compliance_status == "cleared")
                count_query = count_query.where(Lead.compliance_status == "cleared")
            elif status == "exported":
                query = query.where(Lead.export_status == "exported")
                count_query = count_query.where(Lead.export_status == "exported")

        if state:
            query = query.where(Lead.state == state.upper())
            count_query = count_query.where(Lead.state == state.upper())

        total_result = await session.execute(count_query)
        total = total_result.scalar() or 0

        result = await session.execute(query.offset(offset).limit(per_page))
        leads = list(result.scalars().all())

    # Status filter buttons
    statuses = [
        ("", "All"),
        ("detected", "Detected"),
        ("scored", "Scored"),
        ("enriched", "Enriched"),
        ("compliant", "Compliant"),
        ("exported", "Exported"),
        ("blocked", "Blocked"),
    ]
    filter_html = ""
    for val, label in statuses:
        active = "bg-indigo-100 text-indigo-700 border-indigo-300" if val == status else "bg-white text-gray-700 border-gray-300 hover:bg-gray-50"
        filter_html += f'<a href="/leads?status={val}&state={state}" class="px-3 py-1.5 text-xs font-medium rounded-md border {active}">{label}</a>'

    # State filter
    state_filter = f"""<select onchange="window.location='/leads?status={status}&state='+this.value" class="text-xs border border-gray-300 rounded-md px-2 py-1.5">
        <option value="">All States</option>"""
    for s in STATES:
        sel = 'selected' if s == state.upper() else ''
        state_filter += f'<option value="{s}" {sel}>{s}</option>'
    state_filter += "</select>"

    # Table rows
    rows = ""
    for l in leads:
        tier_val = "hot" if (l.mca_position_count or 0) >= 3 else "warm" if (l.mca_position_count or 0) == 2 else "cold"
        tier_colors = {"hot": "text-red-600", "warm": "text-yellow-600", "cold": "text-blue-600"}
        rows += f"""<tr class="hover:bg-gray-50">
            <td class="px-4 py-3 text-sm font-medium text-gray-900">{l.debtor_name}</td>
            <td class="px-4 py-3 text-sm text-gray-500">{l.state}</td>
            <td class="px-4 py-3 text-sm text-gray-500">{l.lead_score or '—'}</td>
            <td class="px-4 py-3 text-sm {tier_colors.get(tier_val, '')}">{tier_val}</td>
            <td class="px-4 py-3 text-sm">{status_badge(l.enrichment_status)}</td>
            <td class="px-4 py-3 text-sm">{status_badge(l.compliance_status)}</td>
            <td class="px-4 py-3 text-sm">{status_badge(l.export_status)}</td>
            <td class="px-4 py-3 text-sm text-gray-500">{l.phone or '—'}</td>
            <td class="px-4 py-3 text-sm text-gray-500">{l.email or '—'}</td>
        </tr>"""

    if not leads:
        rows = '<tr><td colspan="9" class="px-4 py-8 text-center text-sm text-gray-500">No leads found</td></tr>'

    # Pagination
    total_pages = max(1, (total + per_page - 1) // per_page)
    pagination = ""
    if total_pages > 1:
        pagination = '<div class="flex items-center justify-between px-4 py-3 border-t border-gray-200">'
        pagination += f'<div class="text-xs text-gray-500">Showing {offset+1}-{min(offset+per_page, total)} of {total}</div>'
        pagination += '<div class="flex gap-2">'
        if page > 1:
            pagination += f'<a href="/leads?status={status}&state={state}&page={page-1}" class="px-3 py-1 text-xs border rounded hover:bg-gray-50">Prev</a>'
        if page < total_pages:
            pagination += f'<a href="/leads?status={status}&state={state}&page={page+1}" class="px-3 py-1 text-xs border rounded hover:bg-gray-50">Next</a>'
        pagination += '</div></div>'

    content = f"""
    <div class="space-y-4">
        <div class="flex items-center justify-between">
            <h1 class="text-lg font-semibold text-gray-900">Leads <span class="text-sm font-normal text-gray-500">({total} total)</span></h1>
            <div class="flex items-center gap-3">
                {state_filter}
                <div class="flex gap-1">{filter_html}</div>
            </div>
        </div>
        <div class="bg-white shadow rounded-lg overflow-hidden">
            <table class="min-w-full divide-y divide-gray-200">
                <thead class="bg-gray-50">
                    <tr>
                        <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Debtor</th>
                        <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">State</th>
                        <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Score</th>
                        <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Tier</th>
                        <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Enrichment</th>
                        <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Compliance</th>
                        <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Export</th>
                        <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Phone</th>
                        <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Email</th>
                    </tr>
                </thead>
                <tbody class="divide-y divide-gray-200">{rows}</tbody>
            </table>
            {pagination}
        </div>
    </div>
    """
    return HTMLResponse(page_shell(content, "leads"))


# ===================================================================
# Scrapers tab
# ===================================================================

@app.get("/scrapers", response_class=HTMLResponse)
async def scrapers_page():
    # Get latest scraper run per state
    async with get_session() as session:
        # Subquery for latest run per state
        latest_subq = (
            select(
                ScraperRun.state,
                func.max(ScraperRun.id).label("max_id"),
            )
            .group_by(ScraperRun.state)
            .subquery()
        )
        result = await session.execute(
            select(ScraperRun)
            .join(latest_subq, ScraperRun.id == latest_subq.c.max_id)
            .order_by(ScraperRun.state)
        )
        latest_runs = {r.state: r for r in result.scalars().all()}

        # Filing counts per state
        filing_counts_result = await session.execute(
            select(UCCFiling.state, func.count(UCCFiling.id))
            .group_by(UCCFiling.state)
        )
        filing_counts = dict(filing_counts_result.all())

    rows = ""
    for state_code in STATES:
        tier = STATE_TIERS[state_code]
        run = latest_runs.get(state_code)
        count = filing_counts.get(state_code, 0)

        if run:
            last_run_time = run.started_at.strftime("%Y-%m-%d %H:%M") if run.started_at else "—"
            run_status = run.status
            records = run.records_found if run.records_found is not None else "—"
            error = run.error_detail[:60] + "..." if run.error_detail and len(run.error_detail) > 60 else (run.error_detail or "")
        else:
            last_run_time = "Never"
            run_status = "—"
            records = "—"
            error = ""

        rows += f"""<tr class="hover:bg-gray-50">
            <td class="px-4 py-3 text-sm font-medium text-gray-900">{state_code}</td>
            <td class="px-4 py-3 text-sm">{tier_badge(tier)}</td>
            <td class="px-4 py-3 text-sm text-gray-500">{last_run_time}</td>
            <td class="px-4 py-3 text-sm">{status_badge(run_status) if run_status != '—' else '—'}</td>
            <td class="px-4 py-3 text-sm text-gray-500">{records}</td>
            <td class="px-4 py-3 text-sm text-gray-900 font-medium">{count:,}</td>
            <td class="px-4 py-3 text-sm text-red-500">{error}</td>
        </tr>"""

    content = f"""
    <div class="space-y-4">
        <h1 class="text-lg font-semibold text-gray-900">Scrapers <span class="text-sm font-normal text-gray-500">({len(STATES)} states)</span></h1>
        <div class="bg-white shadow rounded-lg overflow-hidden">
            <table class="min-w-full divide-y divide-gray-200">
                <thead class="bg-gray-50">
                    <tr>
                        <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">State</th>
                        <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Tier</th>
                        <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Last Run</th>
                        <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Status</th>
                        <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Records Found</th>
                        <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Total Filings</th>
                        <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Error</th>
                    </tr>
                </thead>
                <tbody class="divide-y divide-gray-200">{rows}</tbody>
            </table>
        </div>
    </div>
    """
    return HTMLResponse(page_shell(content, "scrapers"))


# ===================================================================
# Config tab
# ===================================================================

@app.get("/config", response_class=HTMLResponse)
async def config_page():
    sections = ""
    for section_name, keys in CONFIG_KEYS.items():
        rows = ""
        for key in keys:
            val = os.environ.get(key)
            if val:
                badge = '<span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-800">Configured</span>'
                preview = val[:4] + "..." + val[-4:] if len(val) > 12 else "***"
                preview_html = f'<span class="text-xs text-gray-400 font-mono">{preview}</span>'
            else:
                badge = '<span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-gray-100 text-gray-500">Missing</span>'
                preview_html = ""

            rows += f"""<tr class="hover:bg-gray-50">
                <td class="px-4 py-2.5 text-sm font-mono text-gray-900">{key}</td>
                <td class="px-4 py-2.5 text-sm">{badge}</td>
                <td class="px-4 py-2.5 text-sm">{preview_html}</td>
            </tr>"""

        configured = sum(1 for k in keys if os.environ.get(k))
        sections += f"""
        <div class="bg-white shadow rounded-lg overflow-hidden">
            <div class="px-4 py-3 bg-gray-50 border-b border-gray-200 flex items-center justify-between">
                <h3 class="text-sm font-semibold text-gray-700">{section_name}</h3>
                <span class="text-xs text-gray-500">{configured}/{len(keys)} configured</span>
            </div>
            <table class="min-w-full divide-y divide-gray-200">
                <tbody class="divide-y divide-gray-100">{rows}</tbody>
            </table>
        </div>"""

    env_file_status = ""
    env_path = PROJECT_ROOT / ".env"
    if env_path.exists():
        env_file_status = '<span class="text-xs text-green-600">Loaded from ' + str(env_path) + '</span>'
    else:
        env_file_status = '<span class="text-xs text-yellow-600">No .env file found at ' + str(env_path) + '</span>'

    content = f"""
    <div class="space-y-4">
        <div class="flex items-center justify-between">
            <h1 class="text-lg font-semibold text-gray-900">Configuration</h1>
            {env_file_status}
        </div>
        <div class="space-y-4">{sections}</div>
    </div>
    """
    return HTMLResponse(page_shell(content, "config"))


# ===================================================================
# API endpoints for HTMX partial updates
# ===================================================================

@app.get("/api/stats", response_class=HTMLResponse)
async def api_stats():
    """Quick stats for the dashboard header."""
    async with get_session() as session:
        leads_total = (await session.execute(select(func.count(Lead.id)))).scalar() or 0
        filings_total = (await session.execute(select(func.count(UCCFiling.id)))).scalar() or 0
    return HTMLResponse(f"""
        <span class="text-sm text-gray-500">{filings_total:,} filings | {leads_total:,} leads</span>
    """)


# ===================================================================
# Entry point
# ===================================================================

if __name__ == "__main__":
    import webbrowser

    print("=" * 50)
    print("  UCC Pipeline Dashboard")
    print(f"  http://localhost:8080")
    print("=" * 50)

    # Open browser after a short delay
    def open_browser():
        import time
        time.sleep(1.5)
        webbrowser.open("http://localhost:8080")

    import threading
    threading.Thread(target=open_browser, daemon=True).start()

    uvicorn.run(app, host="0.0.0.0", port=8080, log_level="info")
