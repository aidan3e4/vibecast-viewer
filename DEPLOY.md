# Deployment

Deployed on [Fly.io](https://fly.io) to `vibecast-viewer` app.

## First Time Setup

Run this once to set AWS secrets from `.env` and deploy the app:

```bash
./deploy_first_time.sh
```

This will:
1. Authenticate with Fly.io (opens browser if not already logged in)
2. Read `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY` from `.env` and push them as Fly secrets
3. Deploy the app

## Redeploying

To push a new version of the app:

```bash
./deploy_restart.sh
```

## View logs

```bash
fly logs
```

## SSH into running instance

```bash
fly ssh console
```
