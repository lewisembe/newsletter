# Authenticated Content Scraper POC

Proof of concept para extraer contenido de sitios de noticias usando cookies persistentes para autenticación.

## Características

- ✅ Carga cookies desde archivo JSON
- ✅ **Auto-renovación automática de cookies** 🔄
- ✅ Usa Selenium con sesión autenticada
- ✅ Extrae título y contenido completo
- ✅ Soporta múltiples URLs y dominios
- ✅ Output en JSON con resultados
- ✅ Logging detallado del proceso
- ✅ Monitor de expiración de cookies

## Requisitos

- Python 3.8+
- Chrome/Chromium instalado
- Cookies válidas exportadas del navegador

## Instalación

```bash
# Crear entorno virtual
python3 -m venv venv
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate   # Windows

# Instalar dependencias
pip install -r requirements.txt
```

## Configuración

### 1. Exportar cookies del navegador

#### Opción A: Extensión de Chrome/Firefox

Usa una extensión para exportar cookies en formato JSON:

- **Chrome:** [Cookie Editor](https://chrome.google.com/webstore/detail/cookie-editor/hlkenndednhfkekhgcdicdfddnkalmdm)
- **Firefox:** [Cookie Quick Manager](https://addons.mozilla.org/en-US/firefox/addon/cookie-quick-manager/)

**Pasos:**
1. Navega al sitio y autentica (ej: ft.com)
2. Abre la extensión
3. Exporta todas las cookies en formato JSON
4. Guarda como `cookies.json`

#### Opción B: DevTools (Manual)

1. Abre DevTools (F12)
2. Ve a Application > Cookies
3. Copia manualmente las cookies importantes (session, auth tokens)
4. Crea `cookies.json` con el formato:

```json
[
  {
    "name": "nombre_cookie",
    "value": "valor_cookie",
    "domain": ".dominio.com",
    "path": "/",
    "secure": true,
    "httpOnly": true,
    "sameSite": "Lax"
  }
]
```

**Cookies importantes a exportar:**
- Cookies de sesión (session_id, PHPSESSID, etc.)
- Tokens de autenticación (auth_token, access_token, etc.)
- Cookies de suscripción (subscriber_id, etc.)

### 2. Configurar variables de entorno

```bash
# Copiar template
cp .env.example .env

# Editar .env con tus URLs de prueba
nano .env
```

Ejemplo de `.env`:

```env
TEST_URLS=https://www.ft.com/content/abc123,https://www.ft.com/content/xyz789
COOKIES_FILE=cookies.json
HEADLESS=false
TIMEOUT=30
OUTPUT_DIR=output
```

## Uso

### Ejecución básica

```bash
# Con el entorno virtual activado
python authenticated_scraper.py
```

El script **automáticamente revisará y renovará las cookies** antes de cada ejecución si están próximas a expirar (menos de 7 días).

### Auto-renovación de cookies 🔄

**¡NUEVA FUNCIONALIDAD!** El scraper ahora renueva automáticamente las cookies:

```bash
# Auto-renovación habilitada por defecto
AUTO_RENEW_COOKIES=true  # en .env

# El script:
# 1. Verifica expiración de cookies antes de ejecutar
# 2. Si alguna expira en <7 días, las renueva automáticamente
# 3. Usa la sesión activa para obtener cookies frescas
# 4. Hace backup de cookies antiguas (cookies.json.backup)
# 5. Continúa con el scraping
```

**Ventajas:**
- ✅ No necesitas renovar cookies manualmente cada semana
- ✅ El script se auto-mantiene indefinidamente
- ✅ Backup automático antes de renovar
- ✅ Funciona mientras la sesión esté activa

**Desactivar auto-renovación:**
```bash
# En .env
AUTO_RENEW_COOKIES=false
```

### Verificar estado de cookies

```bash
# Ver cuándo expiran tus cookies
python check_cookies_expiry.py
```

Salida de ejemplo:
```
🔍 Cookie Expiry Analysis
⏰ First to expire: _sxh in 30.0 days
💡 Recommendation: Cookies are valid for ~30 days
📆 For daily usage: Renew cookies every month
```

### Renovar cookies manualmente

```bash
# Forzar renovación inmediata
python cookie_auto_renewer.py
```

### Modo headless (sin interfaz gráfica)

```bash
# Editar .env y cambiar:
HEADLESS=true

# Ejecutar
python authenticated_scraper.py
```

### Resultados

Los resultados se guardan en `output/scrape_results_YYYYMMDD_HHMMSS.json`:

```json
[
  {
    "url": "https://www.ft.com/content/abc123",
    "timestamp": "2025-11-14T10:30:00",
    "success": true,
    "title": "Article Title Here",
    "content": "Full article content...",
    "word_count": 1523,
    "error": null
  }
]
```

## Estructura del Proyecto

```
content_POC/
├── authenticated_scraper.py   # Script principal
├── cookie_auto_renewer.py     # 🔄 Auto-renovador de cookies
├── check_cookies_expiry.py    # 🔍 Verificador de expiración
├── cookies.json               # Tus cookies (no committear!)
├── cookies.json.backup        # Backup automático
├── cookies.json.example       # Template de ejemplo
├── .env                       # Tu configuración (no committear!)
├── .env.example               # Template de ejemplo
├── requirements.txt           # Dependencias Python
├── README.md                  # Este archivo
└── output/                    # Resultados JSON
    └── scrape_results_*.json
```

## Troubleshooting

### Error: "Cookie file not found"

Asegúrate de haber creado `cookies.json` con tus cookies exportadas.

### Error: "Could not extract meaningful content"

Posibles causas:
1. Las cookies expiraron o son inválidas
2. El sitio detectó automatización
3. El selector genérico no funcionó para ese sitio específico

**Solución:**
- Re-exporta cookies frescas del navegador
- Verifica que estás autenticado en el navegador antes de exportar
- Intenta con `HEADLESS=false` para ver qué está pasando

### El navegador se cierra inmediatamente

Si estás en `HEADLESS=false` y quieres que el navegador permanezca abierto para debug:

```python
# En authenticated_scraper.py, comenta la línea self.driver.quit() en el método close()
```

### Cookies no se cargan correctamente

Verifica el formato JSON:
```bash
python -m json.tool cookies.json
```

Si hay errores de sintaxis, corrígelos.

### ChromeDriver issues

El script usa `webdriver-manager` que descarga automáticamente el driver correcto. Si falla:

```bash
# Instalar Chrome manualmente o verificar versión
google-chrome --version
```

## Seguridad

⚠️ **IMPORTANTE:**

- **NO** committees `cookies.json` al repositorio (contiene credenciales)
- **NO** committees `.env` al repositorio
- Añade a `.gitignore`:

```gitignore
cookies.json
.env
output/*.json
venv/
```

## Limitaciones

- El scraper usa selectores genéricos (`<article>`, `<main>`)
- Puede requerir selectores específicos por sitio para mejor precisión
- Cookies eventualmente expiran (re-exportar periódicamente)
- Algunos sitios tienen anti-bot avanzado que puede bloquear Selenium

## Próximos pasos

Para producción, considera:
- [ ] Selectores específicos por dominio (XPath/CSS)
- [ ] Rotación de cookies/sesiones
- [ ] Manejo de CAPTCHAs
- [ ] Proxy rotation
- [ ] Rate limiting
- [ ] Retry logic con backoff exponencial

## Soporte

Para issues o mejoras, consulta la documentación principal del proyecto en `/CLAUDE.md`.
