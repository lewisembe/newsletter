# Guía para agentes

- Propósito: definiciones de prompts en JSON para distintos estilos de newsletter/resumen.
- Archivos: `default*.json`, `tech_focus.json`, `chief_economist.json`, `concise.json` describen instrucciones y temperatura/tokens.
- Uso: cargados por las etapas de ranking/generación; conserva claves esperadas (`system`, `user`, etc.).
- Extensión: crea nuevos archivos duplicando uno existente y ajustando parámetros; referencia desde configs correspondientes.
