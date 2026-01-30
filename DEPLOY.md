# Deployment

Deployed on [Fly.io](https://fly.io) to `vibecast-viewer` app.

## Redeploy

```bash
fly deploy
```

## Set secrets (first time only)

```bash
fly secrets set AWS_ACCESS_KEY_ID="..." AWS_SECRET_ACCESS_KEY="..."
```

## View logs

```bash
fly logs
```

## SSH into running instance

```bash
fly ssh console
```
