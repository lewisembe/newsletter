# Guía para agentes

- Propósito: utilidades de soporte para tareas Celery (selección de API keys y cálculo de costes).
- Archivos: `api_key_selector.py` rota claves según disponibilidad; `cost_calculator.py` estima consumo de tokens y costes.
- Uso: llamados desde tareas para balancear uso de LLM; mantener firmas estables para evitar errores en workers existentes.
