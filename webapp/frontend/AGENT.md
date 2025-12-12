# Guía para agentes

- Propósito: aplicación frontend en Next.js/TypeScript para visualizar y administrar newsletters.
- Estructura: `app/` con rutas, `components/` y `contexts/` para UI/estado, `lib/` para utilidades; incluye tests Playwright en `tests/` y reportes en `playwright-report/`.
- Entorno: usa Tailwind (`tailwind.config.ts`), configuraciones en `next.config.js`, y dependencias gestionadas con `package.json`/`package-lock.json`.
- Uso: instalar con `npm install` y correr `npm run dev`; Playwright configurado en `playwright.config.ts` (instalar browsers con `npx playwright install`).
- Nota: evita tocar `node_modules/` y artefactos de test; mantén coherencia con la API del backend.
- Tests e2e: al cambiar la webapp, ejecuta Playwright contra `https://lewisembe.duckdns.org` (`npm test` o `npx playwright test --trace on`) y revisa los logs del navegador en el reporte (`npx playwright show-report` → Trace → Console).
