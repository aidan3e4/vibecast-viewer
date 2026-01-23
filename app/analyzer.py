#!/usr/bin/env python3
"""
FTP Upload Analyzer Web Application

A FastAPI-based web UI for analyzing FTP uploaded images with LLM.
"""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Optional, List

import cv2
import numpy as np
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from starlette.requests import Request
from dotenv import load_dotenv

from constants import app_dir, data_dir, ftp_uploads_dir
from vision_llm import (
    get_room_views,
    image_to_base64,
    save_image,
    analyze_with_openai,
)

load_dotenv()

app = FastAPI(title="FTP Upload Analyzer")

# Configuration
templates = Jinja2Templates(directory=app_dir / "templates")

# Directories
unwarped_dir = data_dir / "unwarped"
results_dir = data_dir / "results"
unwarped_dir.mkdir(exist_ok=True, parents=True)
results_dir.mkdir(exist_ok=True, parents=True)

# View name mapping
VIEW_MAP = {
    'N': 'North',
    'S': 'South',
    'E': 'East',
    'W': 'West',
    'B': 'Below',
}


# Request/Response Models
class TimeRangeRequest(BaseModel):
    start_date: str  # YYYY-MM-DD
    end_date: str    # YYYY-MM-DD
    start_time: str = "00:00"  # HH:MM
    end_time: str = "23:59"    # HH:MM


class ImageInfo(BaseModel):
    timestamp: str
    filename: str
    date: str
    time: str
    filepath: str


class UnwarpRequest(BaseModel):
    image_paths: List[str]  # List of relative paths from ftp_uploads


class ImageToAnalyze(BaseModel):
    timestamp: str
    direction: str
    path: str


class AnalyzeRequest(BaseModel):
    images: List[ImageToAnalyze]  # List of specific images to analyze
    prompt: str
    api_key: str


def parse_ftp_filename(filename: str) -> Optional[dict]:
    """Parse FTP upload filename to extract timestamp.

    Format: Reolink_00_YYYYMMDDHHMMSS.jpg
    """
    if not filename.startswith('Reolink_00_'):
        return None

    try:
        timestamp_str = filename.replace('Reolink_00_', '').replace('.jpg', '').replace('.mp4', '').replace('.txt', '')
        if len(timestamp_str) != 14:
            return None

        dt = datetime.strptime(timestamp_str, '%Y%m%d%H%M%S')
        return {
            'timestamp': timestamp_str,
            'datetime': dt,
            'date': dt.strftime('%Y-%m-%d'),
            'time': dt.strftime('%H:%M:%S'),
        }
    except (ValueError, AttributeError):
        return None


def get_images_in_range(start_date: str, end_date: str, start_time: str = "00:00", end_time: str = "23:59") -> List[ImageInfo]:
    """Get all FTP uploaded images in the given datetime range."""
    images = []

    # Parse datetime with time components
    start_dt = datetime.strptime(f"{start_date} {start_time}", '%Y-%m-%d %H:%M')
    end_dt = datetime.strptime(f"{end_date} {end_time}", '%Y-%m-%d %H:%M')

    # Walk through the FTP uploads directory
    for year_dir in ftp_uploads_dir.iterdir():
        if not year_dir.is_dir():
            continue

        for month_dir in year_dir.iterdir():
            if not month_dir.is_dir():
                continue

            for day_dir in month_dir.iterdir():
                if not day_dir.is_dir():
                    continue

                # Check each jpg file
                for img_file in day_dir.glob('Reolink_00_*.jpg'):
                    parsed = parse_ftp_filename(img_file.name)
                    if not parsed:
                        continue

                    # Check if in datetime range
                    if start_dt <= parsed['datetime'] <= end_dt:
                        # Calculate relative path from ftp_uploads
                        rel_path = img_file.relative_to(ftp_uploads_dir)

                        images.append(ImageInfo(
                            timestamp=parsed['timestamp'],
                            filename=img_file.name,
                            date=parsed['date'],
                            time=parsed['time'],
                            filepath=str(rel_path),
                        ))

    # Sort by timestamp
    images.sort(key=lambda x: x.timestamp)
    return images


def get_unwarped_path(timestamp: str, direction: str) -> Path:
    """Get the path for an unwarped image."""
    # Extract date components from timestamp
    year = timestamp[:4]
    month = timestamp[4:6]
    day = timestamp[6:8]

    # Create directory structure
    unwarp_subdir = unwarped_dir / year / month / day
    unwarp_subdir.mkdir(exist_ok=True, parents=True)

    return unwarp_subdir / f"{timestamp}_{direction}.jpg"


def unwarp_image(image_path: str) -> dict:
    """Unwarp a fisheye image and cache the results.

    Returns dict with direction -> filepath mappings for unwarped images.
    """
    # Parse timestamp from filepath
    full_path = ftp_uploads_dir / image_path
    filename = full_path.name
    parsed = parse_ftp_filename(filename)

    if not parsed:
        raise ValueError(f"Invalid filename format: {filename}")

    timestamp = parsed['timestamp']

    # Check if all unwarped images already exist
    unwarped_paths = {}
    all_exist = True

    for direction in VIEW_MAP.keys():
        unwarp_path = get_unwarped_path(timestamp, direction)
        unwarped_paths[direction] = unwarp_path
        if not unwarp_path.exists():
            all_exist = False

    # If all exist, return cached paths
    if all_exist:
        return {dir: str(path.relative_to(data_dir)) for dir, path in unwarped_paths.items()}

    # Load the fisheye image
    img = cv2.imread(str(full_path))
    if img is None:
        raise ValueError(f"Failed to load image: {full_path}")

    img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

    # Generate perspective views
    views = get_room_views(img_rgb, fov=90, output_size=(1080, 810))

    # Save all views
    for view_name, view_img in views.items():
        short_name = view_name[0].upper()  # N, E, S, W, B
        unwarp_path = unwarped_paths[short_name]
        save_image(view_img, unwarp_path)

    return {dir: str(path.relative_to(data_dir)) for dir, path in unwarped_paths.items()}


@app.get('/', response_class=HTMLResponse)
async def index(request: Request):
    """Main page - FTP upload analyzer."""
    openai_api_key = os.environ.get('OPENAI_API_KEY', '')

    # Get today's date range as default
    today = datetime.now().strftime('%Y-%m-%d')

    return templates.TemplateResponse('analyzer.html', {
        'request': request,
        'openai_api_key': openai_api_key,
        'default_start_date': today,
        'default_end_date': today,
    })


@app.post('/api/images/list')
async def list_images(req: TimeRangeRequest):
    """List all images in the given time range."""
    try:
        images = get_images_in_range(req.start_date, req.end_date, req.start_time, req.end_time)
        return {'images': [img.dict() for img in images]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post('/api/images/unwarp')
async def unwarp_images(req: UnwarpRequest):
    """Unwarp selected images and return paths to unwarped views."""
    try:
        results = {}

        for image_path in req.image_paths:
            unwarped_paths = unwarp_image(image_path)

            # Extract timestamp from path
            filename = Path(image_path).name
            parsed = parse_ftp_filename(filename)
            if parsed:
                results[parsed['timestamp']] = unwarped_paths

        return {'unwarped': results}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post('/api/analyze')
async def analyze_images(req: AnalyzeRequest):
    """Analyze selected images with LLM and save results."""
    try:
        # Prepare result
        analysis_timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

        result = {
            'analysis_timestamp': analysis_timestamp,
            'analysis_datetime': datetime.now().isoformat(),
            'prompt': req.prompt,
            'analyzed_images': []
        }

        # Analyze each selected image
        for img_info in req.images:
            image_result = {
                'timestamp': img_info.timestamp,
                'direction': img_info.direction,
                'direction_name': VIEW_MAP[img_info.direction],
                'filepath': img_info.path,
            }

            # Load image from data directory
            img_path = data_dir / img_info.path

            if not img_path.exists():
                image_result['error'] = 'Image not found'
                result['analyzed_images'].append(image_result)
                continue

            # Load image and convert to base64
            img = cv2.imread(str(img_path))
            if img is None:
                image_result['error'] = 'Failed to load image'
                result['analyzed_images'].append(image_result)
                continue

            img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            image_base64 = image_to_base64(img_rgb)

            # Analyze with LLM
            try:
                llm_response = analyze_with_openai(image_base64, req.prompt, req.api_key)
                image_result['llm_output'] = llm_response
            except Exception as e:
                image_result['error'] = str(e)

            result['analyzed_images'].append(image_result)

        # Save result to file
        result_path = results_dir / f"{analysis_timestamp}.json"
        with open(result_path, 'w') as f:
            json.dump(result, f, indent=2)

        return {
            'result': result,
            'result_file': str(result_path.relative_to(data_dir))
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get('/api/image/{path:path}')
async def serve_image(path: str):
    """Serve images from data directory."""
    file_path = data_dir / path

    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")

    return FileResponse(file_path)


if __name__ == '__main__':
    import uvicorn
    print("Starting FTP Upload Analyzer...")
    print(f"FTP uploads directory: {ftp_uploads_dir.absolute()}")
    print(f"Unwarped cache directory: {unwarped_dir.absolute()}")
    print(f"Results directory: {results_dir.absolute()}")
    print("Open http://localhost:8001 in your browser")
    uvicorn.run(app, host='0.0.0.0', port=8001)
