# Guía para agentes

- Propósito: implementación de clasificadores de categorías.
- Módulos: `category_classifier.py` orquesta pipelines; `faiss_classifier.py` maneja índices FAISS; `supervised_classifier.py` y `comparison_analyzer.py` comparan modelos; `db_loader.py` carga datos desde la BD.
- Uso: importados por los scripts de `run_classification.py` y `train_classifier.py`; mantener APIs estables (clases y métodos públicos).
- Dependencias: requiere `sentence-transformers` y FAISS; asegúrate de que los paths a modelos coincidan con `config*.yml`.
