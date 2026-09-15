#!/usr/bin/env bash
set -euo pipefail

# NanoCoop Automated Docker Compose Test Suite
# Validates the entire application end-to-end with secure DB background in Docker.

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

echo "=================================================="
echo "🐳 Starting NanoCoop Dockerized Integration Tests"
echo "=================================================="

# Tear down previous test containers and volumes
docker compose -f docker-compose.test.yml down -v --remove-orphans || true

# Build and execute tests, exiting with e2e-tester's status
docker compose -f docker-compose.test.yml up --build --abort-on-container-exit --exit-code-from e2e-tester

# Cleanup
docker compose -f docker-compose.test.yml down -v

echo "=================================================="
echo "✅ All Docker Compose tests passed successfully!"
echo "=================================================="
