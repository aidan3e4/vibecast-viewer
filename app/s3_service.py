"""S3 service for vibecast viewer."""

import json
import os
import re
from collections import defaultdict
from datetime import datetime
from typing import Any

import boto3
from botocore.exceptions import ClientError, NoCredentialsError, PartialCredentialsError

BUCKET_NAME = os.getenv("S3_BUCKET", "vibecast-ftp")
AWS_REGION = os.getenv("AWS_DEFAULT_REGION", "eu-central-1")


def list_vibecast_buckets() -> list[dict]:
    """List all S3 buckets whose name starts with 'vibecast'."""
    s3 = get_s3_client()
    response = s3.list_buckets()
    buckets = [
        {"bucket": b["Name"], "account": b["Name"][len("vibecast-"):]}
        for b in response.get("Buckets", [])
        if b["Name"].startswith("vibecast")
    ]
    return sorted(buckets, key=lambda b: b["account"])

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


def check_aws_credentials() -> dict[str, Any]:
    """Check if AWS credentials are configured properly.

    Returns:
        dict with 'configured' (bool) and 'message' (str) keys
    """
    try:
        s3 = get_s3_client()
        # Try to list buckets to verify credentials work
        s3.list_buckets()
        return {
            "configured": True,
            "message": "AWS credentials are configured correctly"
        }
    except NoCredentialsError:
        return {
            "configured": False,
            "message": "AWS credentials not found. Please configure AWS credentials using:\n"
                      "1. Environment variables (AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY)\n"
                      "2. AWS credentials file (~/.aws/credentials)\n"
                      "3. IAM role (if running on EC2/ECS)"
        }
    except PartialCredentialsError:
        return {
            "configured": False,
            "message": "Incomplete AWS credentials. Both AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY are required."
        }
    except ClientError as e:
        return {
            "configured": False,
            "message": f"AWS credentials error: {str(e)}"
        }
    except Exception as e:
        return {
            "configured": False,
            "message": f"Error checking AWS credentials: {str(e)}"
        }


def parse_image_filename(filename: str) -> dict | None:
    """Parse image filename to extract timestamp.

    Handles format: <name>_<digits>_YYYYMMDDHHMMSS.jpg
    """
    match = re.match(r".+_\d+_(\d{14})\.jpg", filename)
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


def get_image_stats(bucket: str = BUCKET_NAME) -> dict[str, Any]:
    """Get statistics about available images for histogram display."""
    try:
        s3 = get_s3_client()
        date_counts: dict[str, int] = defaultdict(int)
        first_date = None
        last_date = None

        paginator = s3.get_paginator("list_objects_v2")

        for page in paginator.paginate(Bucket=bucket, Prefix=f"{PREFIX_FTP_UPLOADS}/"):
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
    except (NoCredentialsError, PartialCredentialsError):
        return {
            "dates": [],
            "counts": [],
            "first_date": None,
            "last_date": None,
            "total_images": 0,
            "total_days": 0,
            "error": "credentials",
            "error_message": "AWS credentials not configured. Please set up your AWS credentials to access S3."
        }
    except ClientError as e:
        error_code = e.response.get('Error', {}).get('Code', 'Unknown')
        if error_code == 'NoSuchBucket':
            return {
                "dates": [],
                "counts": [],
                "first_date": None,
                "last_date": None,
                "total_images": 0,
                "total_days": 0,
                "error": "bucket",
                "error_message": f"S3 bucket '{bucket}' not found. Please check your configuration."
            }
        else:
            return {
                "dates": [],
                "counts": [],
                "first_date": None,
                "last_date": None,
                "total_images": 0,
                "total_days": 0,
                "error": "s3",
                "error_message": f"S3 error: {str(e)}"
            }


def list_images_by_date(date: str, bucket: str = BUCKET_NAME) -> list[dict]:
    """List raw fisheye images for a specific date.

    Args:
        date: Date in YYYY-MM-DD format
    """
    s3 = get_s3_client()
    images = []

    try:
        dt = datetime.strptime(date, "%Y-%m-%d")
        prefix = f"{PREFIX_FTP_UPLOADS}/{dt.year}/{dt.month:02d}/{dt.day:02d}/"
    except ValueError:
        return []

    paginator = s3.get_paginator("list_objects_v2")

    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
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
    bucket: str = BUCKET_NAME,
) -> list[dict]:
    """List raw fisheye images in a date/time range."""
    s3 = get_s3_client()
    images = []

    try:
        start_dt = datetime.strptime(f"{from_date} {from_time}", "%Y-%m-%d %H:%M")
        end_dt = datetime.strptime(f"{to_date} {to_time}", "%Y-%m-%d %H:%M")
    except ValueError:
        return []

    current_date = start_dt.date()
    end_date = end_dt.date()

    paginator = s3.get_paginator("list_objects_v2")

    while current_date <= end_date:
        prefix = f"{PREFIX_FTP_UPLOADS}/{current_date.year}/{current_date.month:02d}/{current_date.day:02d}/"

        for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
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


def get_presigned_url(key: str, bucket: str = BUCKET_NAME) -> str:
    """Generate presigned URL for an S3 object."""
    s3 = get_s3_client()
    return s3.generate_presigned_url(
        "get_object",
        Params={"Bucket": bucket, "Key": key},
        ExpiresIn=PRESIGN_EXPIRATION,
    )


def get_s3_uri(key: str, bucket: str = BUCKET_NAME) -> str:
    """Get S3 URI for a key."""
    return f"s3://{bucket}/{key}"


def get_unwarped_images(image_key: str, bucket: str = BUCKET_NAME) -> dict[str, dict]:
    """Check which unwarped images exist for a raw fisheye image.

    Returns dict mapping direction to {exists, key, url, rotated_exists, rotated_key, rotated_url}
    """
    s3 = get_s3_client()

    filename = image_key.split("/")[-1]
    parsed = parse_image_filename(filename)
    if not parsed:
        return {}

    dt = parsed["datetime"]
    base_name = filename.rsplit(".", 1)[0]
    unwarped_prefix = f"{PREFIX_UNWARPED}/{dt.year}/{dt.month:02d}/{dt.day:02d}/"

    result = {}
    for direction in DIRECTIONS:
        unwarped_key = f"{unwarped_prefix}{base_name}_{direction}.jpg"

        try:
            s3.head_object(Bucket=bucket, Key=unwarped_key)
            exists = True
            url = get_presigned_url(unwarped_key, bucket)
        except ClientError:
            exists = False
            url = None

        rotated_key = f"{unwarped_prefix}{base_name}_{direction}_rotated.jpg"
        try:
            s3.head_object(Bucket=bucket, Key=rotated_key)
            rotated_exists = True
            rotated_url = get_presigned_url(rotated_key, bucket)
        except ClientError:
            rotated_exists = False
            rotated_url = None

        result[direction] = {
            "exists": exists,
            "key": unwarped_key,
            "url": url,
            "direction": direction.capitalize(),
            "rotated_exists": rotated_exists,
            "rotated_key": rotated_key,
            "rotated_url": rotated_url,
        }

    return result


def batch_check_unwarped(image_keys: list[str], bucket: str = BUCKET_NAME) -> dict[str, bool]:
    """Check which images have at least one unwarped variant.

    Returns dict mapping image_key -> bool (has any unwarped image).
    """
    s3 = get_s3_client()

    date_to_basenames: dict[str, dict[str, str]] = {}
    for image_key in image_keys:
        filename = image_key.split("/")[-1]
        parsed = parse_image_filename(filename)
        if not parsed:
            continue
        dt = parsed["datetime"]
        date_prefix = f"{PREFIX_UNWARPED}/{dt.year}/{dt.month:02d}/{dt.day:02d}/"
        base_name = filename.rsplit(".", 1)[0]
        if date_prefix not in date_to_basenames:
            date_to_basenames[date_prefix] = {}
        date_to_basenames[date_prefix][base_name] = image_key

    result = {key: False for key in image_keys}

    paginator = s3.get_paginator("list_objects_v2")
    for date_prefix, basenames in date_to_basenames.items():
        for page in paginator.paginate(Bucket=bucket, Prefix=date_prefix):
            for obj in page.get("Contents", []):
                obj_filename = obj["Key"].split("/")[-1]
                # Match against known base names + direction suffix
                for base_name, image_key in basenames.items():
                    if obj_filename.startswith(base_name + "_"):
                        result[image_key] = True
                        break

    return result


def list_results_by_date(date: str, bucket: str = BUCKET_NAME) -> list[dict]:
    """List result JSON files for a specific date."""
    s3 = get_s3_client()
    results = []

    try:
        dt = datetime.strptime(date, "%Y-%m-%d")
        prefix = f"{PREFIX_RESULTS}/{dt.year}/{dt.month:02d}/{dt.day:02d}/"
    except ValueError:
        return []

    paginator = s3.get_paginator("list_objects_v2")

    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
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


def get_result_content(result_key: str, bucket: str = BUCKET_NAME) -> dict | None:
    """Fetch and parse a result JSON file from S3."""
    s3 = get_s3_client()

    try:
        response = s3.get_object(Bucket=bucket, Key=result_key)
        content = response["Body"].read().decode("utf-8")
        data = json.loads(content)

        if "unwarped_images" in data:
            for direction, uri in data["unwarped_images"].items():
                if uri.startswith("s3://"):
                    key = uri.replace(f"s3://{bucket}/", "")
                    try:
                        s3.head_object(Bucket=bucket, Key=key)
                        data["unwarped_images"][direction] = {
                            "uri": uri,
                            "url": get_presigned_url(key, bucket),
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


def list_all_results(bucket: str = BUCKET_NAME) -> list[dict]:
    """List all result JSON files across all dates."""
    s3 = get_s3_client()
    results = []

    paginator = s3.get_paginator("list_objects_v2")

    for page in paginator.paginate(Bucket=bucket, Prefix=f"{PREFIX_RESULTS}/"):
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


def get_result_stats(bucket: str = BUCKET_NAME) -> dict[str, Any]:
    """Get statistics about results for histogram display."""
    try:
        s3 = get_s3_client()
        results_generated_counts: dict[str, int] = defaultdict(int)
        images_analyzed_counts: dict[str, int] = defaultdict(int)

        paginator = s3.get_paginator("list_objects_v2")

        for page in paginator.paginate(Bucket=bucket, Prefix=f"{PREFIX_RESULTS}/"):
            for obj in page.get("Contents", []):
                key = obj["Key"]
                filename = key.split("/")[-1]

                if not filename.endswith(".json"):
                    continue

                # Fetch and parse the result JSON
                try:
                    response = s3.get_object(Bucket=bucket, Key=key)
                    content = response["Body"].read().decode("utf-8")
                    data = json.loads(content)

                    # Count for results generated histogram (by processed_at date)
                    if "processed_at" in data:
                        # processed_at format: "2026-01-28T12:09:45.462828Z"
                        processed_date = data["processed_at"].split("T")[0]
                        results_generated_counts[processed_date] += 1

                    # Count for images analyzed histogram (by image capture date)
                    if "input_uri" in data:
                        # Extract filename from input_uri
                        # e.g., s3://vibecast-ftp/ftp_uploads/2026/01/26/reolink_00_20260126233811.jpg
                        input_filename = data["input_uri"].split("/")[-1]
                        parsed = parse_image_filename(input_filename)
                        if parsed:
                            image_date = parsed["date"]
                            images_analyzed_counts[image_date] += 1

                except (ClientError, json.JSONDecodeError, KeyError):
                    # Skip malformed or inaccessible results
                    continue

        # Sort dates
        sorted_results = sorted(results_generated_counts.items())
        sorted_images = sorted(images_analyzed_counts.items())

        return {
            "results_generated": {
                "dates": [d[0] for d in sorted_results],
                "counts": [d[1] for d in sorted_results],
            },
            "images_analyzed": {
                "dates": [d[0] for d in sorted_images],
                "counts": [d[1] for d in sorted_images],
            },
            "total_results": sum(results_generated_counts.values()),
            "total_images_analyzed": sum(images_analyzed_counts.values()),
        }
    except (NoCredentialsError, PartialCredentialsError):
        return {
            "results_generated": {"dates": [], "counts": []},
            "images_analyzed": {"dates": [], "counts": []},
            "total_results": 0,
            "total_images_analyzed": 0,
            "error": "credentials",
            "error_message": "AWS credentials not configured."
        }
    except Exception as e:
        return {
            "results_generated": {"dates": [], "counts": []},
            "images_analyzed": {"dates": [], "counts": []},
            "total_results": 0,
            "total_images_analyzed": 0,
            "error": "unknown",
            "error_message": str(e)
        }
