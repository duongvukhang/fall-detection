# SafeWatch Deployment Checklist

Target architecture:

- Supabase: managed PostgreSQL database only.
- Render: FastAPI backend from `backend/Dockerfile`.
- Vercel: Vite/React frontend from `safewatch-ui`.
- Jetson Nano: `edge/edge_detector.py` running as a systemd service.

## 1. Supabase

Create a Supabase project and copy the pooler connection string. Use the transaction pooler URL on port `6543` for Render unless you know you need a direct database connection.

Set Render `DATABASE_URL` to the Supabase URL. The backend accepts either `postgresql://`, `postgres://`, or `postgresql+asyncpg://` and normalizes it for SQLAlchemy async.

Recommended shape:

```text
postgresql+asyncpg://postgres.PROJECT_REF:PASSWORD@aws-0-REGION.pooler.supabase.com:6543/postgres?ssl=require
```

Do not manually create tables in Supabase. Render runs `alembic -c alembic.ini upgrade head` before starting the API.

## 2. Render Backend

Create a Render Blueprint from `render.yaml`, or create a Web Service manually:

- Root directory: `backend`
- Environment: Docker
- Health check path: `/health`

Required environment variables:

```text
DATABASE_URL=your Supabase pooler URL
JWT_SECRET_KEY=output of: openssl rand -hex 32
ALLOWED_ORIGINS=https://your-vercel-app.vercel.app
ENV=production
WEB_CONCURRENCY=2
JWT_TTL_MINUTES=1440
```

After deploy, confirm:

```text
https://your-render-service.onrender.com/health
```

## 3. Vercel Frontend

Import `safewatch-ui` as the Vercel project root.

Required environment variables:

```text
VITE_API_URL=https://your-render-service.onrender.com
VITE_WS_URL=wss://your-render-service.onrender.com
```

Build command:

```text
npm run build
```

Output directory:

```text
dist
```

After Vercel gives you the production URL, add it to Render `ALLOWED_ORIGINS` and redeploy the backend.

## 4. First Account And Edge API Key

Register the facility once through the API or temporary frontend registration flow. The response returns `api_token`; save it for the Jetson.

If you need to rotate the edge token later, call:

```text
POST /api/v1/auth/rotate-token
Authorization: Bearer <dashboard JWT>
```

## 5. Jetson Nano

Copy the `edge` folder and `edge/yolov8n-pose.pt` to:

```text
/opt/safewatch
```

Create `/etc/safewatch-edge.env` from `edge/.env.example`:

```text
CLOUD_API_URL=https://your-render-service.onrender.com
EDGE_API_KEY=api_token_from_registration
ROOM_NUMBER=ROOM-01
YOLO_MODEL=/opt/safewatch/yolov8n-pose.pt
PENDING_QUEUE_PATH=/var/lib/safewatch-edge/pending_events.jsonl
```

Install Python dependencies in a virtualenv. On Jetson, prefer NVIDIA/JetPack-compatible PyTorch and OpenCV wheels if `pip install ultralytics` tries to replace them.

```text
python3 -m venv /opt/safewatch/venv
/opt/safewatch/venv/bin/pip install -r /opt/safewatch/requirements.txt
```

Install the service:

```text
sudo cp /opt/safewatch/safewatch-edge.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now safewatch-edge
sudo journalctl -u safewatch-edge -f
```

Use `--source csi` for the Jetson CSI camera, or change the service to `--source 0` for a USB camera.

## 6. Still Missing Before Real Production

- A proper registration/admin flow in the frontend, or a documented one-time setup script.
- Image upload storage if you want event verification photos instead of `image_url=null`.
- Monitoring/alerts for Render service failures and Jetson heartbeat absence.
- Backups and retention rules for Supabase.
- HTTPS production domains instead of platform preview URLs.
- End-to-end smoke tests for register, login, telemetry ingest, dashboard reads, and WebSocket connection.
