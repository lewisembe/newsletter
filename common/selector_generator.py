"""
Automatic CSS selector generator using LLM.
Analyzes HTML structure and generates optimal selectors for news article extraction.
"""

import json
import logging
from typing import List, Optional
from .llm import LLMClient

logger = logging.getLogger(__name__)


def generate_selectors_with_llm(
    source_id: str,
    source_name: str,
    html_content: str,
    llm_client: Optional[LLMClient] = None,
    run_date: Optional[str] = None
) -> List[str]:
    """
    Generate CSS selectors using LLM analysis of HTML structure.

    Args:
        source_id: Source identifier (e.g., "elconfidencial")
        source_name: Human-readable source name
        html_content: HTML content of the page
        llm_client: LLM client instance (creates new if None)
        run_date: Run date for token tracking

    Returns:
        List of CSS selectors for extracting news article links
    """
    if llm_client is None:
        llm_client = LLMClient()

    # Truncate HTML to avoid token limits (keep first 20000 chars)
    html_sample = html_content[:20000]

    system_prompt = """Eres un experto en scraping web y selectores CSS. Tu tarea es analizar el HTML de una página de noticias y generar los mejores selectores CSS para extraer enlaces a artículos de noticias.

Criterios para buenos selectores:
- Deben seleccionar enlaces (<a>) que apunten a artículos de noticias individuales
- Evitar enlaces de navegación, menús, footer, publicidad
- PRIORIDAD 1: Selectores basados en patrones de URL que contengan palabras clave de noticias:
  Ejemplos: a[href*='/noticia/'], a[href*='/articulo/'], a[href*='/news/'], a[href*='/story/'], a[href*='/2025/'], a[href*='/2024/']
- PRIORIDAD 2: Clases CSS o atributos data-* específicos de artículos
  Ejemplos: a[class*='article'], a[class*='story'], a[data-type*='article'], a[class*='headline']
- PRIORIDAD 3: Selectores estructurales más amplios pero aún específicos
  Ejemplos: article a, .news-list a, .headlines a
- Evitar selectores muy genéricos como "a" o "div a"
- NO generes selectores que capturen TODOS los enlaces del dominio sin filtros (como a[href^='https://dominio.com/'])
- Incluye 5-8 selectores ordenados de más a menos específico

Devuelve ÚNICAMENTE un JSON válido con este formato exacto:
{
  "selectors": [
    "selector.css.mas.especifico",
    "selector.css.alternativo",
    "selector.css.fallback"
  ]
}"""

    user_prompt = f"""Analiza este HTML de la página principal de "{source_name}" y genera los mejores selectores CSS para extraer enlaces a artículos de noticias.

HTML (primeros 20000 caracteres):
```html
{html_sample}
```

Devuelve un JSON con una lista de selectores CSS ordenados de más específico a más general.
Incluye 3-7 selectores diferentes que capturen artículos de noticias.

IMPORTANTE: NO incluyas selectores genéricos que capturen todos los enlaces del sitio (ejemplo de lo que NO hacer: a[href^='https://ejemplo.com/']).
Todos los selectores deben ser específicos a contenedores de artículos, clases CSS de noticias, o patrones de URL que identifiquen noticias."""

    try:
        logger.info(f"Generating CSS selectors for {source_name} using LLM")

        response = llm_client.call(
            prompt=user_prompt,
            system_prompt=system_prompt,
            model="gpt-4o-mini",
            temperature=0.2,
            max_tokens=1000,
            response_format={"type": "json_object"},
            stage="01",
            operation=f"generate_selectors_{source_id}",
            run_date=run_date
        )

        # Parse JSON response
        result = json.loads(response)
        selectors = result.get('selectors', [])

        if not selectors:
            logger.warning(f"LLM returned empty selectors list for {source_name}")
            # Fallback to generic selectors
            selectors = ["article a", "h2 a", "h3 a", "a[href*='/']"]

        logger.info(f"Generated {len(selectors)} selectors for {source_name}")
        logger.debug(f"Selectors: {selectors}")

        return selectors

    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse LLM JSON response: {e}")
        logger.error(f"Response was: {response}")
        # Fallback to generic selectors
        return ["article a", "h2 a", "h3 a", ".headline a"]

    except Exception as e:
        logger.error(f"Error generating selectors for {source_name}: {e}")
        # Fallback to generic selectors
        return ["article a", "h2 a", "h3 a"]
