# Guía para agentes

- Propósito: POC para clasificar noticias en categorías usando embeddings y clasificadores supervisados/FAISS.
- Entrypoints: `run_classification.py`, `train_classifier.py` y `eval_faiss.py`; configs en `config.yml` y `config_e5base.yml`.
- Directorios: `src/` contiene lógica de modelos, `experiments/` define variantes YAML, `models/` almacena pickles entrenados, `output/` guarda reportes.
- Dependencias: `requirements.txt` local; usa datasets desde la BD principal o archivos preparados.
- Notas: revisar `README.md` para detalles de dataset y flujo; mantener consistencia entre configuraciones y modelos almacenados.
