.PHONY: capture viewer help ip ftp test-ftp

help:
	@echo "Available commands:"
	@echo "  make viewer    - Start the session viewer web UI"
	@echo "  make capture   - Run camera capture (pass args with ARGS='...')"
	@echo "  make ftp       - Start FTP server for camera uploads"
	@echo "  make test-ftp  - Test FTP server connection"
	@echo "  make ip        - Show local IP address for network access"
	@echo ""
	@echo "Examples:"
	@echo "  make viewer"
	@echo "  make capture ARGS='--once'"
	@echo "  make capture ARGS='-f 30 -v N S E W'"
	@echo "  make ftp"
	@echo ""
	@echo "Network Access:"
	@echo "  Run 'make ip' to see your local IP address"
	@echo "  Others on your WiFi can access at http://YOUR_IP:8000"
	@echo "  FTP server runs on port 2121 (configurable in .env)"

ip:
	@echo "Your local IP addresses:"
	@echo ""
	@hostname -I 2>/dev/null || ipconfig getifaddr en0 2>/dev/null || ip addr show | grep "inet " | grep -v 127.0.0.1 | awk '{print $$2}' | cut -d/ -f1
	@echo ""
	@echo "Share http://YOUR_IP:8000 with others on your network"
	@echo "(Replace YOUR_IP with one of the addresses above)"

viewer:
	@echo "Starting viewer on http://0.0.0.0:8000"
	@echo "Local access: http://localhost:8000"
	@echo ""
	@echo "Network access: Find your IP with 'make ip'"
	@echo ""
	@python3 -m app.viewer

capture:
	python3 -m app.capture $(ARGS)

analyzer:
	@echo "Starting Analyzer UI..."
	@echo "Configure in .env file"
	@echo ""
	@python3 -m app.analyzer

ftp:
	@echo "Starting FTP server..."
	@echo "Configure in .env file"
	@echo ""
	@python3 ftp_server/server.py

test-ftp:
	@echo "Testing FTP server connection..."
	@echo "(Make sure FTP server is running first: make ftp)"
	@echo ""
	@python3 ftp_server/test_ftp.py
