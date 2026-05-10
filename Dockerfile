FROM node:20-alpine AS frontend-build

WORKDIR /app
COPY src/frontend/package*.json ./
RUN npm install
COPY src/frontend ./
RUN npm run build

FROM python:3.10-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    EMBEDDING_BACKEND=tfidf \
    CORS_ORIGINS=http://localhost:7860

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    nginx \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY src/backend ./src/backend
COPY --from=frontend-build /app/dist /usr/share/nginx/html

RUN mkdir -p /app/data/runtime /app/data/uploads /etc/nginx/conf.d && \
    printf '%s\n' \
    'server {' \
    '  listen 7860;' \
    '  server_name _;' \
    '  root /usr/share/nginx/html;' \
    '  index index.html;' \
    '  client_max_body_size 1024m;' \
    '  location / { try_files $uri /index.html; }' \
    '  location /api/ {' \
    '    proxy_pass http://127.0.0.1:8000/api/;' \
    '    proxy_read_timeout 600s;' \
    '    proxy_send_timeout 600s;' \
    '    proxy_set_header Host $host;' \
    '    proxy_set_header X-Real-IP $remote_addr;' \
    '  }' \
    '}' > /etc/nginx/conf.d/default.conf

EXPOSE 7860

CMD sh -c "uvicorn src.backend.app.main:app --host 0.0.0.0 --port 8000 & nginx -g 'daemon off;'"
