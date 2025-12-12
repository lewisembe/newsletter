# POC: Authenticated Content Extraction

## 🎯 Objetivo

Proof of concept para extracción automatizada de contenido de fuentes con paywall mediante:
- **Selenium** para interacción con el navegador
- **LLM** para identificación dinámica de selectores (email field, password field, submit button)
- **Gestión de sesión** autenticada para acceso a contenido premium

## 🏗️ Arquitectura

```
1. Login Automatizado
   ├── Navegar a página de login
   ├── LLM identifica selector de campo email → Selenium ingresa credencial
   ├── LLM identifica selector de campo password → Selenium ingresa credencial
   ├── LLM identifica botón submit → Selenium hace click
   └── Verificación de login exitoso

2. Extracción de Contenido
   ├── Navegar a artículo (con sesión autenticada)
   ├── LLM identifica selector de título
   ├── LLM identifica selector de cuerpo del artículo
   └── Extracción y validación de texto

3. Output
   └── JSON con título, contenido, word count y metadata
```

## 🚀 Uso

### Instalación de dependencias

```bash
# Ya incluidas en requirements.txt:
# - selenium
# - webdriver-manager (opcional, si usas ChromeDriverManager)
# - openai (para LLM)

pip install -r requirements.txt
```

### Ejecución

#### 🔥 Método Recomendado: Cookie Caching (Evita CAPTCHA)

**Paso 1: Primera ejecución - Login con CAPTCHA manual**

```bash
# Sin headless para ver y resolver el CAPTCHA manualmente
# El flag --save-cookies guarda la sesión autenticada
venv/bin/python scripts/poc_authenticated_extraction.py \
  --url "https://www.ft.com/content/ARTICLE_ID" \
  --save-cookies

# El script esperará 60 segundos para que resuelvas el CAPTCHA
# Después guardará las cookies en: data/cookies/ft_com_cookies.pkl
```

**Paso 2: Runs posteriores - Usa cookies (SIN CAPTCHA, SIN LOGIN)**

```bash
# Usa cookies guardadas, completamente automático
venv/bin/python scripts/poc_authenticated_extraction.py \
  --url "https://www.ft.com/content/ARTICLE_ID" \
  --use-cookies \
  --headless \
  --output data/extracted/ft_article.json

# ✅ No login
# ✅ No CAPTCHA
# ✅ Acceso directo al contenido
```

**Resultado:**
```
🔑 Attempting to use saved cookies for ft.com...
🔑 Loading cookies from: data/cookies/ft_com_cookies.pkl
   Saved at: 2025-11-13T15:30:00
   Count: 12 cookies
✅ Cookies loaded successfully
🔍 Validating cookies by accessing: https://www.ft.com/content/...
✅ Cookies appear valid - access granted
✅ Cookies are valid! Skipping login.
📰 Navigating to article: https://www.ft.com/content/...
[Extrae contenido sin problemas]
```

#### Opciones Básicas (Sin Cookies - Para Testing)

```bash
# Modo visual (abre navegador, verás el CAPTCHA)
venv/bin/python scripts/poc_authenticated_extraction.py \
  --url "https://www.ft.com/content/ARTICLE_ID"

# Modo headless (fallará en CAPTCHA)
venv/bin/python scripts/poc_authenticated_extraction.py \
  --url "https://www.ft.com/content/ARTICLE_ID" \
  --headless
```

### Ejemplo Completo: Workflow de Producción

```bash
# ===== CONFIGURACIÓN INICIAL (Una sola vez) =====
# 1. Login manual y resolver CAPTCHA
venv/bin/python scripts/poc_authenticated_extraction.py \
  --url "https://www.ft.com/content/ccc0ec9a-aba6-4380-aeaa-ffe5fe803578" \
  --save-cookies

# [Resuelves el CAPTCHA manualmente en el navegador]
# Cookies guardadas en: data/cookies/ft_com_cookies.pkl

# ===== USO DIARIO (Sin CAPTCHA ni login) =====
# 2. Extraer múltiples artículos usando cookies
for url in article1 article2 article3; do
  venv/bin/python scripts/poc_authenticated_extraction.py \
    --url "https://www.ft.com/content/$url" \
    --use-cookies \
    --headless \
    --output "data/extracted/${url}.json"
done

# ===== SI COOKIES EXPIRAN (Cada 24-48 horas) =====
# 3. Renovar cookies (fallback automático)
# Si --use-cookies falla, el script intenta login automáticamente
# Puedes volver a --save-cookies para actualizar la sesión
```

### Todas las Opciones

```
--url URL               # URL del artículo (requerido)
--headless              # Modo headless (sin ventana visible)
--output FILE           # Guardar contenido a archivo JSON
--use-cookies           # Intentar usar cookies guardadas primero
--save-cookies          # Guardar cookies después de login exitoso
--cookies-dir DIR       # Directorio para cookies (default: data/cookies)
```

## 🔧 Configuración

### Credenciales

Las credenciales están hardcodeadas en el script para el POC:

```python
CREDENTIALS = {
    "ft.com": {
        "email": "201001166@alu.upcomillas.edu",
        "password": "luisbarack",
        "login_url": "https://www.ft.com/login"
    }
}
```

**⚠️ IMPORTANTE:** En producción, mover a `.env`:

```env
# .env
FT_EMAIL=your_email@example.com
FT_PASSWORD=your_password
```

### Modelos LLM

El script usa `MODEL_XPATH_DISCOVERY` (definido en `.env`):

```env
MODEL_XPATH_DISCOVERY=gpt-4o-mini  # Modelo para identificar selectores
```

## 📊 Output

### Estructura JSON

```json
{
  "url": "https://www.ft.com/content/...",
  "title": "Article Title Here",
  "content": "Full article text content...",
  "word_count": 1234,
  "extracted_at": "2025-11-13T14:30:00",
  "method": "authenticated_selenium_llm"
}
```

### Screenshots de Debug

El script guarda screenshots automáticamente en `logs/screenshots/`:

```
logs/screenshots/
  ├── 20251113_143000_01_login_page.png
  ├── 20251113_143005_02_credentials_entered.png
  ├── 20251113_143010_03_after_submit.png
  └── 20251113_143015_04_article_page.png
```

## 🧠 Cómo Funciona el LLM

### Identificación de Selectores

El LLM recibe:
1. **HTML snippet** de la página (primeros 10,000 caracteres)
2. **Acción requerida** (ej: "find email input field in the login form")

Y retorna:

```json
{
  "selector_type": "css",
  "selector": "input[type='email']#email",
  "confidence": "high",
  "reasoning": "Found unique email input with id='email'"
}
```

### Ejemplo de Prompt

```
Analyze this HTML snippet from a login page and identify the CSS selector or XPath for:
email input field in the login form

HTML snippet (truncated):
<html>
  <form id="login-form">
    <input type="email" id="email" name="email" placeholder="Enter your email">
    <input type="password" id="password" name="password">
    <button type="submit">Sign In</button>
  </form>
</html>

Return ONLY a JSON object with this structure:
{
    "selector_type": "css" or "xpath",
    "selector": "the actual selector string",
    "confidence": "high/medium/low",
    "reasoning": "brief explanation"
}
```

### Retry Logic

- Si el selector falla, el LLM reintenta hasta **2 veces**
- Útil si la primera sugerencia no funciona o el HTML es ambiguo

## 🔒 CAPTCHA Handling

### El Problema

Financial Times (y otros sitios) muestran CAPTCHAs cuando detectan comportamiento automatizado, incluso con credenciales válidas.

**Resultado de nuestras pruebas:**
- ✅ Login flow completo funciona (email → Continue → password → Sign in)
- ✅ LLM identifica correctamente todos los selectores
- ✅ Selenium ejecuta acciones como humano (delays aleatorios, typing lento)
- ❌ FT muestra CAPTCHA slider después del submit

### Soluciones

#### Opción 1: Resolver CAPTCHA Manualmente (Desarrollo)

```bash
# Ejecutar SIN --headless para ver el navegador
venv/bin/python scripts/poc_authenticated_extraction.py \
  --url "https://www.ft.com/content/ARTICLE_ID"

# El script esperará 60 segundos para que resuelvas el CAPTCHA manualmente
```

**Limitación:** Requiere entorno con GUI (no funciona en servidores headless).

#### Opción 2: Servicios de Resolución de CAPTCHA (Producción)

Integrar servicios comerciales que resuelven CAPTCHAs automáticamente:

**2Captcha** (Recomendado)
```bash
pip install 2captcha-python
```

```python
from twocaptcha import TwoCaptcha

solver = TwoCaptcha('YOUR_API_KEY')
result = solver.slider(
    sitekey='...',
    pageurl='https://www.ft.com/login'
)
```

**Pricing:** ~$2.99 por 1000 CAPTCHAs

**Alternativas:**
- **Anti-Captcha** - https://anti-captcha.com
- **CapSolver** - https://www.capsolver.com
- **CapMonster** - https://capmonster.cloud

#### Opción 3: Cookies de Sesión Pre-autenticada

En lugar de hacer login cada vez, usar cookies de una sesión ya autenticada:

```python
# 1. Login manual UNA VEZ y guardar cookies
import pickle

# Después del login exitoso:
cookies = driver.get_cookies()
with open('ft_cookies.pkl', 'wb') as f:
    pickle.dump(cookies, f)

# 2. En runs posteriores, cargar cookies
with open('ft_cookies.pkl', 'rb') as f:
    cookies = pickle.load(f)

for cookie in cookies:
    driver.add_cookie(cookie)
```

**Ventajas:**
- No requiere login cada vez
- No aparece CAPTCHA
- Más rápido

**Desventajas:**
- Cookies expiran (típicamente 24-48 horas)
- Requiere renovación periódica

#### Opción 4: Playwright Stealth (Alternativa a Selenium)

Usar **Playwright** con modo stealth en lugar de Selenium:

```bash
pip install playwright playwright-stealth
playwright install chromium
```

```python
from playwright.sync_api import sync_playwright
from playwright_stealth import stealth_sync

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()
    stealth_sync(page)
    # Mucho más difícil de detectar
```

**Ventajas:**
- Más difícil de detectar que Selenium
- Menos CAPTCHAs
- API más moderna

**Desventajas:**
- Requiere refactor del código POC

### Recomendación para Producción

**Stack completo:**
1. **Playwright Stealth** - Para evitar detección
2. **Cookie Caching** - Reusar sesiones cuando sea posible
3. **2Captcha como fallback** - Para los casos donde aparezca CAPTCHA

**Flujo:**
```
1. Intentar con cookies guardadas → Si funciona, DONE
2. Si cookies expiradas → Login con Playwright Stealth
3. Si aparece CAPTCHA → Resolver con 2Captcha
4. Guardar nuevas cookies para próximo run
```

## 🐛 Troubleshooting

### 1. Selenium no encuentra ChromeDriver

```bash
# Instalar manualmente
sudo apt install chromium-chromedriver  # Linux
brew install chromedriver               # Mac

# O usar webdriver-manager
pip install webdriver-manager
```

Modificar script para usar:
```python
from webdriver_manager.chrome import ChromeDriverManager
self.driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
```

### 2. Login falla con "element not found"

- Revisar screenshots en `logs/screenshots/`
- Verificar que el HTML snippet incluye el formulario de login
- Aumentar timeout en `WebDriverWait` (default: 20 segundos)

```python
self.wait = WebDriverWait(self.driver, 30)  # Aumentar a 30s
```

### 3. Sitio detecta bot

Añadir más evasión de detección:

```python
# Deshabilitar webdriver flag
chrome_options.add_argument("--disable-blink-features=AutomationControlled")

# Ejecutar script para ocultar automation
self.driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
    "source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
})
```

### 4. Contenido extraído está vacío

- El LLM puede haber identificado el contenedor incorrecto
- Revisar screenshot `04_article_page.png`
- Ajustar prompt para ser más específico:

```python
content_element = self._find_element_with_llm(
    "main article body paragraph container, exclude sidebar and ads"
)
```

## 🔄 Integración con Stage 04

Para integrar con `stages/04_extract_content.py`:

1. **Crear módulo de autenticación:**

```python
# common/stage04_extraction/authenticated_extractor.py
from scripts.poc_authenticated_extraction import AuthenticatedExtractor

def extract_with_auth(url: str, credentials: Dict) -> Optional[str]:
    """Wrapper para usar en Stage 04"""
    extractor = AuthenticatedExtractor(headless=True)
    try:
        if extractor.login(url):
            content = extractor.extract_content(url)
            return content['content'] if content else None
    finally:
        extractor.close()
```

2. **Modificar Stage 04 para detectar sources con credenciales:**

```python
# En stages/04_extract_content.py
AUTHENTICATED_SOURCES = ["ft.com", "wsj.com"]

if get_domain(url) in AUTHENTICATED_SOURCES:
    content = extract_with_auth(url, credentials)
else:
    content = extract_with_xpath(url)  # Método actual
```

## 📈 Próximos Pasos

- [ ] Mover credenciales a `.env` (producción)
- [ ] Soporte multi-source (WSJ, NYT, etc.)
- [ ] Cache de sesiones (evitar re-login)
- [ ] Cookies persistentes entre ejecuciones
- [ ] Manejo de 2FA/CAPTCHA
- [ ] Integración con Stage 04
- [ ] Tests automatizados

## 🎯 Fuentes Objetivo

Prioridad para implementar autenticación:

1. **Financial Times** ✅ (POC implementado)
2. **Wall Street Journal**
3. **The Economist**
4. **Bloomberg**
5. **New York Times** (login + paywall bypass)

## 📝 Notas de Seguridad

- **NO committear credenciales** al repositorio
- Usar variables de entorno en producción
- Considerar rotación de cuentas si se usa intensivamente
- Respetar términos de servicio de cada sitio

---

**Última actualización:** 2025-11-13
