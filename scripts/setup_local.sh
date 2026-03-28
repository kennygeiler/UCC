#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

export DATABASE_URL="postgresql+asyncpg://ucc:ucc_local@localhost:5432/ucc_dev"

echo "==> Starting Postgres via docker-compose..."
docker compose up -d postgres

echo "==> Waiting for Postgres to be healthy..."
until docker compose exec postgres pg_isready -U ucc -d ucc_dev > /dev/null 2>&1; do
    sleep 1
done
echo "    Postgres is ready."

# Copy .env.example → .env if .env doesn't exist
if [ ! -f .env ]; then
    echo "==> Creating .env from .env.example..."
    cp .env.example .env
else
    echo "==> .env already exists, skipping copy."
fi

# Set DATABASE_URL in .env (replace existing or append)
if grep -q '^DATABASE_URL=' .env; then
    sed -i.bak "s|^DATABASE_URL=.*|DATABASE_URL=${DATABASE_URL}|" .env && rm -f .env.bak
    echo "==> Updated DATABASE_URL in .env"
else
    echo "DATABASE_URL=${DATABASE_URL}" >> .env
    echo "==> Appended DATABASE_URL to .env"
fi

echo "==> Installing project in editable mode with dev extras..."
python3.12 -m pip install -e '.[dev]'

echo "==> Running Alembic migrations..."
python3.12 -m alembic upgrade head

echo "==> Seeding MCA aliases..."
python3.12 -c "
import asyncio
from sqlalchemy import select
from app.db import get_session
from app.models.mca_alias import MCAlias
from app.mca.seed_data import KNOWN_MCA_LENDERS

async def seed():
    async with get_session() as session:
        for entry in KNOWN_MCA_LENDERS:
            exists = await session.execute(
                select(MCAlias).where(MCAlias.alias_name == entry['alias_name'])
            )
            if exists.scalar_one_or_none() is None:
                session.add(MCAlias(**entry))
        count = (await session.execute(select(MCAlias))).scalars().all()
        print(f'    Seeded {len(count)} MCA aliases total.')

asyncio.run(seed())
"

echo ""
echo "========================================"
echo "  Local dev environment ready!"
echo "========================================"
echo ""
echo "  Postgres : localhost:5432"
echo "  Database : ucc_dev"
echo "  User     : ucc"
echo "  Password : ucc_local"
echo ""
echo "  DATABASE_URL=${DATABASE_URL}"
echo ""
echo "  Useful commands:"
echo "    docker compose logs -f postgres   # view Postgres logs"
echo "    docker compose down               # stop Postgres"
echo "    docker compose down -v            # stop & delete data"
echo "    alembic upgrade head              # re-run migrations"
echo ""
