#!/bin/bash
set -e

echo "=== Vibecast Viewer - Redeploy ==="
echo ""

# Check fly CLI is installed
if ! command -v fly &> /dev/null; then
    echo "Error: fly CLI not found. Install it from https://fly.io/docs/hands-on/install-flyctl/"
    exit 1
fi

fly deploy

echo ""
echo "=== Redeploy complete ==="
echo "View logs: fly logs"
echo "Open app:  fly open"
