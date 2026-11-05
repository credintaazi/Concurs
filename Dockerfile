# Single-container image for cloud hosting (Render, Railway, Fly.io, any Docker host).
# Builds the React frontend and serves it from the FastAPI process on $PORT, so no
# separate Nginx is needed. HTTPS is terminated by the hosting platform.
# Local Docker Compose is unchanged and keeps using backend/ and frontend/ Dockerfiles.

FROM node:24-alpine AS web
WORKDIR /web
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.13-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    STATIC_DIR=/app/static \
    DATA_DIR=/data \
    DATABASE_URL=sqlite:////data/quiz.sqlite3 \
    PORT=8000
WORKDIR /app
COPY backend/pyproject.toml ./
COPY backend/app ./app
RUN pip install --no-cache-dir . && useradd --create-home quiz && mkdir -p /data && chown quiz:quiz /data
COPY backend/alembic.ini ./
COPY backend/alembic ./alembic
COPY --from=web /web/dist ./static
COPY deploy/entrypoint.py ./entrypoint.py
EXPOSE 8000
# Starts as root only to take ownership of a mounted disk, then runs as `quiz`.
CMD ["python", "entrypoint.py"]
