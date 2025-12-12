# Newsletter Utils Webapp

Professional web application for AI-powered newsletter curation.

## Architecture

- **Frontend**: Next.js 15 + React 19 + TypeScript + TailwindCSS (port 3000)
- **Backend**: FastAPI + PostgreSQL adapter (port 8000)
- **Database**: PostgreSQL 16 (shared with pipeline)
- **Cache**: Redis 7 (shared with pipeline)

## Quick Start

```bash
# Start all services
docker-compose up -d backend frontend

# Access points
- Frontend: http://localhost:3000
- Backend API: http://localhost:8000
- API Docs: http://localhost:8000/docs
```

## Development

```bash
# Backend only
docker-compose up -d backend

# Frontend only (requires backend running)
cd frontend && npm install && npm run dev

# View logs
docker-compose logs -f backend
docker-compose logs -f frontend
```

## Project Structure

```
webapp/
├── backend/           # FastAPI
│   ├── app/
│   │   ├── main.py   # Entry point
│   │   ├── config.py # Settings
│   │   └── api/v1/   # Endpoints
│   ├── Dockerfile
│   └── requirements.txt
│
└── frontend/          # Next.js
    ├── app/          # App Router pages
    ├── components/   # React components
    ├── lib/          # API client
    ├── Dockerfile
    └── package.json
```

## Key Features

- Marketing landing page for user acquisition
- REST API for newsletter data
- Server Components for optimal performance
- Reuses existing PostgreSQL database layer
- Ready for future features (auth, dashboard, admin panel)
