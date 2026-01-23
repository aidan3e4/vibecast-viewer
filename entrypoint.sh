#!/bin/bash
set -e

echo "Starting FTP Server on port 2121..."
make ftp & FTP_PID=$!

echo "Starting Analyzer UI on port 8001..."
make analyzer & ANALYZER_PID=$!

echo "Services started:"
echo "  - FTP Server (PID: $FTP_PID)"
echo "  - Analyzer UI (PID: $ANALYZER_PID)"
echo ""
echo "Access the Analyzer UI at http://localhost:8001"
echo "FTP Server listening on port 2121"
echo ""

# Wait for both processes
wait -n

# Exit with status of first process to exit
exit $?
