# Deploying UCC to Railway

This guide walks you through deploying the UCC lead-generation pipeline to [Railway](https://railway.app). No DevOps experience required.

## What Gets Deployed

| Service | Purpose | Port |
|---------|---------|------|
| **Pipeline** (web) | Dashboard, webhooks, scraping pipeline | 8000 |
| **Agent** | Self-healing LangGraph agent (monitors & repairs the pipeline) | 8001 |
| **Watchdog** | Independent deadman-switch that alerts if the agent goes down | 8002 |

All three services share a single Postgres database provisioned automatically by Railway.

---

## Prerequisites

1. **A Railway account** — sign up at [railway.app](https://railway.app) (free tier works to start)
2. **Railway CLI** — install one of these ways:
   ```bash
   npm install -g @railway/cli    # via npm
   brew install railway            # via Homebrew (macOS)
   ```
3. **API keys** you will need:
   - **Sentry DSN** — from [sentry.io](https://sentry.io) (create a Python project)
   - **GoHighLevel API key + Location ID** — from your GHL sub-account settings
   - **People Data Labs API key** — from [peopledatalabs.com](https://peopledatalabs.com)
   - *(Optional)* Anthropic API key — enables the self-healing agent
   - *(Optional)* SendGrid API key + manager email — enables watchdog email alerts

---

## Option A: Automated Deploy Script

The fastest way. Run from the project root:

```bash
# 1. Log in to Railway
railway login

# 2. Run the deploy script
chmod +x scripts/deploy_railway.sh
./scripts/deploy_railway.sh
```

The script will:
- Create a Railway project (or use your linked one)
- Provision a Postgres database
- Prompt you for each required API key
- Deploy all 3 services
- Run database migrations
- Print your service URLs

---

## Option B: Manual Step-by-Step

### 1. Log in to Railway

```bash
railway login
```

This opens your browser to authenticate.

### 2. Create a project

```bash
railway init --name ucc-pipeline
```

### 3. Add Postgres

```bash
railway add --plugin postgresql
```

Railway automatically sets `DATABASE_URL` for you — no configuration needed.

### 4. Set environment variables

Set each variable one at a time:

```bash
railway variables set "SENTRY_DSN=https://your-sentry-dsn-here"
railway variables set "GHL_API_KEY=your-ghl-api-key"
railway variables set "GHL_LOCATION_ID=your-ghl-location-id"
railway variables set "PDL_API_KEY=your-pdl-api-key"
```

Optional (recommended):

```bash
railway variables set "ANTHROPIC_API_KEY=your-key"
railway variables set "SENDGRID_API_KEY=your-key"
railway variables set "MANAGER_EMAIL=you@example.com"
```

### 5. Deploy

```bash
railway up --detach
```

### 6. Run database migrations

```bash
railway run alembic upgrade head
```

### 7. Check your services

```bash
railway logs
railway status
```

Visit the [Railway dashboard](https://railway.app/dashboard) to see your services running.

---

## After Deployment

### Viewing logs

```bash
railway logs                     # all services
railway logs --service agent     # just the agent
railway logs --service watchdog  # just the watchdog
```

### Running migrations after code changes

```bash
railway run alembic upgrade head
```

### Redeploying after code changes

Push to your linked branch, or run:

```bash
railway up --detach
```

### Adding a custom domain

In the Railway dashboard, click on your pipeline service, go to **Settings > Domains**, and add your domain.

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| `railway: command not found` | Install CLI: `npm install -g @railway/cli` |
| `Not logged in` | Run `railway login` |
| Services crash on startup | Check logs: `railway logs`. Usually a missing env var. |
| Database connection errors | Verify Postgres plugin is provisioned: check Railway dashboard |
| Health check failing | Service may still be starting — Railway allows 5 min (300s) for startup |
| Watchdog sending false alerts | Agent may be slow to start. Check agent logs first. |

---

## Environment Variable Reference

| Variable | Required | Description |
|----------|----------|-------------|
| `DATABASE_URL` | Yes | Auto-set by Railway Postgres plugin |
| `SENTRY_DSN` | Yes | Sentry error tracking DSN |
| `GHL_API_KEY` | Yes | GoHighLevel API key |
| `GHL_LOCATION_ID` | Yes | GoHighLevel sub-account location ID |
| `PDL_API_KEY` | Yes | People Data Labs enrichment API key |
| `ANTHROPIC_API_KEY` | No | Enables AI-powered self-healing agent |
| `SENDGRID_API_KEY` | No | Enables watchdog email alerts |
| `MANAGER_EMAIL` | No | Email address for watchdog alerts |
| `PROXY_URL` | No | Proxy for Tier-3 rate-limited states |
| `APOLLO_API_KEY` | No | Apollo.io enrichment (backup) |
| `TWILIO_ACCOUNT_SID` | No | Twilio phone validation |
| `TWILIO_AUTH_TOKEN` | No | Twilio auth |
| `GITHUB_TOKEN` | No | Agent GitHub integration |
| `GITHUB_REPO` | No | Target repo for agent PRs |
