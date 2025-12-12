# Guía para agentes

- Propósito: configuración Nginx usada como reverse proxy para la webapp/API.
- Archivos: `nginx.conf` define upstreams y headers; carpeta `ssl/` guarda certificados/keys de desarrollo (no productivos).
- Uso: editar `nginx.conf` cuando cambien hosts/puertos de backend/frontend; reiniciar el contenedor tras cambios.
- Seguridad: no comprometer claves reales; sustituir por montajes seguros en producción.
