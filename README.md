# Vibecast - Fisheye Camera Capture & Analysis

A tool for capturing photos from Reolink fisheye cameras, generating perspective views, and analyzing them with LLM vision models.

## Quick Start

### Setup

1. Configure your camera and API credentials in `.env`:
```bash
CAMERA_IP = "192.168.1.143"
CAMERA_USERNAME = "admin"
CAMERA_PASSWORD = "your_password"
USE_HTTPS = "False"
OPENAI_API_KEY = "sk-..."
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

### Available Commands

Run `make help` to see all available commands:

```bash
make help       # Show all available commands
make viewer     # Start the web viewer UI
make capture    # Run camera capture service
make ip         # Show your local IP for network access
```

## Usage

### 1. Web Viewer (Recommended)

Start the web interface to control the camera and view captures:

```bash
make viewer
```

Then open in your browser:
- **Local access**: http://localhost:8000
- **Network access**: See [Network Access](#network-access) below

The web viewer provides:
- Camera connection controls
- Live view toggle
- Photo capture with fisheye view
- Perspective view generation (North, South, East, West, Below)
- LLM analysis with custom prompts

### 2. Command-Line Capture

Run camera capture from the command line:

```bash
# Single capture
make capture ARGS='--once'

# Continuous capture every 30 seconds with LLM analysis
make capture ARGS='-f 30 -v N S E W B'

# Capture with custom views
make capture ARGS='-f 60 -v N E'
```

**View codes:**
- `N` = North
- `S` = South
- `E` = East
- `W` = West
- `B` = Below (floor)

## Network Access

Share the viewer with other devices on your WiFi network:

1. **Find your local IP address**:
```bash
make ip
```

2. **Start the viewer**:
```bash
make viewer
```

3. **Share the URL** with others on your network:
```
http://YOUR_IP:8000
```
(Replace `YOUR_IP` with the address shown by `make ip`, typically `192.168.1.xxx`)

Others on your WiFi can now access the viewer from their browsers.

### Firewall Configuration

If you can't connect from other devices, you may need to allow port 8000:

**Linux:**
```bash
sudo ufw allow 8000/tcp              # Ubuntu/Debian
sudo firewall-cmd --add-port=8000/tcp  # Fedora/RHEL
```

**macOS:**
```bash
# Port 8000 is typically open by default
```

## Features

### Camera Control UI
- Connect to Reolink fisheye cameras
- Live view with auto-refresh
- Capture fisheye photos
- Generate perspective views (unwarp)
- Analyze views with OpenAI Vision

### Session Viewer
- Browse all capture sessions
- View captured images and perspective views
- Review LLM analysis results
- Session metadata tracking

### Command-Line Capture
- Automated periodic captures
- Customizable capture frequency
- Select which views to analyze
- Session-based organization
- Configurable FOV and output size

## Project Structure

```
vibecast/
├── clients/           # Camera capture client
├── viewer/            # Web viewer application
│   └── templates/     # HTML templates
├── vision_llm/        # LLM analysis and fisheye processing
├── data/              # Captured sessions (auto-created)
├── .env               # Configuration
└── Makefile           # Shortcuts
```

## Output

Captured images are saved in session directories under `data/`:

```
data/
└── session_20240123_143022/
    ├── session_metadata.json
    ├── 20240123_143022_fisheye.jpg
    ├── 20240123_143022_N.jpg  (North view)
    ├── 20240123_143022_S.jpg  (South view)
    ├── 20240123_143022_E.jpg  (East view)
    ├── 20240123_143022_W.jpg  (West view)
    ├── 20240123_143022_B.jpg  (Below view)
    └── 20240123_143022_llm_responses.json
```

## Tips

- Use the web viewer for interactive control and testing
- Use command-line capture for automated monitoring
- Sessions are automatically organized by timestamp
- LLM analysis is optional - capture works without it
- All .env values are pre-populated in the web UI
