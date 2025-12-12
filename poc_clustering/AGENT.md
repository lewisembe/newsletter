# Guía para agentes

- Propósito: POC de clustering de noticias con embeddings y generación de hashtags.
- Entrypoints: `run_clustering.py` usa `config.yml` para configurar modelo y umbrales; reportes comparativos en `COMPARATIVA_THRESHOLDS.md`.
- Directorios: `src/` con lógica de clustering, `models_cache/` con cachés de modelos HF, `state/` con índices FAISS persistidos, `output/` con reportes generados.
- Dependencias: `requirements.txt` local; requiere acceso a embeddings (`intfloat/multilingual-e5-*`).
