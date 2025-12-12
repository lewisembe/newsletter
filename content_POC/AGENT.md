# Guía para agentes

- Propósito: pruebas de autenticación/cookies para extraer contenido protegido (p.ej., FT) antes de integrarlo al pipeline.
- Archivos clave: `authenticated_scraper.py`, `cookie_auto_renewer.py`, `check_cookies_expiry.py` y guías `COOKIE_RENEWAL_GUIDE.md`/`README.md`.
- Datos sensibles: `cookies.json` y backups contienen sesiones reales; manipúlalos con cuidado y no los compartas.
- Ejecución: usa `requirements.txt` local; scripts suelen leer cookies y escribir en `output/`.
- Nota: mantener separados de la implementación principal; cualquier mejora debería portarse luego a `common/stage04_extraction`.
