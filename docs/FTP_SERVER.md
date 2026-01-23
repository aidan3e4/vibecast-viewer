# FTP Server for Reolink Camera Uploads

This guide explains how to set up an FTP server to receive uploads from your Reolink camera. The server can run locally or on a cloud server like runpod.

## Quick Start (Local)

1. **Install dependencies**:
```bash
pip install pyftpdlib python-dotenv
```

2. **Configure credentials in `.env`**:
```bash
FTP_USER = "reolink"
FTP_PASSWORD = "camera123"
FTP_PORT = "2121"
FTP_HOST = "0.0.0.0"
FTP_UPLOAD_DIR = "./ftp_uploads"
```

3. **Start the FTP server**:
```bash
make ftp
```

4. **Configure your Reolink camera** (see below)

## Cloud Deployment (Runpod)

### 1. Create a Runpod Instance

1. Go to [runpod.io](https://runpod.io)
2. Create a new pod (GPU not required for FTP server)
3. Choose a template with Python 3.8+
4. Under **Expose HTTP Ports**, add:
   - Port `2121` (for FTP control)
   - Optionally expose range `60000-60100` for passive mode

### 2. Deploy the Code

SSH into your runpod instance:

```bash
# Clone your repository or upload files
git clone <your-repo-url>
cd vibecast

# Install dependencies
pip install pyftpdlib python-dotenv
```

### 3. Configure for Internet Access

Update your `.env` file with strong credentials:

```bash
FTP_USER = "reolink"
FTP_PASSWORD = "STRONG_PASSWORD_HERE"  # Change this!
FTP_PORT = "2121"
FTP_HOST = "0.0.0.0"  # Accept connections from anywhere
FTP_UPLOAD_DIR = "./ftp_uploads"
FTP_MAX_CONS = "256"
FTP_MAX_CONS_PER_IP = "5"
```

### 4. Start the Server

```bash
# Start in background with nohup
nohup make ftp > ftp_server.log 2>&1 &

# Or use screen/tmux for persistent session
screen -S ftp
make ftp
# Press Ctrl+A then D to detach
```

### 5. Get Your Public Address

Runpod will provide you with:
- **Public IP**: e.g., `123.45.67.89`
- **Port**: `2121` (or your configured port)

Your FTP address will be: `ftp://123.45.67.89:2121`

## Configure Reolink Camera

### Via Reolink Web Interface

1. **Open camera web interface**:
   - Go to `http://YOUR_CAMERA_IP` in a browser
   - Login with your credentials

2. **Navigate to FTP Settings**:
   - Settings → Network → FTP

3. **Configure FTP Upload**:
   ```
   Server Address: YOUR_RUNPOD_IP (or local IP)
   Port: 2121
   Username: reolink (from your .env)
   Password: camera123 (from your .env)
   Remote Directory: / (or specify a subdirectory)
   ```

4. **Set Upload Schedule**:
   - Settings → Alarm → Schedule
   - Choose when to upload (motion detection, continuous, etc.)

5. **Test Connection**:
   - Click "Test" button to verify FTP connection
   - Should see "Test succeeded" message

### Via Reolink App

1. Open Reolink app on your phone
2. Select your camera
3. Go to: Device Settings → Advanced → FTP
4. Enter the same configuration as above
5. Enable FTP upload
6. Test the connection

## Upload Modes

Configure what triggers uploads:

- **Motion Detection**: Upload when motion is detected
- **Continuous**: Upload at regular intervals
- **Schedule**: Upload during specific time periods
- **Email Alert**: Upload when alarm triggers

## File Organization

Uploaded files will be organized in `ftp_uploads/`:

```
ftp_uploads/
├── 20240123_140523.jpg
├── 20240123_140524.jpg
├── 20240123_140525.jpg
└── ...
```

## Security Considerations

### For Internet-Exposed Servers

1. **Use strong passwords**:
   ```bash
   FTP_PASSWORD = "Use_A_Very_Strong_Password_123!"
   ```

2. **Limit connections per IP**:
   ```bash
   FTP_MAX_CONS_PER_IP = "5"  # Prevent abuse
   ```

3. **Use a non-standard port**:
   ```bash
   FTP_PORT = "2121"  # Not the default 21
   ```

4. **Consider IP whitelisting**: Modify `services/ftp_server.py` to only accept connections from your camera's IP

5. **Monitor logs**:
   ```bash
   tail -f ftp_server.log
   ```

### For Local Networks

If only using on your local network:
```bash
FTP_HOST = "192.168.1.XXX"  # Your local IP
```

## Firewall Configuration

### On Linux Server

```bash
# Allow FTP port
sudo ufw allow 2121/tcp

# If using passive mode, allow passive port range
sudo ufw allow 60000:60100/tcp
```

### On Runpod

- Runpod automatically handles port exposure
- Just ensure you added port 2121 when creating the pod

## Troubleshooting

### Camera can't connect

1. **Check FTP server is running**:
   ```bash
   ps aux | grep ftp_server
   ```

2. **Check firewall**:
   ```bash
   sudo ufw status
   ```

3. **Test with FTP client**:
   ```bash
   ftp YOUR_SERVER_IP 2121
   # Enter username and password
   ```

4. **Check logs**:
   ```bash
   tail -f ftp_server.log
   ```

### Files not appearing

1. **Check upload directory permissions**:
   ```bash
   ls -la ftp_uploads/
   chmod 755 ftp_uploads/
   ```

2. **Check disk space**:
   ```bash
   df -h
   ```

3. **Review camera upload settings** in Reolink app

### Passive mode issues

If your camera needs passive mode:

1. Edit `services/ftp_server.py`
2. Uncomment the passive ports line:
   ```python
   handler.passive_ports = range(60000, 60100)
   ```
3. Open these ports in your firewall
4. Restart the FTP server

## Integration with Vibecast

The FTP server is separate from the capture service. To process uploaded images:

1. **Monitor the upload directory**:
   ```python
   # Create a watcher script
   from pathlib import Path
   import time

   upload_dir = Path("ftp_uploads")

   while True:
       for img_file in upload_dir.glob("*.jpg"):
           # Process with vision_llm
           print(f"New upload: {img_file}")
       time.sleep(5)
   ```

2. **Or manually process uploads**:
   ```bash
   # Move files to data directory
   mv ftp_uploads/*.jpg data/manual_uploads/
   ```

## Advanced Configuration

### Custom Upload Handling

Edit `services/ftp_server.py` and modify the `on_file_received` method:

```python
def on_file_received(self, file):
    """Called when file is successfully received."""
    logger.info(f"File received: {file}")

    # Custom processing
    if file.endswith('.jpg'):
        # Trigger analysis, send notification, etc.
        process_new_image(file)
```

### Multiple Cameras

Give each camera a unique username:

```python
# In ftp_server.py
authorizer.add_user("camera1", "pass1", "/uploads/camera1", perm="elrw")
authorizer.add_user("camera2", "pass2", "/uploads/camera2", perm="elrw")
```

## Alternative: FTPS (FTP over TLS)

For encrypted uploads, see [pyftpdlib TLS documentation](https://pyftpdlib.readthedocs.io/en/latest/tutorial.html#tls-ftp).

## Monitoring

View real-time uploads:

```bash
# Watch log file
tail -f ftp_server.log

# Watch upload directory
watch -n 1 ls -lh ftp_uploads/

# Count uploads per minute
watch -n 60 'ls ftp_uploads/ | wc -l'
```

## Stopping the Server

```bash
# Find the process
ps aux | grep ftp_server

# Kill it
kill <PID>

# Or if using screen
screen -r ftp
# Press Ctrl+C
```

## Cost Considerations

Runpod pricing (as of 2024):
- CPU-only pods: ~$0.10-0.30/hour
- Storage: Included
- Bandwidth: Usually included

For 24/7 operation: ~$70-220/month

Consider cheaper alternatives for simple FTP:
- DigitalOcean Droplet: $6/month
- AWS EC2 t4g.micro: ~$7/month
- Oracle Cloud free tier: Free (ARM instance)
