# Online deployment

The root `Dockerfile` builds a single container for cloud hosting: it compiles the React frontend and serves it from the FastAPI process, on the port given in `$PORT`. The hosting platform terminates HTTPS. The database is SQLite on a persistent disk mounted at `/data`. You can use PostgreSQL instead by setting `DATABASE_URL`. Both `postgres://` and `postgresql://` URLs are accepted.

The application must run as **one instance with one worker** (see *Runtime limits* in the README). The container always starts exactly one uvicorn worker. Do not enable autoscaling or add replicas.

## Option A: Render (recommended)

`render.yaml` defines everything: one always-on *Starter* web service in Frankfurt with a 1 GB disk. At the time of writing this costs about **$7.25/month** ($7 instance + $0.25 disk). Free Render instances cannot attach a disk, so they would lose all data on every restart.

1. Make sure `render.yaml`, `Dockerfile` and `deploy/` are on the default branch on GitHub.
2. Sign in to [Render](https://render.com) with GitHub and open
   **https://render.com/deploy?repo=https://github.com/TMBOGDAN/concurs-biblic**
   (or Dashboard → **New → Blueprint** → choose the repository).
3. Fill in the two prompted values:
   - `ADMIN_EMAIL`: the administrator's sign-in email
   - `ADMIN_PASSWORD`: at least 12 characters
   These are used only to create the first administrator. Changing them later has no effect (use `python -m app.manage` from the service Shell instead).
4. Click **Apply**. The first build takes a few minutes. When the service shows *Live*, open its URL (for example `https://concurs-biblic.onrender.com`) and sign in at `/login`.

Every push to the default branch redeploys automatically. Data on the disk persists across deploys and restarts. A deploy causes a short interruption (services with disks cannot do zero-downtime deploys), so **do not push during a live competition**.

**Custom domain.** Add the domain under *Settings → Custom Domains*, then add an environment variable `APP_ORIGINS` that lists every origin users will open, comma-separated, for example `https://concurs-biblic.onrender.com,https://concurs.example.ro`. The `onrender.com` origin is allowed automatically only while `APP_ORIGINS` is unset.

**Backup.** From the service *Shell*:

```sh
python -c "import sqlite3; s=sqlite3.connect('/data/quiz.sqlite3'); d=sqlite3.connect('/data/backup.sqlite3'); s.backup(d); d.close()"
```

Download `/data/backup.sqlite3` with `scp` (Render supports SSH on paid instances) or copy it elsewhere.

**Short free trial (no disk).** In `render.yaml`, set `plan: free`, delete the `disk:` block and `DATABASE_URL`, and add a free Render Postgres database wired in with `fromDatabase` (property `connectionString`). Free web services sleep after 15 minutes without traffic (the next visitor waits about a minute), and free Postgres databases expire after 30 days. This is fine for a test, but not for a real event.

## Option B: any Docker host (VPS)

```sh
docker build -t concurs-biblic .
docker run -d --name concurs-biblic --restart unless-stopped \
  -p 127.0.0.1:8000:8000 -v concurs-data:/data \
  -e APP_ORIGINS=https://concurs.example.ro -e COOKIE_SECURE=true \
  -e ADMIN_EMAIL=admin@example.ro -e ADMIN_PASSWORD='at-least-12-characters' \
  concurs-biblic
```

Put an HTTPS reverse proxy in front of it that forwards WebSocket upgrades. With [Caddy](https://caddyserver.com), one line in the Caddyfile is enough: `concurs.example.ro { reverse_proxy 127.0.0.1:8000 }`. The existing `docker compose` setup (PostgreSQL + Nginx) also works on a VPS behind the same kind of proxy. Set `APP_ORIGINS` and `COOKIE_SECURE=true` in `.env`.

## Option C: Railway or Fly.io

Use the same `Dockerfile` and attach a volume at `/data`. The public origin is detected automatically from `RAILWAY_PUBLIC_DOMAIN` (Railway) or `FLY_APP_NAME` (Fly.io). Set `ADMIN_EMAIL`, `ADMIN_PASSWORD` and `COOKIE_SECURE=true`, and keep the service at one replica.

## Environment variables specific to the cloud image

| Variable | Default in image | Meaning |
| --- | --- | --- |
| `PORT` | `8000` | Port to listen on (Render sets 10000 automatically). |
| `DATABASE_URL` | `sqlite:////data/quiz.sqlite3` | SQLite on the disk, or a PostgreSQL URL. |
| `DATA_DIR` | `/data` | Mounted disk. Its ownership is given to the unprivileged `quiz` user on start. |
| `STATIC_DIR` | `/app/static` | Built frontend. When set, FastAPI serves the web app and applies the same security headers as `frontend/nginx.conf`. |
| `APP_ORIGINS` | platform URL | Exact allowed browser origins. If unset on Render/Railway/Fly.io, the platform URL is used. |
