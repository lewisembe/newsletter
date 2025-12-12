# Guía de Renovación de Cookies

## 🎯 Resumen Ejecutivo

Este POC incluye **auto-renovación automática de cookies**, lo que significa que **no necesitas preocuparte por renovar cookies manualmente** si usas el sistema diariamente.

## 🔄 Cómo Funciona la Auto-Renovación

### Flujo Automático

```
1. Ejecutas: python authenticated_scraper.py
2. Script verifica: ¿Alguna cookie expira en <7 días?
3. SI expiran pronto:
   ├─ Carga cookies actuales en navegador
   ├─ Navega a ft.com con sesión activa
   ├─ Obtiene cookies frescas del navegador
   ├─ Hace backup (cookies.json.backup)
   └─ Guarda cookies renovadas
4. Continúa con scraping normalmente
```

### Ventajas

✅ **Totalmente automático** - No requiere intervención manual
✅ **Backup automático** - Siempre guarda las cookies antiguas
✅ **Uso diario infinito** - Mientras tengas sesión activa, se auto-renueva
✅ **Sin interrupciones** - El scraping continúa después de renovar

## 📅 Estrategias de Uso

### Opción 1: Auto-renovación (Recomendado para uso diario)

```bash
# En .env
AUTO_RENEW_COOKIES=true  # ← Por defecto

# Ejecutar diariamente
python authenticated_scraper.py

# El script renovará automáticamente cuando sea necesario
```

**Resultado:**
- Las cookies se renuevan cada ~7 días automáticamente
- Solo necesitas exportar cookies manualmente 1 vez al inicio
- Funciona indefinidamente

### Opción 2: Renovación manual programada

```bash
# En .env
AUTO_RENEW_COOKIES=false

# Configurar cron job para renovar cada semana
0 2 * * 0 cd /ruta/content_POC && venv/bin/python cookie_auto_renewer.py
```

**Resultado:**
- Control total sobre cuándo se renuevan
- Útil si quieres revisar logs de renovación

### Opción 3: Híbrido (verificar + auto-renovar)

```bash
# Verificar estado antes de ejecutar
python check_cookies_expiry.py

# Si todo OK, ejecutar con auto-renovación
python authenticated_scraper.py
```

## 🕐 Frecuencia de Renovación

### Con Auto-Renovación Habilitada

| Situación | Acción Automática | Frecuencia |
|-----------|-------------------|------------|
| Cookies válidas por >7 días | No hace nada | N/A |
| Cookies válidas por <7 días | Renueva automáticamente | Cada ejecución |
| Session cookies presentes | Renueva automáticamente | Cada ejecución |

### Sin Auto-Renovación

| Cookie Type | Duración Típica | Renovar Cada |
|-------------|-----------------|--------------|
| Session cookies | Cierre de navegador | Cada sesión |
| `_sxh`, `_sanba` | 30 días | 3-4 semanas |
| `FTSession_s` | 180 días | 5-6 meses |
| `FTClientSessionId` | 400 días | 1 año |

**Recomendación:** Renovar cada **7-10 días** si no usas auto-renovación.

## 📊 Monitoreo de Cookies

### Verificar estado actual

```bash
python check_cookies_expiry.py
```

**Salida:**
```
🔍 Cookie Expiry Analysis
📊 Summary:
   Total cookies: 19
   Session cookies: 2
   Cookies with expiration: 17

⏰ First to expire: _sxh in 30.0 days

💡 Recommendation:
   ✅ Cookies are valid for ~30 days

📆 For daily usage:
   🔄 Renew cookies: Every month
```

### Verificar durante ejecución

El scraper muestra información de renovación:

```bash
python authenticated_scraper.py
```

**Output con renovación:**
```
🚀 Authenticated Scraper POC
   Auto-renew cookies: True

🔄 Session cookie detected: ft-access-decision-policy - renewal recommended

🔄 Auto-renewing cookies...
📥 Loaded 19 existing cookies
💾 Backed up old cookies to cookies.json.backup
✅ Successfully renewed 31 cookies!

✅ Loaded 31 cookies for ft.com
📄 Fetching: https://www.ft.com/content/...
```

## 🔧 Scripts Disponibles

### 1. `authenticated_scraper.py` (Principal)

Scraper con auto-renovación integrada.

```bash
python authenticated_scraper.py
```

**Cuándo usar:** Para scraping diario normal.

### 2. `cookie_auto_renewer.py` (Renovación manual)

Fuerza renovación inmediata sin scraping.

```bash
python cookie_auto_renewer.py
```

**Cuándo usar:**
- Cuando quieres renovar sin hacer scraping
- Para probar que la renovación funciona
- En cron jobs programados

### 3. `check_cookies_expiry.py` (Monitor)

Verifica estado sin modificar nada.

```bash
python check_cookies_expiry.py
```

**Cuándo usar:**
- Para ver cuándo expiran las cookies
- Debugging
- Planificación de renovaciones manuales

## ⚠️ Limitaciones y Consideraciones

### Cuándo la Auto-Renovación Falla

La renovación automática **fallará** si:

1. **Cerraste sesión en el navegador** desde donde exportaste cookies
2. **Financial Times invalidó tu sesión** por seguridad
3. **Cambiaste tu contraseña** en FT
4. **Cookies expiradas completamente** (>180 días sin renovar)

**Solución:** Re-exportar cookies manualmente del navegador.

### Señales de que necesitas re-exportar cookies

- ❌ Script devuelve página de "Subscribe to read"
- ❌ Auto-renovación reporta 0 cookies cargadas
- ❌ Error: "Failed to add cookie"

**Acción:**
```bash
1. Abre navegador y verifica que estás logueado en ft.com
2. Exporta cookies con Cookie Editor
3. Reemplaza cookies.json
4. Ejecuta de nuevo
```

## 🎓 Best Practices

### Para Uso Diario Automatizado

```bash
# 1. Configurar auto-renovación
AUTO_RENEW_COOKIES=true

# 2. Ejecutar en cron diario
0 9 * * * cd /ruta/content_POC && venv/bin/python authenticated_scraper.py

# 3. Monitoreo semanal opcional
0 10 * * 1 cd /ruta/content_POC && venv/bin/python check_cookies_expiry.py >> logs/cookie_status.log
```

### Para Múltiples Sitios

Si scrapeás varios sitios con paywall:

```bash
# Estructura recomendada
content_POC/
├── cookies_ft.json      # Financial Times
├── cookies_nyt.json     # NY Times
├── cookies_wsj.json     # Wall Street Journal
└── ...

# Configurar por sitio en .env
COOKIES_FILE=cookies_ft.json  # Cambiar según sitio
```

### Seguridad

```bash
# SIEMPRE en .gitignore
cookies*.json
!cookies.json.example
cookies*.backup
.env
```

## 📈 Ejemplo de Uso a Largo Plazo

```bash
# Día 1: Setup inicial
1. Exportar cookies de FT
2. Guardar como cookies.json
3. Configurar AUTO_RENEW_COOKIES=true

# Día 2-365: Uso diario
- Ejecutar: python authenticated_scraper.py
- Script auto-renueva cookies cada ~7 días
- No requiere intervención manual

# Solo si falla la autenticación (raro):
- Re-exportar cookies del navegador
- Reemplazar cookies.json
```

## 🚀 Siguiente Nivel: Integración con Pipeline

Si quieres integrar esto con el pipeline principal de newsletters:

```python
# En stages/04_extract_content.py
from content_POC.authenticated_scraper import AuthenticatedScraper

# Usar para sitios con paywall
scraper = AuthenticatedScraper(
    cookies_file='content_POC/cookies_ft.json',
    headless=True
)
content = scraper.extract_content(url)
```

---

**Resumen:** Con `AUTO_RENEW_COOKIES=true`, solo necesitas exportar cookies 1 vez al inicio. El sistema se auto-mantiene indefinidamente mientras tengas sesión activa en el navegador.
