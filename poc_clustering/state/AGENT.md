# Guía para agentes

- Contenido: artefactos persistentes de clustering, como el índice FAISS (`faiss_index.bin`).
- Uso: cargados por `persistent_clusterer`; regenerar si cambian embeddings o parámetros de clustering.
- Precaución: archivos binarios grandes; respalda antes de sustituirlos.
