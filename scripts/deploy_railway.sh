#!/usr/bin/env bash
# deploy_railway.sh — Deploy all 3 UCC services to Railway
# Usage: ./scripts/deploy_railway.sh
set -euo pipefail

# ── Colors ──────────────────────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

info()  { echo -e "${CYAN}[INFO]${NC}  $*"; }
ok()    { echo -e "${GREEN}[OK]${NC}    $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }
err()   { echo -e "${RED}[ERROR]${NC} $*" >&2; }

# ── Step 1: Check Railway CLI ──────────────────────────────────────────────
info "Checking Railway CLI..."
if ! command -v railway &>/dev/null; then
    err "Railway CLI not found."
    echo "  Install it:  npm install -g @railway/cli"
    echo "  Or:           brew install railway"
    echo "  Then:         railway login"
    exit 1
fi
ok "Railway CLI found: $(railway version 2>/dev/null || echo 'unknown version')"

# Verify login
if ! railway whoami &>/dev/null; then
    err "Not logged in to Railway. Run: railway login"
    exit 1
fi
ok "Logged in to Railway."

# ── Step 2: Project setup ──────────────────────────────────────────────────
info "Checking for linked Railway project..."
if ! railway status &>/dev/null 2>&1; then
    warn "No Railway project linked."
    read -rp "Create a new Railway project? (y/N): " create_project
    if [[ "${create_project,,}" == "y" ]]; then
        info "Creating new Railway project 'ucc-pipeline'..."
        railway init --name ucc-pipeline
        ok "Project created."
    else
        err "Link an existing project first: railway link"
        exit 1
    fi
else
    ok "Railway project is linked."
fi

# ── Step 3: Provision Postgres ─────────────────────────────────────────────
info "Provisioning Postgres plugin..."
info "(If Postgres already exists, Railway will reuse it.)"
railway add --plugin postgresql || warn "Postgres may already be provisioned — continuing."
ok "Postgres plugin ready. DATABASE_URL will be auto-linked."

# ── Step 4: Set required environment variables ─────────────────────────────
info "Configuring environment variables..."

# Helper: prompt for a var if not already set in Railway
set_var_if_missing() {
    local var_name="$1"
    local description="$2"
    local is_required="${3:-true}"

    # Check if already set
    existing=$(railway variables get "$var_name" 2>/dev/null || echo "")
    if [[ -n "$existing" && "$existing" != "null" ]]; then
        ok "$var_name is already set."
        return
    fi

    # Check local .env file
    if [[ -f .env ]]; then
        local_val=$(grep -E "^${var_name}=" .env 2>/dev/null | head -1 | cut -d= -f2- || echo "")
        if [[ -n "$local_val" ]]; then
            read -rp "  Found $var_name in .env. Use it? (Y/n): " use_local
            if [[ "${use_local,,}" != "n" ]]; then
                railway variables set "$var_name=$local_val"
                ok "$var_name set from .env"
                return
            fi
        fi
    fi

    # Prompt user
    if [[ "$is_required" == "true" ]]; then
        echo -e "  ${YELLOW}$var_name${NC} — $description"
        read -rp "  Enter value: " value
        if [[ -z "$value" ]]; then
            err "$var_name is required. Aborting."
            exit 1
        fi
        railway variables set "$var_name=$value"
        ok "$var_name set."
    else
        echo -e "  ${YELLOW}$var_name${NC} (optional) — $description"
        read -rp "  Enter value (or press Enter to skip): " value
        if [[ -n "$value" ]]; then
            railway variables set "$var_name=$value"
            ok "$var_name set."
        else
            warn "$var_name skipped."
        fi
    fi
}

# Required vars
set_var_if_missing "SENTRY_DSN"       "Sentry DSN for error tracking"         true
set_var_if_missing "GHL_API_KEY"      "GoHighLevel API key"                   true
set_var_if_missing "GHL_LOCATION_ID"  "GoHighLevel location/sub-account ID"   true
set_var_if_missing "PDL_API_KEY"      "People Data Labs API key"              true

# Optional but recommended
set_var_if_missing "ANTHROPIC_API_KEY"  "Anthropic API key (self-healing agent)" false
set_var_if_missing "SENDGRID_API_KEY"   "SendGrid API key (watchdog alerts)"    false
set_var_if_missing "MANAGER_EMAIL"      "Alert recipient email address"         false

echo ""
ok "Environment variables configured."

# ── Step 5: Deploy all services ────────────────────────────────────────────
info "Deploying to Railway..."
railway up --detach
ok "Deployment triggered."

info "Waiting for deployment to start..."
sleep 5

# ── Step 6: Run database migrations ───────────────────────────────────────
info "Running Alembic migrations..."
railway run alembic upgrade head
ok "Database migrations complete."

# ── Step 7: Print service URLs ─────────────────────────────────────────────
echo ""
echo -e "${GREEN}═══════════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}  Deployment complete!${NC}"
echo -e "${GREEN}═══════════════════════════════════════════════════════════════${NC}"
echo ""
info "Service URLs:"
railway domain 2>/dev/null || true
echo ""
info "View your services in the Railway dashboard:"
echo "  https://railway.app/dashboard"
echo ""
info "Useful commands:"
echo "  railway logs                  — View logs"
echo "  railway logs --service agent  — View agent logs"
echo "  railway run alembic upgrade head — Run migrations"
echo "  railway status                — Check deployment status"
echo ""
ok "Done! Your UCC pipeline is live."
