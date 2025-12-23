#!/usr/bin/env bash
set -euo pipefail

# Creates data folders and applies schema to a local Postgres reachable via DATABASE_URL.

DATA_ROOT="${DATA_ROOT:-$(pwd)/data}"
echo "Using DATA_ROOT=${DATA_ROOT}"
mkdir -p "${DATA_ROOT}/raw" "${DATA_ROOT}/normalized" "${DATA_ROOT}/attachments"

if [[ -z "${DATABASE_URL:-}" ]]; then
  echo "DATABASE_URL not set; skipping schema apply."
  exit 0
fi

echo "Applying schema..."
psql "${DATABASE_URL}" -f backend/app/db/schema.sql
echo "Done."
