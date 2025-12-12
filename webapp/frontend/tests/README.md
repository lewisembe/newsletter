# Testing con Playwright

Este proyecto usa Playwright para testing end-to-end automatizado de la aplicación web.

## Configuración

Playwright ya está instalado y configurado con:
- ✅ Chromium para ARM64 (compatible con Raspberry Pi)
- ✅ Servidor MCP configurado en Claude Code
- ✅ Tests para la funcionalidad de API Keys

## Entorno remoto y logs del navegador

- Los tests ya apuntan a producción (`baseURL` = `https://lewisembe.duckdns.org` en `playwright.config.ts`), no hay que levantar servidor local.
- Para ejecutar como un usuario real y revisar la consola del browser:
  ```bash
  cd webapp/frontend
  npm install
  npx playwright install chromium  # solo la primera vez
  npx playwright test --trace on --reporter=html
  npx playwright show-report       # abre el reporte; en cada test abre el Trace → Console
  ```
- Para ver la consola en vivo mientras corre el test usa `npm run test:headed -- --trace on`.

## Ejecutar tests

### Tests en modo headless (sin UI)
```bash
cd webapp/frontend
npm test
```

### Tests con interfaz gráfica
```bash
npm run test:ui
```

### Tests en modo debug
```bash
npm run test:debug
```

### Tests con navegador visible
```bash
npm run test:headed
```

## Tests disponibles

### `tests/api-keys.spec.ts`
Suite completa de tests para la gestión de API Keys:

1. **Visualización de la página**
   - Verifica que se muestre el título "Claves API"
   - Verifica que el botón "Añadir Clave API" esté visible

2. **Estado vacío**
   - Verifica el mensaje cuando no hay API keys configuradas

3. **Modal de creación**
   - Abre y cierra el modal correctamente
   - Valida campos requeridos
   - Crea una nueva API key

4. **Tabla de API keys**
   - Verifica que se muestren las columnas correctas
   - Muestra los datos de las API keys existentes

5. **Logout**
   - Verifica que el logout funciona correctamente
   - Redirige al login después del logout

## Uso con Claude Code (MCP)

Claude Code tiene acceso a Playwright MCP, lo que significa que puede:

- 🤖 Ejecutar tests automáticamente
- 🔍 Navegar por la aplicación
- 📸 Tomar screenshots
- 🎯 Interactuar con elementos de la UI
- ✅ Verificar que todo funciona correctamente

### Ejemplo de uso con Claude:

Simplemente pídele a Claude:

```
"Ejecuta los tests de Playwright y muéstrame los resultados"
"Navega a la página de API keys y toma un screenshot"
"Verifica que el formulario de login funciona correctamente"
```

## Estructura de tests

```typescript
test.describe('Nombre del grupo', () => {
  test.beforeEach(async ({ page }) => {
    // Setup antes de cada test (ej: login)
  });

  test('nombre del test', async ({ page }) => {
    // Acciones y verificaciones
    await page.goto('/ruta');
    await expect(page.locator('selector')).toBeVisible();
  });
});
```

## Selectores útiles

```typescript
// Por texto
page.locator('text=Texto exacto')
page.locator('button:has-text("Texto parcial")')

// Por role
page.getByRole('button', { name: 'Texto' })

// Por placeholder
page.locator('input[placeholder="texto"]')

// Por tipo de input
page.locator('input[type="email"]')

// Combinaciones
page.locator('button.btn-primary:has-text("Guardar")')
```

## Debugging

Si un test falla:

1. **Ver el reporte HTML**:
   ```bash
   npx playwright show-report
   ```

2. **Ejecutar un test específico en debug**:
   ```bash
   npx playwright test api-keys.spec.ts --debug
   ```

3. **Ver screenshots de los fallos**:
   Los screenshots se guardan automáticamente en `test-results/`

## Configuración MCP

El servidor MCP de Playwright está configurado en:
```
~/.config/Claude/claude_desktop_config.json
```

Esto permite que Claude Code pueda:
- Ejecutar tests via MCP
- Navegar por la aplicación
- Tomar screenshots
- Interactuar con elementos

## Mejores prácticas

1. **Usa selectores estables**: Prefiere `data-testid` o roles sobre clases CSS
2. **Espera a que carguen los elementos**: Usa `waitForLoadState` o `waitForSelector`
3. **Limpia después de los tests**: Elimina datos de prueba creados
4. **Tests independientes**: Cada test debe poder ejecutarse solo
5. **Nombres descriptivos**: Usa nombres claros para los tests

## Añadir nuevos tests

1. Crea un archivo `.spec.ts` en `tests/`
2. Importa `test` y `expect` de `@playwright/test`
3. Escribe tus tests siguiendo el patrón existente
4. Ejecuta con `npm test`

## Recursos

- [Documentación oficial de Playwright](https://playwright.dev)
- [Best Practices](https://playwright.dev/docs/best-practices)
- [API Reference](https://playwright.dev/docs/api/class-playwright)
