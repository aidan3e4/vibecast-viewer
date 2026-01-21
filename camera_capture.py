#!/usr/bin/env python3
"""
Reolink Fisheye Camera Capture Script

Captures photos from a Reolink fisheye camera at regular intervals,
generates perspective views, and optionally sends them to an LLM for analysis.
"""

import argparse
import base64
from datetime import datetime
from dotenv import load_dotenv
import json
import os
from pathlib import Path
import time

import cv2
import numpy as np

from reolinkapi import Camera

load_dotenv()

# View name mapping
VIEW_MAP = {
    'N': 'North',
    'S': 'South',
    'E': 'East',
    'W': 'West',
    'B': 'Below',
}


def create_perspective_map(fisheye_shape, output_size, fov, theta, phi):
    """
    Create remap arrays for fast fisheye to perspective conversion.
    """
    h, w = fisheye_shape[:2]
    cx, cy = w / 2, h / 2
    radius = min(cx, cy)

    out_w, out_h = output_size

    fov_rad = np.radians(fov)
    theta_rad = np.radians(theta)
    phi_rad = np.radians(phi)

    f = out_w / (2 * np.tan(fov_rad / 2))

    x = np.arange(out_w) - out_w / 2
    y = np.arange(out_h) - out_h / 2
    x_grid, y_grid = np.meshgrid(x, y)

    x_norm = x_grid / f
    y_norm = -y_grid / f
    z_norm = np.ones_like(x_norm)

    rays = np.stack([x_norm, y_norm, z_norm], axis=-1)
    rays = rays / np.linalg.norm(rays, axis=-1, keepdims=True)

    cos_t, sin_t = np.cos(theta_rad), np.sin(theta_rad)
    cos_p, sin_p = np.cos(phi_rad), np.sin(phi_rad)

    Ry = np.array([
        [cos_t, 0, sin_t],
        [0, 1, 0],
        [-sin_t, 0, cos_t]
    ])
    Rx = np.array([
        [1, 0, 0],
        [0, cos_p, -sin_p],
        [0, sin_p, cos_p]
    ])
    R = Ry @ Rx

    rays_rotated = np.einsum('ij,hwj->hwi', R, rays)

    rx, ry, rz = rays_rotated[..., 0], rays_rotated[..., 1], rays_rotated[..., 2]

    angle_from_nadir = np.arccos(np.clip(-ry, -1, 1))
    azimuth = np.arctan2(rx, rz)

    r_fish = (angle_from_nadir / (np.pi / 2)) * radius

    map_x = (cx + r_fish * np.sin(azimuth)).astype(np.float32)
    map_y = (cy - r_fish * np.cos(azimuth)).astype(np.float32)

    return map_x, map_y


def fisheye_to_perspective_fast(img, fov=90, theta=0, phi=0, output_size=(800, 600)):
    """Fast fisheye to perspective conversion using OpenCV remap."""
    map_x, map_y = create_perspective_map(img.shape, output_size, fov, theta, phi)
    return cv2.remap(img, map_x, map_y, cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT)


def extract_center_view(img, radius_fraction=0.6, output_size=(600, 600)):
    """Extract and unwarp the center portion of a fisheye image (directly below)."""
    h, w = img.shape[:2]
    cx, cy = w / 2, h / 2
    radius = min(cx, cy)

    out_w, out_h = output_size

    x = np.linspace(-1, 1, out_w)
    y = np.linspace(-1, 1, out_h)
    x_grid, y_grid = np.meshgrid(x, y)

    r_out = np.sqrt(x_grid**2 + y_grid**2)
    theta_out = np.arctan2(y_grid, x_grid)

    r_fish = r_out * radius * radius_fraction

    map_x = (cx + r_fish * np.cos(theta_out)).astype(np.float32)
    map_y = (cy + r_fish * np.sin(theta_out)).astype(np.float32)

    mask = r_out <= 1.0

    result = cv2.remap(img, map_x, map_y, cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT)
    result[~mask] = 0

    return result


def get_room_views(img, fov=90, output_size=(1080, 810), view_angle=45, below_fraction=0.6):
    """Generate perspective views from fisheye image."""
    directions = {
        'North': (0, view_angle),
        'East': (90, view_angle),
        'South': (180, view_angle),
        'West': (270, view_angle),
    }

    views = {}
    for name, (theta, phi) in directions.items():
        views[name] = fisheye_to_perspective_fast(img, fov=fov, theta=theta, phi=phi, output_size=output_size)

    views['Below'] = extract_center_view(img, radius_fraction=below_fraction, output_size=(output_size[0], output_size[0]))

    return views


def image_to_base64(img_np):
    """Convert numpy array (RGB) to base64 JPEG."""
    img_bgr = cv2.cvtColor(img_np, cv2.COLOR_RGB2BGR)
    _, encoded = cv2.imencode('.jpg', img_bgr)
    return base64.b64encode(encoded.tobytes()).decode('utf-8')


def save_image(img_np, filepath):
    """Save numpy array (RGB) to file."""
    img_bgr = cv2.cvtColor(img_np, cv2.COLOR_RGB2BGR)
    cv2.imwrite(str(filepath), img_bgr)


def create_session(output_dir, place=None):
    """Create a new session folder with metadata."""
    timestamp = datetime.now()
    session_id = f"session_{timestamp.strftime('%Y%m%d_%H%M%S')}"
    session_dir = output_dir / session_id
    session_dir.mkdir(parents=True, exist_ok=True)

    metadata = {
        'session_id': session_id,
        'start_time': timestamp.isoformat(),
        'end_time': None,
        'place': place,
        'capture_count': 0
    }

    metadata_path = session_dir / 'session_metadata.json'
    with open(metadata_path, 'w') as f:
        json.dump(metadata, f, indent=2)

    return session_dir, metadata_path


def update_session_metadata(metadata_path, **updates):
    """Update session metadata file with new values."""
    with open(metadata_path, 'r') as f:
        metadata = json.load(f)

    metadata.update(updates)

    with open(metadata_path, 'w') as f:
        json.dump(metadata, f, indent=2)


def analyze_with_openai(image_base64, prompt, api_key):
    """Send image to OpenAI for analysis."""
    from openai import OpenAI

    client = OpenAI(api_key=api_key)

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{image_base64}"}
                    },
                ],
            }
        ],
    )

    content = response.choices[0].message.content
    content = content.split("```JSON", 1)[-1].rsplit("```", 1)[0]
    content = json.loads(content)
    return content


def capture_and_process(cam, session_dir, metadata_path, views_to_send, prompt, api_key, fov=90, output_size=(1080, 810)):
    """Capture a snapshot, generate views, save files, and optionally call LLM."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # Get snapshot
    pil_image = cam.get_snap()
    if not pil_image:
        print(f"[{timestamp}] Failed to get snapshot")
        return None

    img_np = np.array(pil_image)

    # Save original fisheye
    fisheye_path = session_dir / f"{timestamp}_fisheye.jpg"
    save_image(img_np, fisheye_path)
    print(f"[{timestamp}] Saved fisheye: {fisheye_path}")

    # Generate and save all views
    views = get_room_views(img_np, fov=fov, output_size=output_size)

    view_paths = {}
    for view_name, view_img in views.items():
        short_name = view_name[0].upper()  # N, E, S, W, B
        view_path = session_dir / f"{timestamp}_{short_name}.jpg"
        save_image(view_img, view_path)
        view_paths[short_name] = view_path
        print(f"[{timestamp}] Saved {view_name}: {view_path}")

    # Send selected views to LLM if API key provided
    if api_key and views_to_send:
        results = {}

        for view_code in views_to_send:
            view_name = VIEW_MAP.get(view_code.upper())
            if view_name and view_name in views:
                view_img = views[view_name]
                image_base64 = image_to_base64(view_img)

                print(f"[{timestamp}] Sending {view_name} view to LLM...")
                try:
                    response = analyze_with_openai(image_base64, prompt, api_key)
                    results[view_name] = response
                    print(f"[{timestamp}] LLM response for {view_name}:")
                    print(response)
                    print()
                except Exception as e:
                    print(f"[{timestamp}] LLM error for {view_name}: {e}")
                    results[view_name] = f"Error: {e}"

        # Save LLM responses
        if results:
            response_path = session_dir / f"{timestamp}_llm_responses.json"
            with open(response_path, 'w') as f:
                json.dump({
                    'timestamp': timestamp,
                    'prompt': prompt,
                    'views_analyzed': list(results.keys()),
                    'responses': results,
                }, f, indent=2)
            print(f"[{timestamp}] Saved LLM responses: {response_path}")

    # Update session metadata with incremented capture count
    with open(metadata_path, 'r') as f:
        metadata = json.load(f)
    metadata['capture_count'] += 1
    with open(metadata_path, 'w') as f:
        json.dump(metadata, f, indent=2)

    return timestamp


def main():
    parser = argparse.ArgumentParser(
        description='Capture photos from Reolink fisheye camera and analyze with LLM',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Using defaults from .env file:
  python camera_capture.py -f 60 -v N

  # Capture every 30 seconds, send multiple views
  python camera_capture.py -f 30 -v N S E W B

  # Just save photos, no LLM analysis
  python camera_capture.py -f 60

  # Single capture (no loop)
  python camera_capture.py --once

  # Override .env settings
  python camera_capture.py -i 192.168.1.100 -u admin -p password -f 60 -v N

Environment variables (can be set in .env file):
  CAMERA_IP, CAMERA_USERNAME, CAMERA_PASSWORD, OPENAI_API_KEY

View codes:
  N = North, S = South, E = East, W = West, B = Below (floor)
"""
    )

    # Camera connection (defaults from .env)
    parser.add_argument('-i', '--ip', default=os.environ.get('CAMERA_IP'),
                        help='Camera IP address (default: from CAMERA_IP env var)')
    parser.add_argument('-u', '--username', default=os.environ.get('CAMERA_USERNAME', 'admin'),
                        help='Camera username (default: from CAMERA_USERNAME env var)')
    parser.add_argument('-p', '--password', default=os.environ.get('CAMERA_PASSWORD', ''),
                        help='Camera password (default: from CAMERA_PASSWORD env var)')
    parser.add_argument('--https', action='store_true', help='Use HTTPS instead of HTTP')

    # Capture settings
    parser.add_argument('-f', '--frequency', type=int, default=60,
                        help='Capture frequency in seconds (default: 60)')
    parser.add_argument('-o', '--output', type=str, default='./data',
                        help='Output directory for saved files (default: ./data)')
    parser.add_argument('--once', action='store_true', help='Capture once and exit (no loop)')

    # View settings
    parser.add_argument('-v', '--views', nargs='+', default=[],
                        choices=['N', 'S', 'E', 'W', 'B', 'n', 's', 'e', 'w', 'b'],
                        help='Views to send to LLM: N(orth), S(outh), E(ast), W(est), B(elow)')
    parser.add_argument('--fov', type=int, default=90, help='Field of view in degrees (default: 90)')
    parser.add_argument('--size', type=int, nargs=2, default=[1080, 810],
                        metavar=('WIDTH', 'HEIGHT'), help='Output image size (default: 1080 810)')

    # LLM settings
    parser.add_argument('--prompt', type=str, default=None, help='Prompt to send to LLM')
    parser.add_argument('--api-key', type=str, default=os.environ.get('OPENAI_API_KEY'),
                        help='OpenAI API key (default: from OPENAI_API_KEY env var)')

    args = parser.parse_args()

    # Validate
    if not args.ip:
        parser.error("Camera IP required: use -i or set CAMERA_IP in .env")
    if args.views and not args.api_key:
        parser.error("--api-key or OPENAI_API_KEY environment variable required when using --views")

    # Setup output directory
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    prompt = args.prompt  
    if not prompt:
        with open("prompt.txt") as tfile:
            prompt = tfile.read()

    # Connect to camera
    print(f"Connecting to camera at {args.ip}...")
    try:
        cam = Camera(args.ip, args.username, args.password, https=args.https)
        print("Connected successfully!")
    except Exception as e:
        print(f"Failed to connect: {e}")
        return 1

    # Normalize view codes to uppercase
    views_to_send = [v.upper() for v in args.views]

    # Create session
    session_dir, metadata_path = create_session(output_dir)

    print(f"Output directory: {output_dir}")
    print(f"Session directory: {session_dir}")
    print(f"Capture frequency: {args.frequency} seconds")
    print(f"Views to analyze: {views_to_send if views_to_send else 'None (only capturing, no anlysis)'}")
    print()

    try:
        while True:
            capture_and_process(
                cam=cam,
                session_dir=session_dir,
                metadata_path=metadata_path,
                views_to_send=views_to_send,
                prompt=prompt,
                api_key=args.api_key,
                fov=args.fov,
                output_size=tuple(args.size),
            )

            if args.once:
                print("Single capture complete.")
                update_session_metadata(metadata_path, end_time=datetime.now().isoformat())
                break

            print(f"Waiting {args.frequency} seconds until next capture...")
            print()
            time.sleep(args.frequency)

    except KeyboardInterrupt:
        print("\nStopped by user.")
        update_session_metadata(metadata_path, end_time=datetime.now().isoformat())

    return 0


if __name__ == '__main__':
    exit(main())
