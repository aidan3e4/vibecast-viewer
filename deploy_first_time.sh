#!/bin/bash
set -e

echo "=== Vibecast Viewer - First Time Setup ==="
echo ""

# Check fly CLI is installed
if ! command -v fly &> /dev/null; then
    echo "Error: fly CLI not found. Install it from https://fly.io/docs/hands-on/install-flyctl/"
    exit 1
fi

# Load credentials from .env
if [ ! -f .env ]; then
    echo "Error: .env file not found. Expected it at $(pwd)/.env"
    exit 1
fi

echo "Step 1: Authenticating with Fly.io..."
fly auth whoami 2>/dev/null || fly auth login

echo ""
echo "Step 2: Creating app on Fly.io..."
fly apps create vibecast-viewer

echo ""
echo "Step 3: Setting AWS secrets from .env..."
export $(grep -v '^#' .env | xargs)

fly secrets set \
    AWS_ACCESS_KEY_ID="$AWS_ACCESS_KEY_ID" \
    AWS_SECRET_ACCESS_KEY="$AWS_SECRET_ACCESS_KEY"

echo ""
echo "Step 4: Deploying app..."
fly deploy

echo ""
echo "=== First time setup complete ==="
echo "View logs: fly logs"
echo "Open app:  fly open"
