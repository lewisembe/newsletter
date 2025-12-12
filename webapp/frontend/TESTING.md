# Testing Guide - Briefy Newsletter Webapp

Guía completa para ejecutar tests de Playwright contra la aplicación en producción (lewisembe.duckdns.org).

## Requisitos Previos

### 1. Configuración de `/etc/hosts`

**CRÍTICO**: Para testear contra `lewisembe.duckdns.org` desde la red local, debes añadir esta entrada a `/etc/hosts`:

```bash
sudo nano /etc/hosts
```

Añade la línea:
```
127.0.0.1 lewisembe.duckdns.org
```

**¿Por qué?** DuckDNS apunta a tu IP pública. Desde dentro de la red local, necesitas resolver el dominio a localhost para acceder al servidor Nginx local.

Verifica la configuración:
```bash
curl -sk https://lewisembe.duckdns.org/health
```

Deberías ver: `{"status":"healthy"}`

### 2. Servicios Docker Activos

Asegúrate de que los servicios están corriendo:

```bash
cd /home/luis.martinezb/Documents/newsletter_utils
docker-compose ps
```

Deberías ver `backend` y `frontend` con estado `Up`. Si no:

```bash
docker-compose up -d backend frontend
```

### 3. Credenciales de Prueba

Los tests usan estas credenciales:
- **Admin**: `admin@example.com` / `admin123`
- **Usuario regular**: Crear con `/register` o usar existente

## Estructura de Tests

```
webapp/frontend/tests/
├── login-debug.spec.ts      # Debug de flujo de login
├── api-keys.spec.ts         # Tests completos de gestión de API Keys
└── TESTING.md               # Esta guía
```

## Ejecutar Tests

### Desde el directorio frontend:

```bash
cd /home/luis.martinezb/Documents/newsletter_utils/webapp/frontend
```

### Ejecutar todos los tests:

```bash
npx playwright test
```

### Ejecutar un test específico:

```bash
npx playwright test tests/login-debug.spec.ts
npx playwright test tests/api-keys.spec.ts
```

### Modo debug (con inspector UI):

```bash
npx playwright test --debug
```

### Ver reporte HTML:

```bash
npx playwright show-report
```

### Ejecutar con UI (headed mode):

```bash
npx playwright test --headed
```

## Tests Implementados

### 1. `login-debug.spec.ts` - Test de Login

**Propósito**: Verificar flujo completo de autenticación

**Qué valida**:
- Navegación a `/login`
- Formulario visible
- Login con credenciales admin
- Redirección a `/dashboard`
- Token JWT almacenado correctamente

**Comando**:
```bash
npx playwright test tests/login-debug.spec.ts
```

**Salida esperada**:
```
✓ Navigated to login page
✓ Login form is visible
✓ Form filled with credentials
✓ Submit button clicked
LOGIN RESPONSE: 200
✓ Successfully redirected to dashboard
  ✓  1 [chromium] › tests/login-debug.spec.ts:7:5 › debug login flow
```

### 2. `api-keys.spec.ts` - Gestión de API Keys

**Propósito**: Verificar CRUD completo de API Keys

**Tests incluidos**:
1. **Display page**: Pestaña de API Keys visible
2. **Create key**: Crear nueva API key con alias
3. **Display in table**: Key aparece en tabla
4. **View details**: Modal de detalles muestra info correcta
5. **Edit key**: Modificar alias y notas
6. **Test key**: Validar key contra OpenAI API
7. **Deactivate key**: Desactivar key (soft delete)
8. **Delete key**: Eliminar key permanentemente

**Comando**:
```bash
npx playwright test tests/api-keys.spec.ts
```

**Notas importantes**:
- Usa API key real de OpenAI para test de validación (reemplazar en el código)
- Tests limpian datos creados al finalizar
- Requiere login como admin

## Configuración de Playwright

### `playwright.config.ts`

```typescript
export default defineConfig({
  testDir: './tests',
  fullyParallel: true,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : undefined,

  use: {
    baseURL: 'https://lewisembe.duckdns.org',
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
    ignoreHTTPSErrors: true,  // IMPORTANTE: Certificado autofirmado
  },

  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],
});
```

**Puntos clave**:
- `baseURL`: Apunta a producción (lewisembe.duckdns.org)
- `ignoreHTTPSErrors`: true porque usamos certificado Let's Encrypt
- No necesita `webServer` (usamos Nginx del sistema)

### Variables de Entorno

No es necesario configurar `NEXT_PUBLIC_API_URL` para tests. Playwright usa el Nginx proxy automáticamente:

- Frontend: `https://lewisembe.duckdns.org/` → `localhost:3000`
- Backend API: `https://lewisembe.duckdns.org/api/v1/` → `localhost:8000/api/v1/`

## Troubleshooting

### Error: "No hay conexión a internet" o "ERR_NAME_NOT_RESOLVED"

**Problema**: Playwright no puede resolver lewisembe.duckdns.org

**Solución**: Verifica `/etc/hosts`:
```bash
grep lewisembe /etc/hosts
```

Debe mostrar:
```
127.0.0.1 lewisembe.duckdns.org
```

### Error: "net::ERR_CONNECTION_REFUSED"

**Problema**: Servicios Docker no están corriendo

**Solución**:
```bash
docker-compose up -d backend frontend
docker-compose ps  # Verificar estado
```

### Error: "401 Unauthorized" en tests

**Problema**: Token JWT expirado o credenciales incorrectas

**Solución**:
1. Verifica credenciales en el test (admin@example.com / admin123)
2. Limpia cookies del navegador si usaste modo `--headed`:
   ```bash
   rm -rf playwright/.auth
   ```
3. Verifica que el usuario existe en la DB:
   ```bash
   psql $DATABASE_URL -c "SELECT * FROM users WHERE email='admin@example.com';"
   ```

### Error: "timeout" en waitForSelector

**Problema**: Elemento no aparece en la página

**Solución**:
1. Ejecuta en modo debug para ver la UI real:
   ```bash
   npx playwright test --debug tests/api-keys.spec.ts
   ```
2. Toma screenshot para debugging:
   ```bash
   npx playwright test --screenshot=on
   ```
3. Revisa logs del backend:
   ```bash
   docker-compose logs backend | tail -50
   ```

### Tests pasan localmente pero fallan en CI

**Problema**: Configuración de red diferente

**Solución**:
- En CI, usa `localhost:3000` en lugar de lewisembe.duckdns.org
- Configura variable de entorno `CI=true` para ajustar retries
- Asegúrate de que docker-compose está corriendo en CI

## Mejores Prácticas

### 1. Limpieza de Datos de Test

Siempre limpia los datos creados durante tests:

```typescript
test.afterEach(async ({ page }) => {
  // Eliminar API keys de test
  await page.goto('/admin?tab=api-keys');
  const testKey = page.locator('text=test-playwright-key');
  if (await testKey.count() > 0) {
    await testKey.locator('..').locator('button:has-text("Eliminar")').click();
  }
});
```

### 2. Use Selectores Estables

Preferir selectores semánticos:
- ✅ `button[type="submit"]`
- ✅ `input[type="email"]`
- ✅ `h2:has-text("Claves API")`
- ❌ `.css-class-xyz123`
- ❌ `div > div > button:nth-child(3)`

### 3. Espera Inteligente

Usa `waitForLoadState` en lugar de `waitForTimeout`:

```typescript
// ❌ MAL
await page.waitForTimeout(3000);

// ✅ BIEN
await page.waitForLoadState('networkidle');
await page.waitForSelector('text=Success', { state: 'visible' });
```

### 4. Manejo de Errores Asíncronos

Captura errores de red:

```typescript
page.on('pageerror', err => console.log('PAGE ERROR:', err));
page.on('response', response => {
  if (response.status() >= 400) {
    console.log(`ERROR: ${response.status()} ${response.url()}`);
  }
});
```

## Workflow Completo de Testing

### 1. Antes de Desarrollar Nueva Feature

```bash
# Ejecutar tests existentes para baseline
npx playwright test
```

### 2. Durante Desarrollo

```bash
# Test específico en modo watch
npx playwright test tests/mi-feature.spec.ts --headed
```

### 3. Antes de Commit

```bash
# Ejecutar suite completa
npx playwright test

# Ver reporte
npx playwright show-report
```

### 4. Antes de PR/Deploy

```bash
# Tests en modo CI (con retries)
CI=true npx playwright test

# Verificar screenshots de fallos
ls test-results/
```

## Debugging Avanzado

### Usar el Inspector de Playwright

```bash
npx playwright test --debug tests/login-debug.spec.ts
```

**Controles**:
- **Step Over** (F10): Ejecutar siguiente línea
- **Step Into** (F11): Entrar en función
- **Resume** (F8): Continuar hasta siguiente breakpoint
- **Console**: Ejecutar comandos de Playwright en vivo

### Ver Network Traffic

```typescript
page.on('request', request => {
  console.log('>>', request.method(), request.url());
});

page.on('response', response => {
  console.log('<<', response.status(), response.url());
});
```

### Capturar Screenshots Manuales

```typescript
await page.screenshot({ path: 'debug-screenshot.png', fullPage: true });
```

### Logs del Browser

```typescript
page.on('console', msg => {
  console.log('BROWSER:', msg.type(), msg.text());
});
```

## Integración con CI/CD

### GitHub Actions (ejemplo)

```yaml
name: Playwright Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-node@v3
        with:
          node-version: 18

      - name: Install dependencies
        run: |
          cd webapp/frontend
          npm ci

      - name: Install Playwright
        run: npx playwright install --with-deps chromium

      - name: Start services
        run: docker-compose up -d backend frontend

      - name: Wait for services
        run: |
          sleep 10
          curl http://localhost:8000/health

      - name: Run tests
        run: |
          cd webapp/frontend
          npx playwright test
        env:
          CI: true

      - name: Upload test results
        if: always()
        uses: actions/upload-artifact@v3
        with:
          name: playwright-report
          path: webapp/frontend/playwright-report/
```

## Recursos Adicionales

- **Playwright Docs**: https://playwright.dev/
- **Selector Cheatsheet**: https://playwright.dev/docs/selectors
- **Best Practices**: https://playwright.dev/docs/best-practices
- **Debugging Guide**: https://playwright.dev/docs/debug

## Comandos de Referencia Rápida

```bash
# Ejecutar todos los tests
npx playwright test

# Ejecutar con UI
npx playwright test --ui

# Ejecutar en modo debug
npx playwright test --debug

# Ejecutar test específico
npx playwright test tests/login-debug.spec.ts

# Ver reporte
npx playwright show-report

# Actualizar snapshots
npx playwright test --update-snapshots

# Generar código de test (grabador)
npx playwright codegen https://lewisembe.duckdns.org
```

## Notas de Arquitectura ARM

Este proyecto corre en Raspberry Pi (ARM64). Playwright usa Chromium compilado para ARM:

```bash
# Verificar arquitectura
uname -m  # debería mostrar: aarch64

# Verificar Chromium instalado
npx playwright install chromium
```

**Limitaciones conocidas**:
- Firefox y WebKit pueden no estar disponibles para ARM
- Usa solo `chromium` en la configuración de proyectos
- Algunos binarios requieren emulación (más lento)

---

**Última actualización**: 2025-12-04
**Versión**: 1.0.0
**Compatible con**: Playwright 1.40+, Node.js 18+, ARM64
