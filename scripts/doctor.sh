#!/usr/bin/env bash
# NanoCoop System Health & Environment Doctor
set -euo pipefail

echo "=================================================="
echo "           NanoCoop System Doctor                 "
echo "=================================================="

# Check Node.js
if command -v node >/dev/null 2>&1; then
    NODE_VER=$(node -v)
    echo "✓ Node.js detected: $NODE_VER"
else
    echo "✗ Node.js not found. Please install Node.js 20+."
fi

# Check npm
if command -v npm >/dev/null 2>&1; then
    NPM_VER=$(npm -v)
    echo "✓ npm detected: v$NPM_VER"
else
    echo "✗ npm not found."
fi

# Check uv
if command -v uv >/dev/null 2>&1; then
    UV_VER=$(uv --version)
    echo "✓ uv detected: $UV_VER"
else
    echo "✗ Astral uv not found. Install with: curl -LsSf https://astral.sh/uv/install.sh | sh"
fi

# Check Python 3.12
if command -v python3 >/dev/null 2>&1; then
    PY_VER=$(python3 -V)
    echo "✓ Python detected: $PY_VER"
else
    echo "✗ Python 3 not found."
fi

# Check Docker
if command -v docker >/dev/null 2>&1; then
    DOCKER_VER=$(docker --version)
    echo "✓ Docker detected: $DOCKER_VER"
else
    echo "⚠ Docker not detected (optional, required for containerized testing)."
fi

# Check Port 8000
if lsof -i :8000 >/dev/null 2>&1; then
    echo "⚠ Port 8000 is currently occupied (Backend Core default port)."
else
    echo "✓ Port 8000 is available for Core Backend."
fi

# Check Port 3000
if lsof -i :3000 >/dev/null 2>&1; then
    echo "⚠ Port 3000 is currently occupied (Teller Web default port)."
else
    echo "✓ Port 3000 is available for Teller Web."
fi

# Check .env
if [ -f ".env" ]; then
    echo "✓ .env file present."
else
    echo "ℹ .env file not found. Created from .env.example template."
    cp .env.example .env
fi

echo "=================================================="
echo "System ready to run NanoCoop!"
echo "Commands to get started:"
echo "  npm run dev:core    # Start Core Python backend"
echo "  npm run dev:teller  # Start Expo Teller Web app"
echo "  npm run dev         # Start complete local cluster"
echo "=================================================="
