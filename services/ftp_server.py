#!/usr/bin/env python3
"""
FTP Server for Reolink Camera Uploads

A simple FTP server that accepts uploads from Reolink cameras.
Designed to run on cloud servers (e.g., runpod) and be accessible from the internet.
"""

import os
import sys
from pathlib import Path
from pyftpdlib.authorizers import DummyAuthorizer
from pyftpdlib.handlers import FTPHandler
from pyftpdlib.servers import FTPServer
from dotenv import load_dotenv
import logging

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

load_dotenv()

# Configuration from environment variables
FTP_USER = os.environ.get("FTP_USER", "reolink")
FTP_PASSWORD = os.environ.get("FTP_PASSWORD", "camera123")
FTP_PORT = int(os.environ.get("FTP_PORT", "2121"))
FTP_HOST = os.environ.get("FTP_HOST", "0.0.0.0")  # 0.0.0.0 to accept connections from anywhere
FTP_UPLOAD_DIR = Path(os.environ.get("FTP_UPLOAD_DIR", "./ftp_uploads"))
FTP_MAX_CONS = int(os.environ.get("FTP_MAX_CONS", "256"))
FTP_MAX_CONS_PER_IP = int(os.environ.get("FTP_MAX_CONS_PER_IP", "5"))

# Permissions
# "elradfmwMT" means:
# e = change directory (CWD, CDUP commands)
# l = list files (LIST, NLST, STAT, MLSD, MLST, SIZE commands)
# r = retrieve file from the server (RETR command)
# a = append data to an existing file (APPE command)
# d = delete file or directory (DELE, RMD commands)
# f = rename file or directory (RNFR, RNTO commands)
# m = create directory (MKD command)
# w = store a file to the server (STOR, STOU commands)
# M = change file mode/permission (SITE CHMOD command)
# T = change file modification time (SITE MTIME command)
FTP_PERMISSIONS = os.environ.get("FTP_PERMISSIONS", "elradfmwMT")


class CustomFTPHandler(FTPHandler):
    """Custom FTP handler with additional logging."""

    def on_connect(self):
        """Called when client connects."""
        logger.info(f"Client connected: {self.remote_ip}:{self.remote_port}")

    def on_disconnect(self):
        """Called when client disconnects."""
        logger.info(f"Client disconnected: {self.remote_ip}:{self.remote_port}")

    def on_login(self, username):
        """Called when client logs in."""
        logger.info(f"User '{username}' logged in from {self.remote_ip}")

    def on_logout(self, username):
        """Called when client logs out."""
        logger.info(f"User '{username}' logged out")

    def on_file_sent(self, file):
        """Called when file is successfully sent."""
        logger.info(f"File sent: {file}")

    def on_file_received(self, file):
        """Called when file is successfully received."""
        logger.info(f"File received: {file}")

    def on_incomplete_file_sent(self, file):
        """Called when file transmission is incomplete."""
        logger.warning(f"Incomplete file sent: {file}")

    def on_incomplete_file_received(self, file):
        """Called when file reception is incomplete."""
        logger.warning(f"Incomplete file received: {file}")


def setup_ftp_server():
    """Setup and configure the FTP server."""

    # Create upload directory if it doesn't exist
    FTP_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

    # Instantiate a dummy authorizer for managing 'virtual' users
    authorizer = DummyAuthorizer()

    # Define a new user with full permissions
    authorizer.add_user(
        FTP_USER,
        FTP_PASSWORD,
        str(FTP_UPLOAD_DIR.absolute()),
        perm=FTP_PERMISSIONS
    )

    # Instantiate FTP handler class
    handler = CustomFTPHandler
    handler.authorizer = authorizer

    # Define a customized banner
    handler.banner = "Vibecast FTP Server ready."

    # Optionally set passive ports range
    # handler.passive_ports = range(60000, 60100)

    # Instantiate FTP server class and listen on FTP_HOST:FTP_PORT
    address = (FTP_HOST, FTP_PORT)
    server = FTPServer(address, handler)

    # Set connection limits
    server.max_cons = FTP_MAX_CONS
    server.max_cons_per_ip = FTP_MAX_CONS_PER_IP

    return server


def main():
    """Main function to start the FTP server."""
    logger.info("=" * 70)
    logger.info("Starting Vibecast FTP Server")
    logger.info("=" * 70)
    logger.info(f"Host: {FTP_HOST}")
    logger.info(f"Port: {FTP_PORT}")
    logger.info(f"Upload directory: {FTP_UPLOAD_DIR.absolute()}")
    logger.info(f"Username: {FTP_USER}")
    logger.info(f"Max connections: {FTP_MAX_CONS}")
    logger.info(f"Max connections per IP: {FTP_MAX_CONS_PER_IP}")
    logger.info("=" * 70)

    # Setup server
    server = setup_ftp_server()

    # Start serving
    try:
        logger.info("FTP server started. Press Ctrl+C to stop.")
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("\nShutting down FTP server...")
        server.close_all()
        logger.info("FTP server stopped.")
        return 0
    except Exception as e:
        logger.error(f"Error running FTP server: {e}")
        return 1


if __name__ == '__main__':
    sys.exit(main())
