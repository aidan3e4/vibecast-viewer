# Vibecast Viewer

A web application for browsing, processing, and analyzing images stored in S3.

## Features

- **Browse Images**: Explore images uploaded to S3, organized by date with histogram visualization
- **Process Images**: Unwarp fisheye images and run LLM-based analysis via AWS Lambda
- **View Results**: Browse processing results with unwarped images and analysis responses

## Tech Stack

- **Backend**: FastAPI + Uvicorn
- **Frontend**: Vanilla JavaScript with Chart.js
- **Cloud**: AWS S3 for storage, Lambda for processing
- **Deployment**: Docker, Fly.io

## Setup

### Environment Variables

```bash
AWS_ACCESS_KEY_ID=your_access_key
AWS_SECRET_ACCESS_KEY=your_secret_key
AWS_DEFAULT_REGION=eu-central-1  # optional, defaults to eu-central-1
S3_BUCKET=vibecast-ftp           # optional, defaults to vibecast-ftp
```

### Run Locally

```bash
# Install dependencies
pip install -e .

# Start the server
uvicorn app.main:app --reload --port 8001
```

### Run with Docker

```bash
docker build -t vibecast-viewer .
docker run -p 8001:8001 \
  -e AWS_ACCESS_KEY_ID=... \
  -e AWS_SECRET_ACCESS_KEY=... \
  vibecast-viewer
```

Then open http://localhost:8001

## Usage

1. **Explorer Tab**: Select a date range to browse available images
2. **Process Tab**: Select images and configure processing (unwarp, analyze)
3. **Results Tab**: View processing results filtered by date
