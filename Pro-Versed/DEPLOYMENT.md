# PRO-VERSED — Deployment & Cloud Hosting Guide

**PRO-VERSED** is engineered for zero-friction deployment to any cloud hosting provider, container platform, VPS, or local environment.

---

## 🚀 Quick Deployment Options

### Option 1: Docker & Docker Compose (Any Server / Cloud VPS)
The project includes a production-ready `Dockerfile` and `docker-compose.yml`.

```bash
# Build and run with Docker Compose
docker-compose up --build -d

# View logs
docker-compose logs -f
```
App will be live at `http://localhost:8000` (or `http://YOUR_SERVER_IP:8000`).

---

### Option 2: Render.com (1-Click Free Hosting)
1. Fork or push this repository to GitHub/GitLab.
2. Go to [Render Dashboard](https://dashboard.render.com/) ➔ **New Web Service**.
3. Select this repository.
4. Render will automatically detect `render.yaml` or you can manually configure:
   - **Environment**: `Python 3`
   - **Build Command**: `pip install -r backend/requirements.txt`
   - **Start Command**: `uvicorn backend.main:app --host 0.0.0.0 --port $PORT`
   - **Health Check Path**: `/health`
5. Click **Create Web Service**.

---

### Option 3: Railway.app (1-Click Container Deploy)
1. Push repository to GitHub.
2. Log into [Railway.app](https://railway.app/) ➔ **New Project** ➔ **Deploy from GitHub repo**.
3. Railway automatically detects `Dockerfile` and `railway.json`.
4. Deploy instantly with zero manual configuration.

---

### Option 4: Fly.io
1. Install Flyctl CLI (`brew install flyctl` or `curl -L https://fly.io/install.sh | sh`).
2. Run:
```bash
fly launch
fly deploy
```
Fly will read the included `fly.toml` and deploy the application.

---

### Option 5: AWS EC2 / DigitalOcean / Ubuntu VPS (Systemd + Nginx)

#### 1. Setup Virtual Environment
```bash
sudo apt update && sudo apt install -y python3-pip python3-venv git
git clone <your-repo-url> /opt/pro-versed
cd /opt/pro-versed
python3 -m venv venv
source venv/bin/activate
pip install -r backend/requirements.txt
```

#### 2. Create Systemd Service (`/etc/systemd/system/proversed.service`)
```ini
[Unit]
Description=Pro-Versed FastAPI Service
After=network.target

[Service]
User=ubuntu
WorkingDirectory=/opt/pro-versed
Environment="PATH=/opt/pro-versed/venv/bin"
Environment="PORT=8000"
ExecStart=/opt/pro-versed/venv/bin/uvicorn backend.main:app --host 0.0.0.0 --port 8000
Restart=always

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable proversed
sudo systemctl start proversed
```

#### 3. Nginx Reverse Proxy Config (`/etc/nginx/sites-available/proversed`)
```nginx
server {
    listen 80;
    server_name yourdomain.com;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```
```bash
sudo ln -s /etc/nginx/sites-available/proversed /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
```

---

## ⚙️ Environment Variables Reference

| Variable | Default Value | Description |
| :--- | :--- | :--- |
| `PORT` | `8000` | Port on which the web server listens. Set automatically by cloud providers. |
| `HOST` | `0.0.0.0` | Bind IP address. |
| `PROVERSED_DB_PATH` | `/tmp/proversed.db` | Path to the SQLite database file. Set to a persistent volume path if desired. |

---

## 🩺 Health Check & Monitoring

- **Endpoint**: `/health` or `/api/health`
- **Method**: `GET`
- **Response**:
```json
{
  "status": "healthy",
  "service": "pro-versed",
  "version": "1.0.0",
  "timestamp": "2026-08-18T10:25:00.000000"
}
```
