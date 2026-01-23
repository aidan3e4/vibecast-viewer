# Camera Session Management & Viewer

This project includes a camera capture system with session management and a web-based session viewer built with FastAPI.

## Features

### Session Management ([camera_capture.py](camera_capture.py))
- Groups multiple captures into sessions
- Creates session folders with timestamps (e.g., `session_20260121_103045/`)
- Stores metadata in `session_metadata.json`:
  - Session ID
  - Start/end times
  - Capture count
  - Place (extensible for future use)
- All images saved directly in session folder (flat structure)

### Session Viewer ([session_viewer.py](session_viewer.py))
- Web-based UI for browsing and viewing sessions
- Features:
  - List all available sessions with metadata
  - View images (fisheye + 5 directional views per capture)
  - Display LLM analysis results alongside images
  - Toggle to hide images without analysis
  - Full-screen image viewer (click any image)
  - Clean, responsive design

## Installation

1. Install dependencies:
```bash
pip install -e .
```

This will install:
- `fastapi` - Web framework
- `uvicorn` - ASGI server
- `jinja2` - Template engine
- `opencv-python` - Image processing
- `openai` - LLM analysis (optional)
- And other required packages

## Usage

### 1. Capture Images with Session Management

Run the camera capture script to create a new session:

```bash
# Single capture (creates session with 1 capture)
python camera_capture.py --once

# Continuous capture every 60 seconds
python camera_capture.py -f 60

# With LLM analysis
python camera_capture.py -f 30 -v B  # Analyze Below view

# Multiple views
python camera_capture.py -f 60 -v N S E W B
```

This creates a folder structure like:
```
data/
└── session_20260121_103045/
    ├── session_metadata.json
    ├── 20260121_103045_fisheye.jpg
    ├── 20260121_103045_N.jpg
    ├── 20260121_103045_S.jpg
    ├── 20260121_103045_E.jpg
    ├── 20260121_103045_W.jpg
    ├── 20260121_103045_B.jpg
    ├── 20260121_103105_fisheye.jpg
    ├── 20260121_103105_N.jpg
    └── ... (more captures)
```

### 2. View Sessions in Web UI

Start the session viewer:

```bash
python session_viewer.py
```

Then open your browser to:
```
http://localhost:8000
```

## Web UI Navigation

### Home Page
- Shows all available sessions as cards
- Displays session metadata:
  - Session ID
  - Start/End times
  - Number of captures
  - Status (Active/Completed)
- Click any session card to view details

### Session View Page
- **Header**: Session metadata and controls
- **Toggle Button**: "Hide images without analysis"
  - Click to filter out captures that don't have LLM analysis
- **Capture Items**: Each capture shows:
  - All images (fisheye + 5 views) with timestamps
  - Analysis results (if available)
  - Click any image for full-screen view
- **Close Session**: Return to home page

## Session Metadata Format

The `session_metadata.json` file contains:

```json
{
  "session_id": "session_20260121_103045",
  "start_time": "2026-01-21T10:30:45.123456",
  "end_time": "2026-01-21T11:45:30.654321",
  "place": null,
  "capture_count": 25
}
```

- `start_time`: ISO 8601 format when session started
- `end_time`: When session ended (null if still running)
- `place`: Reserved for future location tracking
- `capture_count`: Total number of captures in this session

## API Endpoints

The FastAPI application exposes these endpoints:

- `GET /` - Home page (HTML)
- `GET /session/{session_name}` - Session view page (HTML)
- `GET /data/{session_name}/{filename}` - Serve image files
- `GET /api/sessions` - List all sessions (JSON)
- `GET /api/session/{session_name}` - Get session data (JSON)

## Configuration

### Camera Settings
Configure via `.env` file or command-line arguments:

```env
CAMERA_IP=192.168.1.141
CAMERA_USERNAME=admin
CAMERA_PASSWORD=your_password
OPENAI_API_KEY=sk-proj-...
```

### Data Directory
By default, sessions are stored in `./data/`. Change with:

```bash
python camera_capture.py -o /path/to/data
```

Update `session_viewer.py` `DATA_DIR` variable if using a custom path.

## Development

### Running in Development Mode

FastAPI with auto-reload:
```bash
uvicorn session_viewer:app --reload --host 0.0.0.0 --port 8000
```

### Project Structure
```
reolinkapipy/
├── camera_capture.py       # Camera capture with session management
├── session_viewer.py       # FastAPI web application
├── templates/              # Jinja2 HTML templates
│   ├── index.html         # Session list page
│   └── session.html       # Session detail page
├── data/                  # Session data (gitignored)
│   └── session_*/         # Individual session folders
└── pyproject.toml         # Dependencies
```

## Future Enhancements

Potential features to add:
- Add `--place` argument to camera_capture.py to set location
- Session search/filter by date, place, capture count
- Export session data (ZIP download)
- Delete sessions from UI
- Real-time session monitoring (WebSocket)
- Comparison view for multiple captures
- Image enhancement tools
- Session notes/annotations
