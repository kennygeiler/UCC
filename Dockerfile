# UCC platform image — Python 3.12 + Playwright Chromium for browser-based Tier 1 scrapers.
# All three Railway services (web / agent / watchdog) share this image; per-service
# start commands come from railway.toml. Chromium is only exercised by the pipeline
# scrapers, but baking it in keeps a single reproducible image for every service.

FROM python:3.12-slim

WORKDIR /app

# Source first so the editable install resolves the app/agent/watchdog packages.
COPY . .

# Install the package, then Chromium plus its OS dependencies for Playwright.
# `--with-deps` runs apt-get for the system libraries Chromium needs; the Docker
# build runs as root so this succeeds without extra configuration.
RUN pip install --no-cache-dir -e . \
    && playwright install --with-deps chromium

# Default to the pipeline service; Railway overrides per service via railway.toml.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
