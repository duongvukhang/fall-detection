# SafeWatch Fall Detection

SafeWatch is an edge-to-cloud fall and bed-exit detection system.

- `backend/` - FastAPI API, auth, telemetry ingest, dashboard endpoints, Alembic migrations
- `safewatch-ui/` - React/Vite dashboard deployed on Vercel
- `edge/` - Jetson Nano edge detector using YOLOv8 pose estimation
- `nginx/` - optional local reverse-proxy config

Production target:

- Supabase for Postgres
- Render for the FastAPI backend
- Vercel for the frontend dashboard
- Jetson Nano for camera inference and event transmission

## Local Development

### Backend

```bash
cd backend
pip install -r requirements.txt
alembic -c alembic.ini upgrade head
uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

Health check:

```text
http://localhost:8000/health
```

### Frontend

Create `safewatch-ui/.env`:

```env
VITE_API_URL=http://localhost:8000
VITE_WS_URL=ws://localhost:8000
```

Run:

```bash
cd safewatch-ui
npm install
npm run dev
```

Open:

```text
http://localhost:5173
```

## Cloud Deployment

### Supabase

Create a Supabase project and use the connection pooler URL, not the direct database URL.

Recommended shape:

```env
DATABASE_URL=postgresql://postgres.PROJECT_REF:PASSWORD@aws-0-REGION.pooler.supabase.com:6543/postgres?ssl=require
```

If the password contains symbols like `@`, `#`, `/`, `?`, or `:`, URL-encode it.

### Render Backend

Deploy `backend/` as a Docker web service.

Required Render environment variables:

```env
DATABASE_URL=your_supabase_pooler_url
JWT_SECRET_KEY=output_from_openssl_rand_hex_32
JWT_TTL_MINUTES=1440
ALLOWED_ORIGINS=https://your-vercel-app.vercel.app
ENV=production
WEB_CONCURRENCY=2
```

Generate the JWT secret:

```bash
openssl rand -hex 32
```

The Dockerfile runs:

```bash
alembic -c alembic.ini upgrade head
```

before starting the API.

### Vercel Frontend

Deploy `safewatch-ui/` on Vercel.

Required Vercel environment variables:

```env
VITE_API_URL=https://your-render-service.onrender.com
VITE_WS_URL=wss://your-render-service.onrender.com
```

After Vercel gives you a frontend URL, put that URL into Render:

```env
ALLOWED_ORIGINS=https://your-vercel-app.vercel.app
```

Then redeploy Render.

## Create First Facility And Edge Token

The Jetson needs an API token. Register one facility/user:

```bash
curl -X POST https://your-render-service.onrender.com/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@example.com","password":"password123","facility_name":"My Facility","ward_unit":"Ward A"}'
```

The response includes:

```json
{
  "api_token": "copy_this_value"
}
```

Save this token. The Jetson sends it in the `X-API-KEY` header.

## Running On Jetson Nano

### 1. Prepare The Jetson

Use a Jetson Nano with JetPack installed and camera support working.

Update packages:

```bash
sudo apt update
sudo apt install -y python3-pip python3-venv git libopenblas-base libopenmpi-dev
```

Create an app user and folders:

```bash
sudo useradd --create-home --shell /bin/bash safewatch || true
sudo mkdir -p /opt/safewatch /var/lib/safewatch-edge
sudo chown -R safewatch:safewatch /opt/safewatch /var/lib/safewatch-edge
```

### 2. Copy Edge Files

Copy the contents of this repo's `edge/` folder to the Jetson:

```text
/opt/safewatch
```

The Jetson folder should contain:

```text
/opt/safewatch/edge_detector.py
/opt/safewatch/requirements.txt
/opt/safewatch/yolov8n-pose.pt
/opt/safewatch/safewatch-edge.service
```

### 3. Install Python Dependencies

On the Jetson:

```bash
cd /opt/safewatch
python3 -m venv venv
./venv/bin/pip install --upgrade pip
./venv/bin/pip install -r requirements.txt
```

Note: Jetson devices often need NVIDIA/JetPack-compatible PyTorch and OpenCV packages. If `ultralytics` tries to replace a working Jetson PyTorch install, install the Jetson-compatible PyTorch first, then install the remaining requirements.

### 4. Configure Environment

Create:

```bash
sudo nano /etc/safewatch-edge.env
```

Example:

```env
CLOUD_API_URL=https://your-render-service.onrender.com
EDGE_API_KEY=your_api_token_from_registration
ROOM_NUMBER=ROOM-01
YOLO_MODEL=/opt/safewatch/yolov8n-pose.pt
PENDING_QUEUE_PATH=/var/lib/safewatch-edge/pending_events.jsonl
```

Lock down the file because it contains the API token:

```bash
sudo chmod 600 /etc/safewatch-edge.env
```

### 5. Test Camera

For a USB camera:

```bash
cd /opt/safewatch
./venv/bin/python edge_detector.py \
  --source 0 \
  --room ROOM-01 \
  --api-url https://your-render-service.onrender.com \
  --api-key your_api_token_from_registration \
  --model /opt/safewatch/yolov8n-pose.pt
```

For the Jetson CSI camera:

```bash
cd /opt/safewatch
./venv/bin/python edge_detector.py \
  --source csi \
  --room ROOM-01 \
  --api-url https://your-render-service.onrender.com \
  --api-key your_api_token_from_registration \
  --model /opt/safewatch/yolov8n-pose.pt
```

For headless SSH mode:

```bash
cd /opt/safewatch
./venv/bin/python edge_detector.py \
  --source csi \
  --room ROOM-01 \
  --api-url https://your-render-service.onrender.com \
  --api-key your_api_token_from_registration \
  --model /opt/safewatch/yolov8n-pose.pt \
  --no-display
```

Successful cloud transmission looks like:

```text
[CLOUD] /api/v1/telemetry/events -> HTTP 202
[HEARTBEAT] -> HTTP 200
```

If the network is down, events are saved to:

```text
/var/lib/safewatch-edge/pending_events.jsonl
```

and retried automatically.

### 6. Run As A System Service

Copy the service file:

```bash
sudo cp /opt/safewatch/safewatch-edge.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now safewatch-edge
```

View logs:

```bash
sudo journalctl -u safewatch-edge -f
```

Restart service:

```bash
sudo systemctl restart safewatch-edge
```

Stop service:

```bash
sudo systemctl stop safewatch-edge
```

### 7. Confirm Dashboard Events

Open your Vercel dashboard:

```text
https://your-vercel-app.vercel.app
```

When the Jetson detects a `FLOOR_FALL` or `BED_EXIT`, the event is sent to Render and should appear in the dashboard.

## Troubleshooting

### Render Cannot Reach Supabase

If Render logs show:

```text
OSError: [Errno 101] Network is unreachable
```

use the Supabase pooler URL instead of the direct database URL.

### Backend Refuses To Start

If Render logs show:

```text
ALLOWED_ORIGINS must be set
```

set Render:

```env
ALLOWED_ORIGINS=https://your-vercel-app.vercel.app
```

### Browser Shows CORS Error

Check that:

- Render backend is running.
- Vercel `VITE_API_URL` points to Render.
- Render `ALLOWED_ORIGINS` points to Vercel.
- You redeployed after changing env vars.

### WebSocket URL

Frontend uses:

```env
VITE_WS_URL=wss://your-render-service.onrender.com
```

Do not use `https://` for WebSockets.

### Jetson Sends Nothing

Check:

- API token is correct.
- `CLOUD_API_URL` is the Render backend URL.
- Render health endpoint works.
- Camera source is correct: `0` for USB, `csi` for CSI camera.
- Logs show heartbeat or cloud POST status.

## Useful Files

- `DEPLOYMENT.md` - deployment checklist
- `backend/.env.example` - backend env template
- `safewatch-ui/.env.example` - frontend env template
- `edge/.env.example` - Jetson env template
- `edge/safewatch-edge.service` - systemd service template
