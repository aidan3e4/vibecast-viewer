"""Vibecast Viewer - FastAPI application for exploring S3 images."""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any

import boto3
import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from starlette.requests import Request

from app import s3_service

load_dotenv()

app = FastAPI(title="Vibecast Viewer")

# Configuration
APP_DIR = Path(__file__).parent
templates = Jinja2Templates(directory=APP_DIR / "templates")

# Lambda API Gateway URL
LAMBDA_API_URL = os.getenv(
    "LAMBDA_API_URL",
    "https://ck8k8vbs36.execute-api.eu-central-1.amazonaws.com/process",
)


class ProcessRequest(BaseModel):
    s3_uri: str
    unwarp: bool = True  # Perform fisheye unwarping
    analyze: bool = True  # Perform LLM analysis
    prompt: str | None = None
    views_to_analyze: list[str] | None = None  # e.g., ["N", "S", "E", "W", "B"] - only for unwarp+analyze


# ============================================================================
# Pages
# ============================================================================


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """Main viewer page."""
    today = datetime.now().strftime("%Y-%m-%d")
    return templates.TemplateResponse(
        "viewer.html",
        {
            "request": request,
            "default_date": today,
        },
    )


# ============================================================================
# API Endpoints - Stats & Images
# ============================================================================


@app.get("/api/health")
async def health_check() -> dict[str, Any]:
    """Check API and AWS credentials health."""
    creds_check = s3_service.check_aws_credentials()
    return {
        "status": "ok" if creds_check["configured"] else "degraded",
        "aws_credentials": creds_check
    }


@app.get("/api/stats")
async def get_stats() -> dict[str, Any]:
    """Get image statistics for histogram."""
    # This now returns error info in the response instead of raising exceptions
    return s3_service.get_image_stats()


@app.get("/api/images")
async def list_images(
    date: str | None = None,
    from_date: str | None = None,
    to_date: str | None = None,
    from_time: str = "00:00",
    to_time: str = "23:59",
) -> dict[str, Any]:
    """List images for a date or date range."""
    try:
        if from_date and to_date:
            images = s3_service.list_images_by_range(from_date, to_date, from_time, to_time)
        elif date:
            images = s3_service.list_images_by_date(date)
        else:
            return {"images": [], "count": 0, "error": "date or from_date/to_date required"}

        # Add presigned URLs
        for img in images:
            img["url"] = s3_service.get_presigned_url(img["key"])
        return {"images": images, "count": len(images)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/image-url")
async def get_image_url(key: str) -> dict[str, str]:
    """Get presigned URL for an image."""
    try:
        url = s3_service.get_presigned_url(key)
        return {"url": url}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/unwarped")
async def get_unwarped(image_key: str) -> dict[str, Any]:
    """Get unwarped images for a raw fisheye image."""
    try:
        unwarped = s3_service.get_unwarped_images(image_key)
        return {"unwarped": unwarped, "image_key": image_key}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# API Endpoints - Processing
# ============================================================================


@app.post("/api/process")
async def process_image(req: ProcessRequest) -> dict[str, Any]:
    """Process an image via Lambda."""
    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            payload = {
                "input_s3_uri": req.s3_uri,
                "unwarp": req.unwarp,
                "analyze": req.analyze,
            }
            if req.prompt:
                payload["prompt"] = req.prompt
            # Only include views_to_analyze for unwarp+analyze mode
            if req.unwarp and req.analyze:
                payload["views_to_analyze"] = req.views_to_analyze or ["N", "S", "E", "W", "B"]

            response = await client.post(LAMBDA_API_URL, json=payload)

            if response.status_code != 200:
                raise HTTPException(
                    status_code=response.status_code,
                    detail=f"Lambda error: {response.text}",
                )

            return response.json()
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="Lambda processing timeout")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/unwarp")
async def unwarp_image(image_key: str) -> dict[str, Any]:
    """Unwarp an image via Lambda function (direct invocation).

    Args:
        image_key: S3 key of the image (e.g., ftp_uploads/2026/01/26/image.jpg)
    """
    try:
        # Convert image key to S3 URI
        s3_uri = s3_service.get_s3_uri(image_key)

        # Invoke Lambda function directly
        lambda_client = boto3.client('lambda', region_name=s3_service.AWS_REGION)

        payload = {
            "input_s3_uri": s3_uri,
            "unwarp": True,
            "analyze": False,
        }

        response = lambda_client.invoke(
            FunctionName='vibecast-process-image',
            InvocationType='RequestResponse',
            Payload=json.dumps(payload)
        )

        # Parse response
        response_payload = json.loads(response['Payload'].read())

        # Parse body if it's a JSON string (Lambda returns stringified JSON for API Gateway compatibility)
        body = response_payload.get('body', {})
        if isinstance(body, str):
            body = json.loads(body)

        # Check for errors in the response
        if response_payload.get('statusCode') != 200:
            error_msg = body.get('error', 'Unknown error')
            raise HTTPException(
                status_code=response_payload.get('statusCode', 500),
                detail=f"Lambda error: {error_msg}"
            )

        return body

    except boto3.exceptions.botocore.exceptions.NoCredentialsError:
        raise HTTPException(
            status_code=500,
            detail="AWS credentials not configured. Please set up your AWS credentials to invoke Lambda functions."
        )
    except boto3.exceptions.botocore.exceptions.PartialCredentialsError:
        raise HTTPException(
            status_code=500,
            detail="Incomplete AWS credentials. Both AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY are required."
        )
    except Exception as e:
        error_str = str(e)
        if "credentials" in error_str.lower():
            raise HTTPException(
                status_code=500,
                detail=f"AWS credentials error: {error_str}"
            )
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# API Endpoints - Results
# ============================================================================


@app.get("/api/result-stats")
async def get_result_stats() -> dict[str, Any]:
    """Get result statistics for histograms."""
    return s3_service.get_result_stats()


@app.get("/api/results")
async def list_results(date: str | None = None) -> dict[str, Any]:
    """List result files, optionally filtered by date."""
    try:
        if date:
            results = s3_service.list_results_by_date(date)
        else:
            results = s3_service.list_all_results()
        return {"results": results, "count": len(results)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/result")
async def get_result(key: str) -> dict[str, Any]:
    """Get result JSON content."""
    try:
        content = s3_service.get_result_content(key)
        if content is None:
            raise HTTPException(status_code=404, detail="Result not found")
        return content
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Main
# ============================================================================

if __name__ == "__main__":
    import uvicorn

    print("=" * 60)
    print("Starting Vibecast Viewer...")
    print("=" * 60)
    print(f"Lambda API URL: {LAMBDA_API_URL}")
    print(f"S3 Bucket: {s3_service.BUCKET_NAME}")
    print(f"AWS Region: {s3_service.AWS_REGION}")
    print()

    # Check AWS credentials
    creds_check = s3_service.check_aws_credentials()
    if creds_check["configured"]:
        print("✓ AWS credentials configured correctly")
    else:
        print("⚠ WARNING: AWS credentials issue detected!")
        print(f"  {creds_check['message']}")
        print()
        print("  The app will start, but S3 features will not work.")
        print("  Please configure your AWS credentials to access S3 and Lambda.")
        print()

    print("=" * 60)
    print("Open http://localhost:8001 in your browser")
    print("=" * 60)
    print()

    uvicorn.run(app, host="0.0.0.0", port=8001)
