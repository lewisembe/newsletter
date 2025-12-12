"""
Content Validator - LLM-based validation of fetched HTML

Validates that fetched HTML contains:
1. No paywall
2. Actual article content (not just skeleton)
3. Sufficient text for extraction

Author: Newsletter Utils Team
Created: 2025-11-16
"""

import logging
from typing import Dict, Any
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


def validate_content_quality(html: str, url: str, title: str, llm_client, is_archive: bool = False) -> Dict[str, Any]:
    """
    IMPROVED: Robust paywall & content validator with heuristics + minimal LLM.

    Strategy:
    1. Use heuristics first for quick decisions (saves 80% of LLM calls)
    2. Check word count + paywall keywords before LLM
    3. Minimal JSON responses (no verbose reasons)
    4. Archive.today always assumed valid if >200 words

    Args:
        html: HTML content to validate
        url: URL of the article (for context)
        title: Expected article title (for context)
        llm_client: LLM client instance
        is_archive: True if content was fetched from archive.today

    Returns:
        Dict with:
            - is_valid: bool (True if content is complete and accessible)
            - has_paywall: bool
            - has_content: bool (sufficient article text)
            - word_count: int (estimated from visible text)
            - confidence: int (0-100)
            - reason: str (explanation of decision)
    """
    # Extract visible text for analysis
    soup = BeautifulSoup(html, 'html.parser')

    # Remove scripts, styles, and other non-content tags
    for tag in soup(['script', 'style', 'nav', 'header', 'footer', 'aside']):
        tag.decompose()

    visible_text = soup.get_text(separator=' ', strip=True)
    word_count = len(visible_text.split())

    # HEURISTIC 1: Obviously broken HTML (< 20 words = skeleton)
    if word_count < 20:
        logger.warning(f"HTML has only {word_count} words - clearly insufficient")
        return {
            'is_valid': False,
            'has_paywall': False,
            'has_content': False,
            'word_count': word_count,
            'confidence': 100,
            'reason': f'Too few words ({word_count} < 20 minimum)'
        }

    # HEURISTIC 2: Check for BLOCKING paywall keywords (not marketing)
    visible_lower = visible_text.lower()

    # These keywords indicate content is BLOCKED (not just marketing)
    blocking_keywords = [
        'suscríbete para seguir leyendo',
        'subscribe to continue reading',
        'para seguir leyendo',
        'to continue reading',
        'regístrate para continuar leyendo',
        'sign in to continue reading'
    ]

    # Marketing keywords (not blocking, just CTA)
    marketing_keywords = [
        'artículo solo para suscriptores',
        'article for subscribers only',
        'suscríbete',
        'subscribe'
    ]

    has_blocking = any(kw in visible_lower for kw in blocking_keywords)
    has_marketing = any(kw in visible_lower for kw in marketing_keywords)

    # If has blocking keywords + short content → clearly paywalled
    if has_blocking and word_count < 150:
        logger.info(f"Blocking paywall detected ({word_count} words)")
        return {
            'is_valid': False,
            'has_paywall': True,
            'has_content': False,
            'word_count': word_count,
            'confidence': 95,
            'reason': 'Blocking paywall keywords with short content'
        }

    # If has substantial content (200+ words) + NO blocking keywords → valid
    # Even if has marketing messages
    if word_count >= 200 and not has_blocking:
        logger.info(f"Substantial content ({word_count} words) without blocking paywall - assumed valid")
        return {
            'is_valid': True,
            'has_paywall': False,
            'has_content': True,
            'word_count': word_count,
            'confidence': 90,
            'reason': f'{word_count} words without blocking paywall'
        }

    # BORDERLINE CASE: 100-200 words OR has blocking keywords but substantial content
    # Send FULL content to LLM (don't truncate - need full context)
    logger.debug(f"Borderline case, sending full content to LLM ({word_count} words)")

    # ROBUST prompt that teaches the LLM the LOGIC of paywall detection
    if is_archive:
        prompt = f"""Analiza contenido de ARCHIVE.TODAY.

CONTEXTO: Archive.today preserva páginas completas tal como aparecieron.
Si ves mensajes de "suscríbete", son del sitio original pero NO bloquean el acceso.

Palabras totales: {word_count}
Título esperado: {title}

CONTENIDO (inicio + final):
{text_sample}

PREGUNTA: ¿Este contenido tiene suficiente información periodística?

LÓGICA A APLICAR:
- Archive.today captura TODO, incluyendo banners publicitarios
- Si hay múltiples párrafos desarrollando la noticia → has_content=true
- Si solo hay titular/lead → has_content=false
- Ignora completamente mensajes de suscripción (son del sitio original)

JSON:
{{
  "has_paywall": false,
  "has_content": true/false,
  "confidence": 0-100
}}"""
    else:
        prompt = f"""Analiza si este HTML tiene un PAYWALL REAL bloqueando el acceso.

Palabras totales: {word_count}
Título esperado: {title}

CONTENIDO (inicio + final):
{text_sample}

NOTA: Te muestro INICIO + FINAL del artículo ({word_count} palabras total).
Si ves "[...CONTENIDO MEDIO OMITIDO...]" es solo para ahorrar tokens, NO significa que esté cortado.

LÓGICA DE PAYWALL:
Un paywall REAL bloquea el acceso. Señales:
1. Contenido se CORTA abruptamente (historia inconclusa, sin final)
2. Mensaje imperativo "suscríbete PARA SEGUIR leyendo", "subscribe TO CONTINUE reading"

NO es paywall si:
- Historia tiene principio, desarrollo Y final/conclusión
- Párrafos desarrollan la noticia completamente (aunque sea breve)
- Mensajes de suscripción al final DESPUÉS del contenido completo ("Artículo solo para suscriptores" puede ser solo un banner)

CLAVE: Distingue entre:
- PAYWALL: "Titular. Intro. [Suscríbete PARA seguir leyendo]" ← Historia CORTADA, no hay final
- NO PAYWALL: "Titular. Intro. Desarrollo. Conclusión. [Artículo solo para suscriptores]" ← Historia COMPLETA + banner marketing

EVALÚA:
1. ¿La historia está COMPLETA (tiene desarrollo y cierre) o CORTADA (se interrumpe sin terminar)?
2. ¿Hay mensaje que IMPIDE continuar ("PARA seguir leyendo") o solo invita a suscribirse DESPUÉS del contenido?
3. Ignora el número de palabras - un artículo de 150 palabras puede estar completo, uno de 500 puede estar cortado.

JSON:
{{
  "has_paywall": true/false,
  "has_content": true/false,
  "confidence": 0-100
}}"""

    try:
        logger.debug(f"LLM validation for borderline case: {word_count} words")

        response = llm_client.call(
            prompt=prompt,
            system_prompt="Eres experto en detectar paywalls y validar contenido web extraído.",
            max_tokens=80,  # Reduced from 200, enough for JSON response
            temperature=0.1,
            response_format={"type": "json_object"},
            stage="04",
            operation="content_validation"
        )

        import json
        result = json.loads(response)

        # Determine if content is valid
        is_valid = (
            not result.get('has_paywall', True) and
            result.get('has_content', False)
        )

        logger.info(f"LLM validation for {url}: paywall={result.get('has_paywall')}, has_content={result.get('has_content')}, valid={is_valid}")

        return {
            'is_valid': is_valid,
            'has_paywall': result.get('has_paywall', True),
            'has_content': result.get('has_content', False),
            'word_count': word_count,
            'confidence': result.get('confidence', 50),
            'reason': f'LLM validated (borderline {word_count} words)'
        }

    except Exception as e:
        logger.error(f"LLM validation failed: {e}")

        # Fallback: basic heuristic
        # If word count is reasonable, assume it's OK
        has_enough_words = word_count >= 100

        return {
            'is_valid': has_enough_words,
            'has_paywall': False,  # Can't determine
            'has_content': has_enough_words,
            'word_count': word_count,
            'confidence': 30,  # Low confidence (fallback)
            'reason': f'LLM validation failed, using word count heuristic ({word_count} words)'
        }
