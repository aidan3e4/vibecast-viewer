# Runpod Deployment Guide

Quick guide to deploy the FTP server on runpod for receiving Reolink camera uploads over the internet.

## Step 1: Create Runpod Account

1. Go to https://runpod.io
2. Sign up for an account
3. Add some credits ($10 minimum recommended)

## Step 2: Deploy a Pod

1. **Go to Pods** → **+ Deploy**

2. **Choose a template**:
   - Select "RunPod Pytorch" or any Python 3.8+ template
   - GPU not required - choose CPU pod for cost savings

3. **Configure Pod**:
   - **GPU/CPU**: Select "CPU" (cheaper, sufficient for FTP)
   - **Container Disk**: 10 GB minimum
   - **Volume**: Optional (for persistent storage)

4. **Expose Ports**:
   - Add port `2121` (FTP control port)
   - Optionally add `60000-60100` (for passive mode)

5. **Deploy Pod**

## Step 3: Connect to Pod

Once deployed, connect via SSH:

```bash
# Runpod provides SSH connection string
ssh root@<pod-id>.runpod.io -p <ssh-port>
```

Or use the web terminal in runpod interface.

## Step 4: Install Code

```bash
# Update system
apt-get update

# Install git if not present
apt-get install -y git

# Clone repository (replace with your repo)
git clone https://github.com/your-username/vibecast.git
cd vibecast

# Or upload files manually
# You can use runpod's file upload feature
```

## Step 5: Install Dependencies

```bash
# Install Python dependencies
pip install -r requirements-ftp.txt
```

## Step 6: Configure Environment

```bash
# Copy example env file
cp .env.example .env

# Edit with strong password
nano .env
```

Update these critical values:
```bash
FTP_USER = "reolink"
FTP_PASSWORD = "USE_A_STRONG_PASSWORD_HERE"  # IMPORTANT!
FTP_PORT = "2121"
FTP_HOST = "0.0.0.0"
```

## Step 7: Start FTP Server

### Option A: Foreground (for testing)

```bash
python3 services/ftp_server.py
```

Press Ctrl+C to stop.

### Option B: Background with nohup

```bash
nohup python3 services/ftp_server.py > ftp_server.log 2>&1 &

# Check if running
ps aux | grep ftp_server

# View logs
tail -f ftp_server.log
```

### Option C: Using screen (recommended)

```bash
# Start screen session
screen -S ftp

# Start FTP server
python3 services/ftp_server.py

# Detach: Press Ctrl+A then D

# Reattach later
screen -r ftp

# List sessions
screen -ls
```

## Step 8: Get Your Public Address

Runpod provides connection info:

1. Go to your pod details
2. Find **TCP Port Mappings**
3. Look for port 2121 mapping

You'll see something like:
```
External: 123.45.67.89:54321
Internal: 2121
```

Your FTP address is: `ftp://123.45.67.89:54321`

## Step 9: Configure Reolink Camera

In your Reolink camera settings:

```
Server: 123.45.67.89
Port: 54321 (the external port from runpod)
Username: reolink (from your .env)
Password: YOUR_STRONG_PASSWORD (from your .env)
Directory: /
```

Test the connection in camera settings.

## Step 10: Monitor Uploads

```bash
# Watch log in real-time
tail -f ftp_server.log

# Check upload directory
ls -lh ftp_uploads/

# Count files
ls ftp_uploads/ | wc -l

# Watch directory continuously
watch -n 2 'ls -lh ftp_uploads/ | tail -10'
```

## Using Docker (Alternative)

If you prefer Docker:

```bash
# Build image
docker build -f Dockerfile.ftp -t vibecast-ftp .

# Run container
docker run -d \
  -p 2121:2121 \
  -v $(pwd)/ftp_uploads:/app/ftp_uploads \
  --env-file .env \
  --name ftp-server \
  vibecast-ftp

# View logs
docker logs -f ftp-server

# Stop
docker stop ftp-server
```

## Costs

Runpod CPU pricing (approximate, check current rates):

- **CPU Pod**: ~$0.10 - $0.30/hour
- **24/7 for 30 days**: ~$72 - $216/month
- **Storage**: Usually included
- **Bandwidth**: Usually included

### Cost Optimization

1. **Use Spot Instances**: 50-90% cheaper (but can be interrupted)
2. **Lower-tier CPU**: Choose smallest CPU that works
3. **Auto-stop**: Configure pod to stop when idle
4. **Alternative Providers**: Consider DigitalOcean ($6/month), AWS, or Oracle Cloud free tier

## Security Checklist

- [ ] Changed default FTP password
- [ ] Using non-standard port (2121)
- [ ] Set max connections per IP
- [ ] Monitoring logs regularly
- [ ] Backup important uploads
- [ ] Consider IP whitelisting (if camera has static IP)

## Troubleshooting

### Pod won't start
- Check if you have enough credits
- Try different region
- Check disk space requirements

### Can't connect to FTP
- Verify port is exposed in pod settings
- Check if server is running: `ps aux | grep ftp_server`
- Check logs: `tail -f ftp_server.log`
- Test locally: `telnet localhost 2121`

### Camera can't reach server
- Verify external port from runpod
- Check camera firewall settings
- Test from another location: `ftp <external-ip> <external-port>`
- Ensure camera has internet access

### Files not appearing
- Check disk space: `df -h`
- Check permissions: `ls -la ftp_uploads/`
- Review camera upload settings
- Check logs for errors

## Stopping the Server

```bash
# If using screen
screen -r ftp
# Press Ctrl+C

# If using background process
ps aux | grep ftp_server
kill <PID>

# If using Docker
docker stop ftp-server
```

## Persistent Storage

For long-term deployments, use runpod volumes:

1. Create a network volume in runpod
2. Mount it when creating pod: `/workspace`
3. Update `.env`:
   ```bash
   FTP_UPLOAD_DIR=/workspace/ftp_uploads
   ```

This ensures uploads persist even if pod restarts.

## Monitoring & Alerts

### Simple monitoring script

```bash
#!/bin/bash
# monitor.sh - Check if FTP server is running

if ! pgrep -f "ftp_server.py" > /dev/null; then
    echo "FTP server is down! Restarting..."
    nohup python3 services/ftp_server.py > ftp_server.log 2>&1 &
fi
```

Add to crontab:
```bash
crontab -e
# Add line:
*/5 * * * * /root/vibecast/monitor.sh
```

## Backup Strategy

Regular backups of uploads:

```bash
# Sync to S3
aws s3 sync ftp_uploads/ s3://your-bucket/camera-uploads/

# Or compress and download
tar -czf uploads-$(date +%Y%m%d).tar.gz ftp_uploads/
```

## Next Steps

- Set up automatic processing of uploaded images
- Configure notifications for new uploads
- Integrate with vision_llm for automatic analysis
- Set up multiple cameras with separate directories
