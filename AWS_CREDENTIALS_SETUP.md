# AWS Credentials Setup Guide

The Vibecast Viewer requires AWS credentials to access S3 buckets and invoke Lambda functions.

## Quick Setup

### Option 1: Environment Variables (Recommended for development)

```bash
export AWS_ACCESS_KEY_ID="your-access-key-id"
export AWS_SECRET_ACCESS_KEY="your-secret-access-key"
export AWS_DEFAULT_REGION="eu-central-1"
```

Then start the application:
```bash
python app/main.py
```

### Option 2: AWS Credentials File (Recommended for local development)

Create or edit `~/.aws/credentials`:

```ini
[default]
aws_access_key_id = your-access-key-id
aws_secret_access_key = your-secret-access-key
```

Create or edit `~/.aws/config`:

```ini
[default]
region = eu-central-1
```

### Option 3: IAM Role (For EC2/ECS deployment)

If running on AWS infrastructure, attach an IAM role with the necessary permissions.

## Required AWS Permissions

Your IAM user or role needs the following permissions:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "s3:GetObject",
        "s3:ListBucket",
        "s3:HeadObject"
      ],
      "Resource": [
        "arn:aws:s3:::vibecast-ftp",
        "arn:aws:s3:::vibecast-ftp/*"
      ]
    },
    {
      "Effect": "Allow",
      "Action": [
        "lambda:InvokeFunction"
      ],
      "Resource": [
        "arn:aws:lambda:eu-central-1:*:function:vibecast-process-image"
      ]
    }
  ]
}
```

## Verifying Your Setup

When you start the application, you should see:

```
============================================================
Starting Vibecast Viewer...
============================================================
Lambda API URL: https://...
S3 Bucket: vibecast-ftp
AWS Region: eu-central-1

✓ AWS credentials configured correctly

============================================================
Open http://localhost:8001 in your browser
============================================================
```

If credentials are **not** configured, you'll see:

```
⚠ WARNING: AWS credentials issue detected!
  AWS credentials not found. Please configure AWS credentials using:
  1. Environment variables (AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY)
  2. AWS credentials file (~/.aws/credentials)
  3. IAM role (if running on EC2/ECS)

  The app will start, but S3 features will not work.
  Please configure your AWS credentials to access S3 and Lambda.
```

## Troubleshooting

### "NoCredentialsError"
- Credentials are not configured at all
- Solution: Use one of the setup options above

### "PartialCredentialsError"
- Only one of ACCESS_KEY_ID or SECRET_ACCESS_KEY is set
- Solution: Ensure both are configured

### "AccessDenied"
- Credentials are configured but don't have the right permissions
- Solution: Check your IAM permissions match the required permissions above

### Testing Credentials

You can test your credentials with the health check endpoint:

```bash
curl http://localhost:8001/api/health
```

This will return:
```json
{
  "status": "ok",
  "aws_credentials": {
    "configured": true,
    "message": "AWS credentials are configured correctly"
  }
}
```

## Environment Variables Reference

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `AWS_ACCESS_KEY_ID` | Yes | - | Your AWS access key ID |
| `AWS_SECRET_ACCESS_KEY` | Yes | - | Your AWS secret access key |
| `AWS_DEFAULT_REGION` | No | `eu-central-1` | AWS region |
| `S3_BUCKET` | No | `vibecast-ftp` | S3 bucket name |
| `LAMBDA_API_URL` | No | (see main.py) | Lambda API Gateway URL |
