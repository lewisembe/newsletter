# Guía para agentes

- Contenido: modelos entrenados en pickle (`*_classifier.pkl`) listos para cargar desde los scripts de clasificación.
- Uso: referencia en `config*.yml` para rutas; evita modificar estos binarios sin regenerarlos con `train_classifier.py`.
- Control de versiones: si agregas un nuevo modelo, documenta métricas en `output/` y actualiza las configs correspondientes.
