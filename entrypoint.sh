#!/usr/bin/env sh
set -e

# Ensure data dir exists and is writable
mkdir -p /app/data

echo "Timezone: ${TZ:-Europe/Moscow}"
echo "Starting water bot..."
exec python -m app.main