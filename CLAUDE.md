# Newsletter Pipeline CLI Guide

Pipeline Python que automatiza scraping, clasificación y redacción de newsletters con PostgreSQL + LLM.

## Instrucciones para Claude Code

**IMPORTANTE:**
- NO crear documentación (.md) automáticamente a menos que se solicite explícitamente
- Enfocarse en modificar código, no documentar cada cambio
- Usar comandos CLI directos para debugging/consultas
- **MANTENER este CLAUDE.md actualizado** cuando haya:
  - Cambios arquitectónicos mayores (nuevos stages, DB schema)
  - Nuevos comandos CLI esenciales
  - Cambios en configuración crítica (.env, newsletters.yml)
  - Modificaciones a workflows comunes

## Arquitectura

```
Orchestrator → Stage 01 → Stage 02 → Stage 03 → Stage 04 → Stage 05
             (scraping)   (filter)    (ranking)  (content)  (newsletter)
                         PostgreSQL: newsletter_db (Docker)
```

## Comandos CLI Esenciales

```bash
# Pipeline completo
venv/bin/python stages/orchestrator.py --config config/newsletters.yml

# Stages individuales (usar fecha actual con $(date +%Y-%m-%d))
venv/bin/python stages/01_extract_urls.py --date $(date +%Y-%m-%d)
venv/bin/python stages/02_filter_for_newsletters.py --date $(date +%Y-%m-%d)
venv/bin/python stages/03_ranker.py --newsletter-name daily --date $(date +%Y-%m-%d) --categories economia,politica
venv/bin/python stages/04_extract_content.py --date $(date +%Y-%m-%d)
venv/bin/python stages/05_generate_newsletters.py --config config/newsletters.yml

# Debugging común
psql $DATABASE_URL -c "SELECT COUNT(*) FROM urls WHERE DATE(extracted_at) = '$(date +%Y-%m-%d)';"
psql $DATABASE_URL -c "SELECT relevance_level, COUNT(*) FROM urls WHERE relevance_level IS NOT NULL GROUP BY relevance_level;"
tail -30 common/token_usage.csv
tail -50 logs/$(date +%Y-%m-%d)/orchestrator.log

# Forzar re-scraping/re-scoring
venv/bin/python stages/01_extract_urls.py --date $(date +%Y-%m-%d) --force
venv/bin/python stages/03_ranker.py --newsletter-name daily --date $(date +%Y-%m-%d) --no-cached-scores

# Regenerar reglas clasificación (solo si cambian fuentes)
UPDATE_RULES_ON_RUN=true venv/bin/python stages/01_extract_urls.py --date $(date +%Y-%m-%d)
```

## Config Key Locations

- `.env`: OPENAI_API_KEY, modelo LLM, TTL scores
- `config/newsletters.yml`: Definición newsletters (sources, categories, count)
- `config/sources.yml`: URLs scraping + XPath selectors
- `config/categories.yml`: Taxonomía temática
- `templates/prompts/*.json`: Prompts LLM (ranking, newsletter generation)

## DB Schema (PostgreSQL: newsletter_db)

- `urls`: noticias + contenido + scores (`relevance_level`, `scored_at`)
- `ranking_runs`: tracking ejecuciones stage 03
- `ranked_urls`: top URLs por newsletter
- `newsletters`: newsletters finales + metadata
- `debug_reports`: métricas/tokens

## Modificaciones Comunes

**Agregar nueva fuente de noticias:**
1. Editar `config/sources.yml` (URL + selectores)
2. Regenerar reglas: `UPDATE_RULES_ON_RUN=true venv/bin/python stages/01_extract_urls.py --date $(date +%Y-%m-%d)`

**Cambiar categorías/taxonomía:**
1. Editar `config/categories.yml`
2. Actualizar `templates/prompts/filter_urls.json` si es necesario

**Ajustar ranking/scoring:**
1. Modificar `templates/prompts/level_scoring.json`
2. Re-score: `venv/bin/python stages/03_ranker.py --no-cached-scores ...`

**Cambiar template newsletter:**
1. Editar `templates/outputs/*.md` (Jinja2)
2. Modificar `templates/prompts/newsletter_*.json` si cambias estructura

## Costos/Performance

- Stage 02: ~$0.02-0.04 (clasificación temática)
- Stage 03: ~$0.01-0.03 (scoring incremental, TTL 7 días)
- Stage 05: ~$0.003 (generación newsletter)
- Total: ~$0.04-0.08/newsletter, 4-8 min

## Webapp (FastAPI + Next.js)

### Arquitectura
- **Frontend**: Next.js 15 + React 19 + TypeScript + TailwindCSS (localhost:3000)
- **Backend**: FastAPI + postgres_db.py (localhost:8000)
- **Database**: PostgreSQL 16 (shared with pipeline)
- **Cache**: Redis 7 (shared with pipeline)

### Comandos Docker

**Iniciar webapp completa** (backend + frontend):
```bash
docker-compose up -d backend frontend
```

**Iniciar solo backend**:
```bash
docker-compose up -d backend
```

**Ver logs**:
```bash
docker-compose logs -f backend
docker-compose logs -f frontend
```

**Parar servicios**:
```bash
docker-compose down
```

**Rebuild después de cambios**:
```bash
docker-compose up -d --build backend frontend
```

**Iniciar webapp completa (acceso público vía Nginx del sistema)**:
```bash
docker-compose up -d backend frontend
```

### Acceso

**Local:**
- **Frontend (Landing Page)**: http://localhost:3000
- **Backend API**: http://localhost:8000
- **API Docs (Swagger)**: http://localhost:8000/docs
- **API Redoc**: http://localhost:8000/redoc
- **PostgreSQL**: localhost:5432 (via Cloudbeaver: http://localhost:8978)
- **Redis**: localhost:6379

**Public (via System Nginx):**
- **Frontend**: https://lewisembe.duckdns.org
- **Backend API**: https://lewisembe.duckdns.org/api/v1/
- **API Docs**: https://lewisembe.duckdns.org/docs
- **Health Check**: https://lewisembe.duckdns.org/health

### Estructura

```
webapp/
├── backend/          # FastAPI
│   ├── app/
│   │   ├── main.py        # Entry point, CORS config
│   │   ├── config.py      # Settings desde .env
│   │   └── api/v1/        # Endpoints (usa common/postgres_db.py)
│   ├── Dockerfile
│   └── requirements.txt
│
├── frontend/         # Next.js App Router
│   ├── app/
│   │   ├── page.tsx       # Landing page
│   │   └── layout.tsx     # Root layout
│   ├── components/
│   │   └── landing/       # Hero, Features, CTA, Footer
│   ├── lib/
│   │   └── api-client.ts  # Axios client para FastAPI
│   ├── Dockerfile
│   └── package.json
│
└── README.md
```

### Desarrollo Local (sin Docker)

**Backend**:
```bash
cd webapp/backend
../venv/bin/uvicorn app.main:app --reload --port 8000
```

**Frontend**:
```bash
cd webapp/frontend
npm install
npm run dev  # Runs on port 3000
```

### Añadir Features

**Nueva API endpoint**:
1. Crear `webapp/backend/app/api/v1/[nombre].py`
2. Definir Pydantic schema en `webapp/backend/app/schemas/`
3. Usar métodos de `common/postgres_db.py` (NO duplicar modelos)
4. Registrar router en `webapp/backend/app/api/v1/router.py`
5. **IMPORTANTE**: Definir endpoints **sin trailing slash** (usar `""` no `"/"`)

**Nueva página frontend**:
1. Crear `webapp/frontend/app/[ruta]/page.tsx`
2. Componentes en `webapp/frontend/components/`
3. Actualizar API client en `webapp/frontend/lib/api-client.ts`

**Añadir gestión en panel de admin**:
1. Crear componente en `webapp/frontend/components/admin/[Nombre]Management.tsx`
2. Añadir pestaña en `webapp/frontend/app/(dashboard)/admin/page.tsx`
3. Panel de admin centralizado: todas las gestiones en `/admin` con pestañas

### Puntos Clave

- Backend **reutiliza** `common/postgres_db.py` (no hay duplicación de modelos)
- Frontend usa Server Components por defecto (mejor performance + SEO)
- PostgreSQL compartido entre pipeline y webapp (single source of truth)
- Docker monta volúmenes para hot reload en desarrollo
- **Nginx reverse proxy** expone la app en `lewisembe.duckdns.org` (HTTP en puerto 80)

### Seguridad: JWT Secret Rotation

El sistema soporta **rotación de JWT secrets sin invalidar sesiones activas**. Ver `JWT_ROTATION.md` para detalles.

**TL;DR:**
```bash
# Generar nuevo secret
python scripts/generate_jwt_secret.py

# .env - Para rotar JWT secret sin cerrar sesiones:
JWT_SECRET_KEY=nuevo_secret_aqui
JWT_SECRET_KEY_OLD=secret_anterior  # ← Mantiene sesiones antiguas válidas

# Restart backend
docker-compose restart backend

# Monitorear progreso
docker-compose logs backend | grep "old secret key"

# Test rotación
venv/bin/python scripts/test_jwt_rotation.py
```

- Nuevos logins usan `JWT_SECRET_KEY`
- Sesiones antiguas validan con `JWT_SECRET_KEY_OLD`
- Después de 30+ días, remover `JWT_SECRET_KEY_OLD`

### Autenticación: "Remember Me"

El sistema soporta **sesiones extendidas** mediante la opción "Recordarme". Ver `REMEMBER_ME.md` para detalles.

**TL;DR:**
```bash
# API Login con Remember Me
POST /api/v1/auth/login
{
  "email": "user@example.com",
  "password": "password123",
  "remember_me": true  # ← Extiende sesión a 30 días
}

# .env - Configurar duraciones
ACCESS_TOKEN_EXPIRE_MINUTES=30  # Login normal: 30 minutos
REMEMBER_ME_EXPIRE_DAYS=30      # Remember Me: 30 días

# Test
venv/bin/python scripts/test_remember_me.py
```

- `remember_me: false`: Sesión 30 minutos (default)
- `remember_me: true`: Sesión 30 días (persiste tras cerrar navegador)
- Cookie HTTP-only con `max_age` dinámico

### Configuración DuckDNS (Nginx del Sistema)

**Configuración actual:**
- Nginx del sistema (no Docker) actúa como reverse proxy
- SSL/HTTPS ya configurado con Let's Encrypt
- Frontend: `https://lewisembe.duckdns.org/` → `localhost:3000` (Docker)
- Backend API: `https://lewisembe.duckdns.org/api/` → `localhost:8000` (Docker)
- API Docs: `https://lewisembe.duckdns.org/docs` → `localhost:8000/docs`

**Iniciar la aplicación:**
```bash
# Iniciar backend + frontend (exponen puertos 8000 y 3000 a localhost)
docker-compose up -d backend frontend

# Verificar que estén corriendo
docker-compose ps
curl http://localhost:8000/health
curl http://localhost:3000
```

**Recargar configuración Nginx después de cambios:**
```bash
sudo nginx -t  # Verificar sintaxis
sudo systemctl reload nginx
```

**Archivos de configuración:**
- `/etc/nginx/sites-available/lewisembe.conf`: Configuración Nginx del sistema
- `docker-compose.yml`: Backend (8000) y Frontend (3000) expuestos a localhost
- `.env`: Variables `CORS_ORIGINS` y `NEXT_PUBLIC_API_URL` configuradas para HTTPS

### Testing con Playwright

**Guía completa**: Ver `webapp/frontend/TESTING.md`

**Setup esencial** (ARM64):
```bash
# CRÍTICO: Añadir a /etc/hosts para testear desde red local
sudo nano /etc/hosts
# Añadir: 127.0.0.1 lewisembe.duckdns.org

# Instalar Playwright (compatible ARM)
cd webapp/frontend
npx playwright install chromium
```

**Comandos principales**:
```bash
cd webapp/frontend

# Ejecutar todos los tests
npx playwright test

# Test específico
npx playwright test tests/login-debug.spec.ts
npx playwright test tests/api-keys.spec.ts

# Modo debug (con UI inspector)
npx playwright test --debug

# Ver reporte HTML
npx playwright show-report
```

**Tests implementados**:
- `login-debug.spec.ts`: Validación de flujo de autenticación
- `api-keys.spec.ts`: CRUD completo de gestión de API Keys (admin panel)

**Troubleshooting**:
- Error "ERR_NAME_NOT_RESOLVED": Verificar `/etc/hosts`
- Error "401 Unauthorized": Limpiar cookies o verificar credenciales
- Error "timeout": Ejecutar `npx playwright test --debug` para ver UI real

## Ejecución Secuencial de Tareas Programadas

**IMPORTANTE**: Las ejecuciones del Stage 1 (scraping) se ejecutan **siempre de forma secuencial**, nunca en paralelo.

### Configuración
- **Celery Worker**: `--concurrency=1` (solo 1 tarea a la vez)
- **Lock Global**: `has_running_execution()` verifica ejecuciones activas antes de lanzar nuevas
- **Orden Aleatorio**: Si múltiples schedules están programados para la misma hora, se procesan en orden aleatorio (`random.shuffle`)

### Reiniciar Workers
```bash
# Aplicar cambios en configuración
docker-compose restart celery_worker celery_beat

# Rebuild si hay cambios en código
docker-compose up -d --build celery_worker celery_beat
```

### Ejemplo de Comportamiento
```
10:00 AM - 3 schedules programados (A, B, C)
         → random.shuffle → Orden: [B, C, A]
         → Ejecuta B (lock global activo)
         → SKIP C (B corriendo)
         → SKIP A (B corriendo)
10:15 AM - B completa
11:00 AM - Siguiente ronda → random.shuffle → Ejecuta siguiente pendiente
```
