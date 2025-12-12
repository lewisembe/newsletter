# Guía para agentes

- Propósito: implementación del pipeline de clustering.
- Módulos: `embedder.py` genera embeddings; `cluster_manager.py` aplica clustering; `persistent_clusterer.py` guarda/carga estados; `hashtag_generator.py` crea etiquetas; `db_loader.py` extrae datos desde la BD.
- Uso: importados por `run_clustering.py`; mantener coherencia de firmas y formatos de estado (`state/`, `output/`).
