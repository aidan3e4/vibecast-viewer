"""S3 service for vibecast viewer."""

import json
import os
import re
from collections import defaultdict
from datetime import datetime
from typing import Any

import boto3
from botocore.exceptions import ClientError

BUCKET_NAME = os.getenv("S3_BUCKET", "vibecast-ftp")
AWS_REGION = os.getenv("AWS_DEFAULT_REGION", "eu-central-1")

# Prefixes in the bucket
PREFIX_FTP_UPLOADS = "ftp_uploads"
PREFIX_UNWARPED = "unwarped"
PREFIX_RESULTS = "results"

# Directions for unwarped images
DIRECTIONS = ["north", "south", "east", "west", "below"]

# Presigned URL expiration (1 hour)
PRESIGN_EXPIRATION = 3600


def get_s3_client():
    """Get boto3 S3 client."""
    return boto3.client("s3", region_name=AWS_REGION)


def parse_image_filename(filename: str) -> dict | None:
    """Parse image filename to extract timestamp.

    Handles formats:
    - reolink_00_YYYYMMDDHHMMSS.jpg
    - Reolink_00_YYYYMMDDHHMMSS.jpg
    """
    match = re.match(r"[Rr]eolink_\d+_(\d{14})\.jpg", filename)
    if not match:
        return None

    timestamp_str = match.group(1)
    try:
        dt = datetime.strptime(timestamp_str, "%Y%m%d%H%M%S")
        return {
            "timestamp": timestamp_str,
            "datetime": dt,
            "date": dt.strftime("%Y-%m-%d"),
            "time": dt.strftime("%H:%M:%S"),
        }
    except ValueError:
        return None


def get_image_stats() -> dict[str, Any]:
    """Get statistics about available images for histogram display."""
    s3 = get_s3_client()
    date_counts: dict[str, int] = defaultdict(int)
    first_date = None
    last_date = None

    paginator = s3.get_paginator("list_objects_v2")

    for page in paginator.paginate(Bucket=BUCKET_NAME, Prefix=f"{PREFIX_FTP_UPLOADS}/"):
        for obj in page.get("Contents", []):
            key = obj["Key"]
            filename = key.split("/")[-1]

            if not filename.lower().endswith(".jpg"):
                continue

            parsed = parse_image_filename(filename)
            if not parsed:
                continue

            date_str = parsed["date"]
            date_counts[date_str] += 1

            if first_date is None or parsed["datetime"] < first_date:
                first_date = parsed["datetime"]
            if last_date is None or parsed["datetime"] > last_date:
                last_date = parsed["datetime"]

    sorted_dates = sorted(date_counts.items())

    return {
        "dates": [d[0] for d in sorted_dates],
        "counts": [d[1] for d in sorted_dates],
        "first_date": first_date.strftime("%Y-%m-%d") if first_date else None,
        "last_date": last_date.strftime("%Y-%m-%d") if last_date else None,
        "total_images": sum(date_counts.values()),
        "total_days": len(date_counts),
    }


def list_images_by_date(date: str) -> list[dict]:
    """List raw fisheye images for a specific date.

    Args:
        date: Date in YYYY-MM-DD format
    """
    s3 = get_s3_client()
    images = []

    # Parse date to get year/month/day
    try:
        dt = datetime.strptime(date, "%Y-%m-%d")
        prefix = f"{PREFIX_FTP_UPLOADS}/{dt.year}/{dt.month:02d}/{dt.day:02d}/"
    except ValueError:
        return []

    paginator = s3.get_paginator("list_objects_v2")

    for page in paginator.paginate(Bucket=BUCKET_NAME, Prefix=prefix):
        for obj in page.get("Contents", []):
            key = obj["Key"]
            filename = key.split("/")[-1]

            if not filename.lower().endswith(".jpg"):
                continue

            parsed = parse_image_filename(filename)
            if not parsed:
                continue

            images.append(
                {
                    "key": key,
                    "filename": filename,
                    "timestamp": parsed["timestamp"],
                    "date": parsed["date"],
                    "time": parsed["time"],
                    "size": obj.get("Size", 0),
                }
            )

    # Sort by timestamp
    images.sort(key=lambda x: x["timestamp"])
    return images


def list_images_by_range(
    from_date: str,
    to_date: str,
    from_time: str = "00:00",
    to_time: str = "23:59",
) -> list[dict]:
    """List raw fisheye images in a date/time range.

    Args:
        from_date: Start date in YYYY-MM-DD format
        to_date: End date in YYYY-MM-DD format
        from_time: Start time in HH:MM format (default 00:00)
        to_time: End time in HH:MM format (default 23:59)
    """
    s3 = get_s3_client()
    images = []

    # Parse datetime range
    try:
        start_dt = datetime.strptime(f"{from_date} {from_time}", "%Y-%m-%d %H:%M")
        end_dt = datetime.strptime(f"{to_date} {to_time}", "%Y-%m-%d %H:%M")
    except ValueError:
        return []

    # Get all dates in range
    current_date = start_dt.date()
    end_date = end_dt.date()

    paginator = s3.get_paginator("list_objects_v2")

    while current_date <= end_date:
        prefix = f"{PREFIX_FTP_UPLOADS}/{current_date.year}/{current_date.month:02d}/{current_date.day:02d}/"

        for page in paginator.paginate(Bucket=BUCKET_NAME, Prefix=prefix):
            for obj in page.get("Contents", []):
                key = obj["Key"]
                filename = key.split("/")[-1]

                if not filename.lower().endswith(".jpg"):
                    continue

                parsed = parse_image_filename(filename)
                if not parsed:
                    continue

                # Check if within time range
                img_dt = parsed["datetime"]
                if start_dt <= img_dt <= end_dt:
                    images.append(
                        {
                            "key": key,
                            "filename": filename,
                            "timestamp": parsed["timestamp"],
                            "date": parsed["date"],
                            "time": parsed["time"],
                            "size": obj.get("Size", 0),
                        }
                    )

        # Move to next day
        from datetime import timedelta

        current_date = current_date + timedelta(days=1)

    # Sort by timestamp
    images.sort(key=lambda x: x["timestamp"])
    return images


def get_presigned_url(key: str) -> str:
    """Generate presigned URL for an S3 object."""
    s3 = get_s3_client()
    return s3.generate_presigned_url(
        "get_object",
        Params={"Bucket": BUCKET_NAME, "Key": key},
        ExpiresIn=PRESIGN_EXPIRATION,
    )


def get_s3_uri(key: str) -> str:
    """Get S3 URI for a key."""
    return f"s3://{BUCKET_NAME}/{key}"


def get_unwarped_images(image_key: str) -> dict[str, dict]:
    """Check which unwarped images exist for a raw fisheye image.

    Returns dict mapping direction to {exists, key, url}
    """
    s3 = get_s3_client()

    # Parse the original image key
    # ftp_uploads/2026/01/26/reolink_00_20260126233811.jpg
    filename = image_key.split("/")[-1]
    parsed = parse_image_filename(filename)
    if not parsed:
        return {}

    # Build unwarped path
    # unwarped/2026/01/26/reolink_00_20260126233811_north.jpg
    dt = parsed["datetime"]
    base_name = filename.rsplit(".", 1)[0]  # Remove .jpg
    unwarped_prefix = f"{PREFIX_UNWARPED}/{dt.year}/{dt.month:02d}/{dt.day:02d}/"

    result = {}
    for direction in DIRECTIONS:
        unwarped_key = f"{unwarped_prefix}{base_name}_{direction}.jpg"

        # Check if exists
        try:
            s3.head_object(Bucket=BUCKET_NAME, Key=unwarped_key)
            exists = True
            url = get_presigned_url(unwarped_key)
        except ClientError:
            exists = False
            url = None

        result[direction] = {
            "exists": exists,
            "key": unwarped_key,
            "url": url,
            "direction": direction.capitalize(),
        }

    return result


def list_results_by_date(date: str) -> list[dict]:
    """List result JSON files for a specific date."""
    s3 = get_s3_client()
    results = []

    # Parse date
    try:
        dt = datetime.strptime(date, "%Y-%m-%d")
        prefix = f"{PREFIX_RESULTS}/{dt.year}/{dt.month:02d}/{dt.day:02d}/"
    except ValueError:
        return []

    paginator = s3.get_paginator("list_objects_v2")

    for page in paginator.paginate(Bucket=BUCKET_NAME, Prefix=prefix):
        for obj in page.get("Contents", []):
            key = obj["Key"]
            filename = key.split("/")[-1]

            if not filename.endswith(".json"):
                continue

            results.append(
                {
                    "key": key,
                    "filename": filename,
                    "last_modified": obj.get("LastModified").isoformat() if obj.get("LastModified") else None,
                    "size": obj.get("Size", 0),
                }
            )

    # Sort by last modified (newest first)
    results.sort(key=lambda x: x["last_modified"] or "", reverse=True)
    return results


def get_result_content(result_key: str) -> dict | None:
    """Fetch and parse a result JSON file from S3."""
    s3 = get_s3_client()

    try:
        response = s3.get_object(Bucket=BUCKET_NAME, Key=result_key)
        content = response["Body"].read().decode("utf-8")
        data = json.loads(content)

        # Add presigned URLs for unwarped images in the result
        if "unwarped_images" in data:
            for direction, uri in data["unwarped_images"].items():
                # Convert s3://bucket/key to presigned URL
                if uri.startswith("s3://"):
                    key = uri.replace(f"s3://{BUCKET_NAME}/", "")
                    try:
                        s3.head_object(Bucket=BUCKET_NAME, Key=key)
                        data["unwarped_images"][direction] = {
                            "uri": uri,
                            "url": get_presigned_url(key),
                            "exists": True,
                        }
                    except ClientError:
                        data["unwarped_images"][direction] = {
                            "uri": uri,
                            "url": None,
                            "exists": False,
                        }

        return data
    except ClientError:
        return None


def list_all_results() -> list[dict]:
    """List all result JSON files across all dates."""
    s3 = get_s3_client()
    results = []

    paginator = s3.get_paginator("list_objects_v2")

    for page in paginator.paginate(Bucket=BUCKET_NAME, Prefix=f"{PREFIX_RESULTS}/"):
        for obj in page.get("Contents", []):
            key = obj["Key"]
            filename = key.split("/")[-1]

            if not filename.endswith(".json"):
                continue

            # Extract date from path
            parts = key.split("/")
            if len(parts) >= 4:
                date_str = f"{parts[1]}-{parts[2]}-{parts[3]}"
            else:
                date_str = None

            results.append(
                {
                    "key": key,
                    "filename": filename,
                    "date": date_str,
                    "last_modified": obj.get("LastModified").isoformat() if obj.get("LastModified") else None,
                    "size": obj.get("Size", 0),
                }
            )

    # Sort by last modified (newest first)
    results.sort(key=lambda x: x["last_modified"] or "", reverse=True)
    return results
