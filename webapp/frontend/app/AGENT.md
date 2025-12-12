# Guía para agentes

- Propósito: rutas y layouts de la app Next.js.
- Estructura: `page.tsx` y `layout.tsx` definen la landing; subcarpetas `(auth)/` y `(dashboard)/` agrupan rutas protegidas y vistas administrativas. `globals.css` contiene estilos globales.
- Uso: al añadir páginas, sigue la convención de segmentos de Next 13/14 y reutiliza providers definidos en `contexts/`.
- Estilo: la app usa Tailwind; respeta clases y temas establecidos.
