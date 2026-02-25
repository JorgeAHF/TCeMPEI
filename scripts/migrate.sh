#!/usr/bin/env bash
set -euo pipefail

# Runs Alembic migrations inside backend service container.
docker-compose run --rm backend bash -lc "cd /app && alembic -c alembic.ini upgrade head"
