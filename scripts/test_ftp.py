#!/usr/bin/env python3
"""
Simple FTP test script to verify the server is working.
"""

import os
from ftplib import FTP
from pathlib import Path
from dotenv import load_dotenv
import tempfile

load_dotenv()

FTP_HOST = os.environ.get("FTP_HOST", "localhost")
FTP_PORT = int(os.environ.get("FTP_PORT", "2121"))
FTP_USER = os.environ.get("FTP_USER", "reolink")
FTP_PASSWORD = os.environ.get("FTP_PASSWORD", "camera123")


def test_ftp_connection():
    """Test FTP server connection and upload."""

    print("=" * 60)
    print("FTP Server Test")
    print("=" * 60)
    print(f"Host: {FTP_HOST}")
    print(f"Port: {FTP_PORT}")
    print(f"User: {FTP_USER}")
    print("=" * 60)

    try:
        # Connect
        print("\n1. Connecting to FTP server...")
        ftp = FTP()
        ftp.connect(FTP_HOST, FTP_PORT)
        print("✓ Connected successfully")

        # Login
        print("\n2. Logging in...")
        ftp.login(FTP_USER, FTP_PASSWORD)
        print(f"✓ Logged in as {FTP_USER}")

        # List files
        print("\n3. Listing files...")
        files = ftp.nlst()
        if files:
            print(f"✓ Found {len(files)} files:")
            for f in files[:10]:  # Show first 10
                print(f"  - {f}")
        else:
            print("✓ Directory is empty (no uploads yet)")

        # Create test file
        print("\n4. Creating test file...")
        test_file = tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False)
        test_file.write("FTP test upload from vibecast\n")
        test_file.write(f"Server: {FTP_HOST}:{FTP_PORT}\n")
        test_file.close()

        # Upload test file
        print("5. Uploading test file...")
        test_filename = Path(test_file.name).name
        with open(test_file.name, 'rb') as f:
            ftp.storbinary(f'STOR test_{test_filename}', f)
        print(f"✓ Uploaded: test_{test_filename}")

        # Verify upload
        print("\n6. Verifying upload...")
        files_after = ftp.nlst()
        if f'test_{test_filename}' in files_after:
            print("✓ Upload verified - file exists on server")
        else:
            print("✗ Upload verification failed")

        # Get file size
        size = ftp.size(f'test_{test_filename}')
        if size:
            print(f"✓ File size: {size} bytes")

        # Cleanup local test file
        os.unlink(test_file.name)

        # Close connection
        print("\n7. Closing connection...")
        ftp.quit()
        print("✓ Connection closed")

        print("\n" + "=" * 60)
        print("✓ ALL TESTS PASSED")
        print("=" * 60)
        print("\nYour FTP server is working correctly!")
        print(f"You can configure your Reolink camera to upload to:")
        print(f"  Server: {FTP_HOST}")
        print(f"  Port: {FTP_PORT}")
        print(f"  User: {FTP_USER}")
        print(f"  Password: {FTP_PASSWORD}")
        print("=" * 60)

        return 0

    except ConnectionRefusedError:
        print("\n✗ Connection refused")
        print("  Make sure the FTP server is running: make ftp")
        return 1

    except Exception as e:
        print(f"\n✗ Error: {e}")
        print("\nTroubleshooting:")
        print("  1. Check if FTP server is running: ps aux | grep ftp_server")
        print("  2. Check .env configuration")
        print("  3. Check firewall settings")
        return 1


if __name__ == '__main__':
    import sys
    sys.exit(test_ftp_connection())
