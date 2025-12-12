# Nginx Setup for lewisembe.duckdns.org

## Overview

La aplicación está expuesta públicamente usando el Nginx del sistema (no Docker) como reverse proxy con SSL/HTTPS configurado vía Let's Encrypt.

## Architecture

```
Internet → lewisembe.duckdns.org (Port 443/HTTPS)
    ↓
System Nginx (/etc/nginx/sites-available/lewisembe.conf)
    ↓
    ├─→ / → Docker Frontend (localhost:3000)
    └─→ /api/ → Docker Backend (localhost:8000)
```

## Quick Start

### 1. Start Docker Services

```bash
cd /home/luis.martinezb/Documents/newsletter_utils
docker-compose up -d backend frontend
```

### 2. Verify Services

```bash
# Check containers are running
docker-compose ps

# Test backend locally
curl http://localhost:8000/health

# Test frontend locally
curl http://localhost:3000 | head -20
```

### 3. Access Publicly

- Frontend: https://lewisembe.duckdns.org
- API: https://lewisembe.duckdns.org/api/v1/
- API Docs: https://lewisembe.duckdns.org/docs

## Configuration Files

### System Nginx Configuration

Location: `/etc/nginx/sites-available/lewisembe.conf`

Key routes:
- `/` → Frontend Next.js app (localhost:3000)
- `/api/` → Backend FastAPI (localhost:8000)
- `/docs`, `/redoc` → API documentation
- `/health` → Health check

### Docker Compose

Location: `docker-compose.yml`

Services exposed to localhost:
- `backend`: Port 8000
- `frontend`: Port 3000

### Environment Variables

Location: `.env`

Key variables:
- `CORS_ORIGINS=https://lewisembe.duckdns.org,http://localhost:3000`
- `NEXT_PUBLIC_API_URL=https://lewisembe.duckdns.org`

## Maintenance

### Reload Nginx After Config Changes

```bash
# Test configuration syntax
sudo nginx -t

# Reload nginx
sudo systemctl reload nginx

# Check status
sudo systemctl status nginx
```

### Rebuild Docker Containers

```bash
# Rebuild and restart
docker-compose up -d --build backend frontend

# View logs
docker-compose logs -f backend
docker-compose logs -f frontend
```

### Stop Services

```bash
# Stop Docker services
docker-compose down

# Or stop specific services
docker-compose stop backend frontend
```

## SSL/HTTPS

SSL certificates are managed by Let's Encrypt:
- Certificate: `/etc/letsencrypt/live/lewisembe.duckdns.org/fullchain.pem`
- Private Key: `/etc/letsencrypt/live/lewisembe.duckdns.org/privkey.pem`

Certificates auto-renew via certbot systemd timer.

## Common Issues

### Mixed Content Errors (HTTP/HTTPS)

If you see "Mixed Content" errors in the browser console:
- The frontend is configured to use **relative URLs** (no baseURL)
- This ensures all API requests use the same protocol (HTTPS) as the page
- The `api-client.ts` has interceptors that automatically:
  - Add `/api/v1` prefix to all API calls
  - Force HTTPS for any absolute URLs when page is HTTPS

### CORS Errors

Make sure `CORS_ORIGINS` in `.env` includes your domain:
```bash
CORS_ORIGINS=https://lewisembe.duckdns.org,http://localhost:3000
```

## Troubleshooting

### Check Nginx Error Logs

```bash
sudo tail -f /var/log/nginx/lewisembe.error.log
```

### Check Docker Logs

```bash
docker-compose logs -f backend
docker-compose logs -f frontend
```

### Test Backend Connectivity

```bash
# From host
curl http://localhost:8000/health

# Through Nginx
curl https://lewisembe.duckdns.org/health
```

### Verify Ports are Open

```bash
# Check if ports are listening
sudo netstat -tlnp | grep -E ':(3000|8000|443)'

# Or with ss
sudo ss -tlnp | grep -E ':(3000|8000|443)'
```

## Other Services on Same Domain

The Nginx config coexists with other subdomain services:
- `n8n-lewisembe.duckdns.org` - n8n Automation
- `jnb-lewisembe.duckdns.org` - Jupyter Notebook
- `nextcloud-lewisembe.duckdns.org` - Nextcloud
- `portainer-lewisembe.duckdns.org` - Portainer

The main domain (`lewisembe.duckdns.org`) now serves the Newsletter Utils webapp.
