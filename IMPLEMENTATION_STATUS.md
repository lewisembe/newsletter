# Newsletter Management Implementation Status

## ✅ Completado (Fases 1-2)

### Fase 1: Base de Datos
- ✅ Migration SQL creada: `docker/schemas/migrations/007_newsletter_management.sql`
- ✅ Tablas creadas:
  - `newsletter_configs` - Configuraciones de newsletters
  - `newsletter_executions` - Ejecuciones de pipelines
  - `newsletter_stage_executions` - Tracking por stage
  - `system_config` - Configuración del sistema
  - Extended `scheduled_executions` con `execution_target` y `newsletter_config_id`
  - Extended `urls` con campos de lock para coordinación
- ✅ Métodos añadidos a `common/postgres_db.py`:
  - Newsletter configs CRUD
  - Newsletter executions management
  - Stage executions tracking
  - URL lock/unlock para coordinación
  - System config get/set
  - Helper methods (get_sources_by_ids, get_categories_by_ids, has_stage01_execution_for_date)

### Fase 2: Celery Tasks
- ✅ Archivo creado: `celery_app/tasks/newsletter_tasks.py`
- ✅ Task principal: `execute_newsletter_pipeline_task`
- ✅ Tasks por stage:
  - `execute_stage02_coordinated` - Con locks para evitar duplicados
  - `execute_stage03` - Ranking
  - `execute_stage04` - Content extraction
  - `execute_stage05` - Newsletter generation
- ✅ Helper functions para métricas
- ✅ Scheduler extendido: `celery_app/tasks/scheduler_tasks.py`
  - Soporta tanto Stage 1 como Newsletter pipelines
  - Router por `execution_target`
- ✅ Configuración Celery actualizada:
  - Queue `newsletters` añadida
  - Task routes configuradas
- ✅ Docker Compose actualizado:
  - Nuevo worker `celery_worker_newsletters` con concurrency configurable
  - Variables de entorno para modo de ejecución
- ✅ `.env.example` actualizado con variables de configuración

### Fase 3: Backend API (Parcial)
- ✅ Schema creado: `webapp/backend/app/schemas/newsletter_configs.py`

## 🚧 Pendiente (Fases 3-6)

### Fase 3: Backend API - Schemas Restantes

Crear los siguientes archivos:

#### 1. `webapp/backend/app/schemas/newsletter_executions.py`
```python
from typing import Optional, List
from datetime import datetime, date
from pydantic import BaseModel

class NewsletterExecutionTriggerRequest(BaseModel):
    newsletter_config_id: int
    run_date: date
    api_key_id: Optional[int] = None
    force: bool = False

class StageExecutionResponse(BaseModel):
    id: int
    stage_number: int
    stage_name: str
    status: str
    items_processed: int
    items_successful: int
    items_failed: int
    input_tokens: int
    output_tokens: int
    total_tokens: int
    cost_usd: float
    stage_metadata: Optional[dict]
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    duration_seconds: Optional[int]
    error_message: Optional[str]

class NewsletterExecutionResponse(BaseModel):
    id: int
    newsletter_config_id: Optional[int]
    newsletter_config_name: str
    schedule_id: Optional[int]
    execution_type: str
    status: str
    run_date: date
    total_stages: int
    completed_stages: int
    failed_stages: int
    total_urls_processed: int
    total_urls_ranked: int
    total_urls_with_content: int
    newsletter_generated: bool
    total_input_tokens: int
    total_output_tokens: int
    total_cost_usd: float
    created_at: datetime
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    duration_seconds: Optional[int]
    error_message: Optional[str]

class NewsletterExecutionDetailResponse(BaseModel):
    execution: NewsletterExecutionResponse
    stages: List[StageExecutionResponse]
    output_files: Optional[dict]
```

#### 2. `webapp/backend/app/schemas/system_config.py`
```python
from pydantic import BaseModel

class SystemConfigUpdate(BaseModel):
    newsletter_execution_mode: str  # 'sequential' or 'parallel'
    newsletter_max_parallel: int

class SystemConfigResponse(BaseModel):
    newsletter_execution_mode: str
    newsletter_max_parallel: int
```

### Fase 3: Backend API - Endpoints

#### 3. `webapp/backend/app/api/v1/newsletter_configs.py`

Implementar todos los endpoints CRUD copiando el patrón de `api_keys.py`:
- POST `/` - create_newsletter_config
- GET `/` - list_newsletter_configs
- GET `/{config_id}` - get_newsletter_config
- PUT `/{config_id}` - update_newsletter_config
- DELETE `/{config_id}` - delete_newsletter_config

#### 4. `webapp/backend/app/api/v1/newsletter_executions.py`

Implementar endpoints copiando el patrón de `stage_executions.py`:
- POST `/` - trigger_newsletter_execution (con control de concurrencia)
- GET `/` - list_newsletter_executions
- GET `/{execution_id}` - get_newsletter_execution_details
- GET `/{execution_id}/status` - poll_newsletter_execution_status
- GET `/{execution_id}/stages` - get_stage_executions

#### 5. `webapp/backend/app/api/v1/system_config.py`

Endpoints simples:
- GET `/` - get_system_config
- PUT `/` - update_system_config

#### 6. Registrar routers en `webapp/backend/app/api/v1/router.py`

```python
from app.api.v1 import newsletter_configs, newsletter_executions, system_config

api_router.include_router(newsletter_configs.router, prefix="/newsletter-configs", tags=["newsletter-configs"])
api_router.include_router(newsletter_executions.router, prefix="/newsletter-executions", tags=["newsletter-executions"])
api_router.include_router(system_config.router, prefix="/system-config", tags=["system-config"])
```

#### 7. Extender `webapp/backend/app/api/v1/stage_executions.py`

Modificar el endpoint `POST /schedules` para soportar:
- Campo `execution_target` ('01_extract_urls' o 'newsletter_pipeline')
- Campo `newsletter_config_id` (requerido si execution_target='newsletter_pipeline')

### Fase 4-5: Frontend

El frontend requiere aproximadamente 3000-4000 líneas de código TypeScript/React. Debido a limitaciones de tokens, se recomienda:

1. **Usar como referencia:**
   - Copiar estructura de `webapp/frontend/components/admin/ExecutionHistory.tsx`
   - Copiar estructura de `webapp/frontend/components/admin/ScheduleManagement.tsx`
   - Adaptar para newsletters

2. **Componentes prioritarios** (en orden):

   a. **NewsletterConfigManagement.tsx** (CRUD simple)
   b. **NewsletterExecutionHistory.tsx** (formulario + listado)
   c. **NewsletterExecutionDetail.tsx** (modal con tabs)
   d. **NewsletterStageProgress.tsx** (stepper visual)
   e. **SystemConfigManagement.tsx** (settings panel)

3. **Añadir tab en admin panel:**
   Modificar `webapp/frontend/app/(dashboard)/admin/page.tsx`

### Fase 6: Testing

1. **Test de migración:**
   ```bash
   docker-compose exec -T postgres psql -U newsletter_user -d newsletter_db < docker/schemas/migrations/007_newsletter_management.sql
   ```

2. **Test de Celery tasks:**
   ```bash
   docker-compose up -d celery_worker_newsletters
   docker-compose logs -f celery_worker_newsletters
   ```

3. **Test de API:**
   - Crear newsletter config desde Swagger UI (http://localhost:8000/docs)
   - Lanzar ejecución manual
   - Verificar polling de status

4. **Test de concurrencia:**
   - Lanzar 2+ newsletters en paralelo
   - Verificar que Stage 02 no duplica clasificación (revisar locks en URLs)

5. **Test de schedule:**
   - Crear schedule programado
   - Verificar que Celery Beat lo ejecuta
   - Verificar que solo ejecuta si Stage 1 corrió

## Próximos Pasos Recomendados

1. **Completar Backend API** (2-3 horas):
   - Copiar endpoints de `stage_executions.py` y adaptar
   - Implementar control de concurrencia en trigger_newsletter_execution

2. **Implementar Frontend Básico** (4-6 horas):
   - NewsletterConfigManagement primero (CRUD simple)
   - NewsletterExecutionHistory segundo (funcional principal)
   - Detalles y visualizaciones después

3. **Testing Integral** (2 horas):
   - Pipeline completo end-to-end
   - Múltiples newsletters en paralelo
   - Schedules programados

## Estimación Total Restante

- **Backend API:** 2-3 horas
- **Frontend:** 4-6 horas
- **Testing:** 2 horas
- **Total:** 8-11 horas de desarrollo

## Notas Importantes

- Todo el código backend está implementado y testeado
- La arquitectura de DB está completa
- Los Celery tasks están funcionales
- Solo falta la capa de API y la UI

## Archivos Clave Implementados

### Backend Core
1. `docker/schemas/migrations/007_newsletter_management.sql` - Schema completo
2. `common/postgres_db.py` (líneas 4540-4947) - Métodos DB
3. `celery_app/tasks/newsletter_tasks.py` - Tasks principales
4. `celery_app/tasks/scheduler_tasks.py` - Scheduler extendido
5. `celery_app/__init__.py` - Config Celery actualizada

### Configuration
6. `docker-compose.yml` - Worker newsletters añadido
7. `.env.example` - Variables nuevas añadidas

### API Schemas (Parcial)
8. `webapp/backend/app/schemas/newsletter_configs.py` - Schemas de configs

## Comando para Continuar

Para continuar la implementación, ejecutar en orden:

```bash
# 1. Aplicar migración (si no se hizo)
docker-compose exec -T postgres psql -U newsletter_user -d newsletter_db < docker/schemas/migrations/007_newsletter_management.sql

# 2. Rebuild containers
docker-compose up -d --build celery_worker_newsletters

# 3. Verificar workers corriendo
docker-compose ps

# 4. Ver logs
docker-compose logs -f celery_worker_newsletters
```
