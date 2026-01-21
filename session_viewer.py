#!/usr/bin/env python3
"""
Session Viewer Web Application

A FastAPI-based web UI for viewing camera capture sessions with metadata,
images, and LLM analysis results.
"""

import json
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.requests import Request

app = FastAPI(title="Camera Session Viewer")

# Configuration
DATA_DIR = Path('./data')
templates = Jinja2Templates(directory="templates")


def get_available_sessions():
    """Get list of all available session folders."""
    if not DATA_DIR.exists():
        return []

    sessions = []
    for session_dir in DATA_DIR.iterdir():
        if session_dir.is_dir() and session_dir.name.startswith('session_'):
            metadata_path = session_dir / 'session_metadata.json'
            if metadata_path.exists():
                with open(metadata_path, 'r') as f:
                    metadata = json.load(f)
                sessions.append({
                    'path': session_dir.name,
                    'metadata': metadata
                })

    # Sort by start time (newest first)
    sessions.sort(key=lambda x: x['metadata']['start_time'], reverse=True)
    return sessions


def get_session_data(session_name):
    """Get complete session data including metadata, images, and analyses."""
    session_dir = DATA_DIR / session_name

    if not session_dir.exists():
        return None

    # Read metadata
    metadata_path = session_dir / 'session_metadata.json'
    if not metadata_path.exists():
        return None

    with open(metadata_path, 'r') as f:
        metadata = json.load(f)

    # Find all images and their analyses
    captures = {}

    # Find all fisheye images to get timestamps
    for img_file in session_dir.glob('*_fisheye.jpg'):
        timestamp = img_file.stem.replace('_fisheye', '')
        captures[timestamp] = {
            'timestamp': timestamp,
            'fisheye': img_file.name,
            'views': {},
            'analysis': None
        }

    # Find all view images
    view_codes = ['N', 'S', 'E', 'W', 'B']
    view_names = {
        'N': 'North',
        'S': 'South',
        'E': 'East',
        'W': 'West',
        'B': 'Below'
    }

    for timestamp in captures.keys():
        for code in view_codes:
            view_file = session_dir / f"{timestamp}_{code}.jpg"
            if view_file.exists():
                captures[timestamp]['views'][code] = {
                    'filename': view_file.name,
                    'name': view_names[code]
                }

        # Check for LLM analysis
        analysis_file = session_dir / f"{timestamp}_llm_responses.json"
        if analysis_file.exists():
            with open(analysis_file, 'r') as f:
                captures[timestamp]['analysis'] = json.load(f)

    # Sort captures by timestamp
    sorted_captures = sorted(captures.values(), key=lambda x: x['timestamp'])

    return {
        'session_name': session_name,
        'metadata': metadata,
        'captures': sorted_captures
    }


@app.get('/', response_class=HTMLResponse)
async def index(request: Request):
    """Main page - shows list of available sessions."""
    sessions = get_available_sessions()
    return templates.TemplateResponse('index.html', {
        'request': request,
        'sessions': sessions
    })


@app.get('/session/{session_name}', response_class=HTMLResponse)
async def view_session(request: Request, session_name: str):
    """View a specific session with all its images and analyses."""
    session_data = get_session_data(session_name)

    if not session_data:
        raise HTTPException(status_code=404, detail="Session not found")

    return templates.TemplateResponse('session.html', {
        'request': request,
        'session': session_data
    })


@app.get('/data/{session_name}/{filename}')
async def serve_image(session_name: str, filename: str):
    """Serve image files from session directories."""
    session_dir = DATA_DIR / session_name
    file_path = session_dir / filename

    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")

    return FileResponse(file_path)


@app.get('/api/sessions')
async def api_sessions():
    """API endpoint to get list of sessions."""
    sessions = get_available_sessions()
    return sessions


@app.get('/api/session/{session_name}')
async def api_session(session_name: str):
    """API endpoint to get session data."""
    session_data = get_session_data(session_name)

    if not session_data:
        raise HTTPException(status_code=404, detail="Session not found")

    return session_data


if __name__ == '__main__':
    import uvicorn
    print("Starting Session Viewer...")
    print(f"Data directory: {DATA_DIR.absolute()}")
    print("Open http://localhost:8000 in your browser")
    uvicorn.run(app, host='0.0.0.0', port=8000)
