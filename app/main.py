"""Vibecast Viewer - FastAPI application for exploring S3 images."""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any

import boto3
import httpx
from botocore.exceptions import ClientError
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
LAMBDA_API_BASE = LAMBDA_API_URL.rsplit("/", 1)[0]  # Base URL without /process


class ProcessRequest(BaseModel):
    s3_uri: str
    unwarp: bool = True  # Perform fisheye unwarping
    analyze: bool = True  # Perform LLM analysis
    prompt: str | None = None
    views_to_analyze: list[str] | None = None  # e.g., ["N", "S", "E", "W", "B"] - only for unwarp+analyze
    model: str | None = None  # LLM model to use for analysis


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


@app.get("/api/models")
async def get_models() -> dict[str, Any]:
    """Get available models from Lambda API."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(f"{LAMBDA_API_BASE}/models")
            if response.status_code != 200:
                raise HTTPException(
                    status_code=response.status_code,
                    detail=f"Failed to fetch models: {response.text}",
                )
            data = response.json()
            # Handle case where body is JSON string (Lambda response format)
            if "body" in data and isinstance(data["body"], str):
                return json.loads(data["body"])
            return data
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="Timeout fetching models")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


def _parse_lambda_response(data: dict) -> dict:
    """Parse Lambda response, handling JSON string body."""
    if "body" in data and isinstance(data["body"], str):
        return json.loads(data["body"])
    return data


@app.get("/api/prompts")
async def list_prompts(all: bool = False, bucket: str = s3_service.BUCKET_NAME) -> dict[str, Any]:
    """List all prompts (names only, or all versions if all=true)."""
    bucket_suffix = bucket.removeprefix("vibecast-")
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            params: dict[str, Any] = {"bucket_suffix": bucket_suffix}
            if all:
                params["all"] = "true"
            response = await client.get(f"{LAMBDA_API_BASE}/prompts", params=params)
            if response.status_code != 200:
                raise HTTPException(response.status_code, f"Failed to fetch prompts: {response.text}")
            return _parse_lambda_response(response.json())
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="Timeout fetching prompts")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/prompts/{name}")
async def get_prompt(name: str, bucket: str = s3_service.BUCKET_NAME) -> dict[str, Any]:
    """Get latest version of a prompt."""
    bucket_suffix = bucket.removeprefix("vibecast-")
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(f"{LAMBDA_API_BASE}/prompts/{name}", params={"bucket_suffix": bucket_suffix})
            if response.status_code != 200:
                raise HTTPException(response.status_code, f"Prompt not found: {response.text}")
            return _parse_lambda_response(response.json())
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="Timeout fetching prompt")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/prompts/{name}/{version}")
async def get_prompt_version(name: str, version: int, bucket: str = s3_service.BUCKET_NAME) -> dict[str, Any]:
    """Get specific version of a prompt."""
    bucket_suffix = bucket.removeprefix("vibecast-")
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(f"{LAMBDA_API_BASE}/prompts/{name}/{version}", params={"bucket_suffix": bucket_suffix})
            if response.status_code != 200:
                raise HTTPException(response.status_code, f"Prompt version not found: {response.text}")
            return _parse_lambda_response(response.json())
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="Timeout fetching prompt")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class PromptCreate(BaseModel):
    name: str
    content: str
    bucket: str = s3_service.BUCKET_NAME


@app.post("/api/prompts")
async def save_prompt(req: PromptCreate) -> dict[str, Any]:
    """Create new prompt or push new version."""
    bucket_suffix = req.bucket.removeprefix("vibecast-")
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                f"{LAMBDA_API_BASE}/prompts",
                json={"name": req.name, "content": req.content, "bucket_suffix": bucket_suffix}
            )
            if response.status_code not in (200, 201):
                raise HTTPException(response.status_code, f"Failed to save prompt: {response.text}")
            return _parse_lambda_response(response.json())
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="Timeout saving prompt")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/accounts")
async def list_accounts() -> dict[str, Any]:
    """List all vibecast S3 accounts (buckets starting with 'vibecast')."""
    try:
        accounts = s3_service.list_vibecast_buckets()
    except Exception:
        accounts = []
    default = s3_service.BUCKET_NAME
    if not accounts:
        name = default[len("vibecast-"):] if default.startswith("vibecast-") else default
        accounts = [{"bucket": default, "account": name}]
    return {"accounts": accounts, "default": default}


class CreateAccountRequest(BaseModel):
    account: str
    password: str | None = None


@app.post("/api/accounts")
async def create_account(req: CreateAccountRequest) -> dict[str, Any]:
    """Create a new vibecast account by provisioning an S3 bucket."""
    account = req.account.strip().lower()
    if not account:
        raise HTTPException(status_code=400, detail="Account name cannot be empty")
    if not account.replace("-", "").isalnum():
        raise HTTPException(status_code=400, detail="Account name may only contain letters, numbers, and hyphens")
    bucket = f"vibecast-{account}"
    try:
        s3 = s3_service.get_s3_client()
        kwargs: dict[str, Any] = {"Bucket": bucket}
        if s3_service.AWS_REGION != "us-east-1":
            kwargs["CreateBucketConfiguration"] = {"LocationConstraint": s3_service.AWS_REGION}
        s3.create_bucket(**kwargs)
    except ClientError as e:
        code = e.response["Error"]["Code"]
        if code in ("BucketAlreadyOwnedByYou", "BucketAlreadyExists"):
            pass
        else:
            raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    if req.password:
        try:
            s3 = s3_service.get_s3_client()
            config = {"password": req.password}
            s3.put_object(Bucket=bucket, Key="config.json", Body=json.dumps(config), ContentType="application/json")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Bucket created but failed to save config: {e}")

    return {"bucket": bucket, "account": account}


class VerifyAccountRequest(BaseModel):
    password: str


@app.post("/api/accounts/{bucket}/verify")
async def verify_account(bucket: str, req: VerifyAccountRequest) -> dict[str, Any]:
    """Verify the password for an account by checking config.json in its S3 bucket."""
    try:
        s3 = s3_service.get_s3_client()
        obj = s3.get_object(Bucket=bucket, Key="config.json")
        config = json.loads(obj["Body"].read())
    except ClientError as e:
        if e.response["Error"]["Code"] in ("NoSuchKey", "NoSuchBucket"):
            # No config.json means no password set — allow access
            return {"ok": True}
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    stored = config.get("password")
    if not stored:
        return {"ok": True}
    if req.password != stored:
        raise HTTPException(status_code=401, detail="Incorrect password")
    return {"ok": True}


class ChangePasswordRequest(BaseModel):
    old_password: str | None = None
    new_password: str


@app.post("/api/accounts/{bucket}/password")
async def change_password(bucket: str, req: ChangePasswordRequest) -> dict[str, Any]:
    """Change the password for an account."""
    s3 = s3_service.get_s3_client()

    # Read existing config
    config: dict[str, Any] = {}
    try:
        obj = s3.get_object(Bucket=bucket, Key="config.json")
        config = json.loads(obj["Body"].read())
    except ClientError as e:
        if e.response["Error"]["Code"] not in ("NoSuchKey", "NoSuchBucket"):
            raise HTTPException(status_code=500, detail=str(e))

    # Verify old password if one is set
    stored = config.get("password")
    if stored and req.old_password != stored:
        raise HTTPException(status_code=401, detail="Current password is incorrect")

    config["password"] = req.new_password
    try:
        s3.put_object(Bucket=bucket, Key="config.json", Body=json.dumps(config), ContentType="application/json")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return {"ok": True}


@app.get("/api/stats")
async def get_stats(bucket: str = s3_service.BUCKET_NAME) -> dict[str, Any]:
    """Get image statistics for histogram."""
    return s3_service.get_image_stats(bucket=bucket)


@app.get("/api/images")
async def list_images(
    date: str | None = None,
    from_date: str | None = None,
    to_date: str | None = None,
    from_time: str = "00:00",
    to_time: str = "23:59",
    bucket: str = s3_service.BUCKET_NAME,
) -> dict[str, Any]:
    """List images for a date or date range."""
    try:
        if from_date and to_date:
            images = s3_service.list_images_by_range(from_date, to_date, from_time, to_time, bucket=bucket)
        elif date:
            images = s3_service.list_images_by_date(date, bucket=bucket)
        else:
            return {"images": [], "count": 0, "error": "date or from_date/to_date required"}

        for img in images:
            img["url"] = s3_service.get_presigned_url(img["key"], bucket=bucket)
        return {"images": images, "count": len(images)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/image-url")
async def get_image_url(key: str, bucket: str = s3_service.BUCKET_NAME) -> dict[str, str]:
    """Get presigned URL for an image."""
    try:
        url = s3_service.get_presigned_url(key, bucket=bucket)
        return {"url": url}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/unwarped-status")
async def unwarped_status(request: dict[str, Any], bucket: str = s3_service.BUCKET_NAME) -> dict[str, Any]:
    """Batch check which images have unwarped variants."""
    try:
        image_keys = request.get("image_keys", [])
        status = s3_service.batch_check_unwarped(image_keys, bucket=bucket)
        return {"status": status}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/unwarped")
async def get_unwarped(image_key: str, bucket: str = s3_service.BUCKET_NAME) -> dict[str, Any]:
    """Get unwarped images for a raw fisheye image."""
    try:
        unwarped = s3_service.get_unwarped_images(image_key, bucket=bucket)
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
            if req.model:
                payload["model"] = req.model
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
async def unwarp_image(image_key: str, bucket: str = s3_service.BUCKET_NAME) -> dict[str, Any]:
    """Unwarp an image via Lambda function (direct invocation).

    Args:
        image_key: S3 key of the image (e.g., ftp_uploads/2026/01/26/image.jpg)
    """
    try:
        # Convert image key to S3 URI
        s3_uri = s3_service.get_s3_uri(image_key, bucket=bucket)

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


@app.post("/api/rotate")
async def rotate_image(image_key: str, angle: float, bucket: str = s3_service.BUCKET_NAME) -> dict[str, Any]:
    """Rotate an unwarped image by a given angle via Lambda.

    Args:
        image_key: S3 key of the unwarped image
        angle: Rotation angle in degrees clockwise
    """
    try:
        s3_uri = s3_service.get_s3_uri(image_key, bucket=bucket)

        lambda_client = boto3.client('lambda', region_name=s3_service.AWS_REGION)

        payload = {
            "input_s3_uri": s3_uri,
            "rotate": True,
            "rotation_angle": angle,
        }

        response = lambda_client.invoke(
            FunctionName='vibecast-process-image',
            InvocationType='RequestResponse',
            Payload=json.dumps(payload)
        )

        response_payload = json.loads(response['Payload'].read())

        body = response_payload.get('body', {})
        if isinstance(body, str):
            body = json.loads(body)

        if response_payload.get('statusCode') != 200:
            error_msg = body.get('error', 'Unknown error')
            raise HTTPException(
                status_code=response_payload.get('statusCode', 500),
                detail=f"Lambda error: {error_msg}"
            )

        return body

    except HTTPException:
        raise
    except Exception as e:
        error_str = str(e)
        if "credentials" in error_str.lower():
            raise HTTPException(status_code=500, detail=f"AWS credentials error: {error_str}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/rotated")
async def delete_rotated_image(image_key: str, bucket: str = s3_service.BUCKET_NAME) -> dict[str, Any]:
    """Delete the rotated variant of an unwarped image.

    Args:
        image_key: S3 key of the original unwarped image (not the rotated one)
    """
    try:
        name_without_ext, ext = image_key.rsplit(".", 1)
        rotated_key = f"{name_without_ext}_rotated.{ext}"

        s3 = s3_service.get_s3_client()
        s3.delete_object(Bucket=bucket, Key=rotated_key)

        return {"deleted": rotated_key}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# API Endpoints - Results
# ============================================================================


@app.get("/api/result-stats")
async def get_result_stats(bucket: str = s3_service.BUCKET_NAME) -> dict[str, Any]:
    """Get result statistics for histograms."""
    return s3_service.get_result_stats(bucket=bucket)


@app.get("/api/results")
async def list_results(date: str | None = None, bucket: str = s3_service.BUCKET_NAME) -> dict[str, Any]:
    """List result files, optionally filtered by date."""
    try:
        if date:
            results = s3_service.list_results_by_date(date, bucket=bucket)
        else:
            results = s3_service.list_all_results(bucket=bucket)
        return {"results": results, "count": len(results)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/result")
async def get_result(key: str, bucket: str = s3_service.BUCKET_NAME) -> dict[str, Any]:
    """Get result JSON content."""
    try:
        content = s3_service.get_result_content(key, bucket=bucket)
        if content is None:
            raise HTTPException(status_code=404, detail="Result not found")
        return content
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class CrowdRequest(BaseModel):
    bucket_suffix: str
    timestamp: str
    interval_seconds: int = 60
    num_images: int = 3
    model_id: str = "gpt-4o"
    views: list[str] = ["below", "north", "east", "south", "west"]


@app.post("/api/crowd")
async def get_crowd(req: CrowdRequest) -> Any:
    """Call the Lambda crowd insights endpoint."""
    url = f"{LAMBDA_API_BASE}/insights/crowd"
    payload = {
        "bucket_suffix": req.bucket_suffix,
        "timestamp": req.timestamp,
        "interval_seconds": req.interval_seconds,
        "num_images": req.num_images,
        "model_id": req.model_id,
        "views": req.views,
    }
    async with httpx.AsyncClient(timeout=120) as client:
        try:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            data = resp.json()
            if "body" in data and isinstance(data["body"], str):
                return json.loads(data["body"])
            return data
        except httpx.HTTPStatusError as e:
            raise HTTPException(status_code=e.response.status_code, detail=e.response.text)
        except Exception as e:
            raise HTTPException(status_code=502, detail=str(e))


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
