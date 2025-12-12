# Guía para agentes

- Propósito: interfaz web del sistema (frontend Next.js + backend Python) para gestionar newsletters.
- Estructura: `backend/` expone API y autenticación; `frontend/` es la app Next/Tailwind; `README.md` ofrece visión general.
- Despliegue: usar `docker-compose.yml` de la raíz o los Dockerfiles individuales; coordinar puertos con `docker/nginx`.
- Nota: evita mezclar dependencias del frontend (Node) con las del backend (Python); cada uno tiene sus propios requirements/package.
