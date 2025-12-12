"""
Paywall Detection Validator

Detects paywalls in HTML content using LLM-based validation.
Optimized to use only beginning and end of content to save tokens.

Author: Newsletter Utils Team
Created: 2025-11-13
"""

import logging
from bs4 import BeautifulSoup
from typing import Dict, Any

logger = logging.getLogger(__name__)


def detect_paywall_with_llm(
    html: str,
    url: str,
    llm_client: Any,
    model: str = None
) -> bool:
    """
    OPTIMIZED: Detect paywall using heuristics first, then LLM if needed.

    Strategy:
    1. Check for obvious paywall keywords first (saves 80% of LLM calls)
    2. Only use LLM for borderline cases
    3. JSON structured response for consistency

    Args:
        html: HTML content to analyze
        url: URL being analyzed (for context)
        llm_client: LLM client instance with call() method
        model: Model to use (defaults to MODEL_PAYWALL_VALIDATOR from env)

    Returns:
        True if paywall detected, False if content is free
    """
    import os
    import json

    if model is None:
        model = os.getenv('MODEL_PAYWALL_VALIDATOR', 'gpt-4o-mini')

    try:
        # Extract visible text from HTML
        soup = BeautifulSoup(html, 'lxml')

        # Remove script and style tags
        for tag in soup(['script', 'style', 'noscript']):
            tag.decompose()

        # Get full visible text
        full_text = soup.get_text(separator=' ', strip=True)
        full_text_lower = full_text.lower()

        # HEURISTIC 1: Check for obvious strong paywall keywords
        strong_paywall_keywords = [
            'suscríbete para seguir leyendo',
            'subscribe to continue reading',
            'this article is for subscribers only',
            'este contenido es exclusivo para suscriptores',
            'regístrate para acceder al contenido completo',
            'hazte premium para leer',
            'become a member to read'
        ]

        has_strong_paywall = any(kw in full_text_lower for kw in strong_paywall_keywords)

        if has_strong_paywall:
            logger.info(f"Paywall detected via heuristics for {url}")
            return True

        # HEURISTIC 2: If content is long (>1500 words), likely no paywall
        word_count = len(full_text.split())
        if word_count >= 1500:
            logger.info(f"No paywall (long content: {word_count} words) for {url}")
            return False

        # BORDERLINE CASE: Use LLM for 300-1500 word articles
        # Optimize: Take beginning + end (where paywalls usually appear)
        inicio = full_text[:500]
        final = full_text[-1000:] if len(full_text) > 1000 else full_text

        # Combine for analysis
        sample = f"[INICIO]\n{inicio}\n\n[FINAL]\n{final}"

        logger.debug(f"LLM paywall check for {url}: sample length = {len(sample)} chars")

        # Optimized LLM prompt with JSON response
        system_prompt = """Eres un experto detector de paywalls en sitios de noticias.
Tu tarea es distinguir entre contenido bloqueado (paywall REAL) vs contenido completo con mensajes de apoyo."""

        user_prompt = f"""Analiza si este artículo tiene un PAYWALL que BLOQUEA el contenido.

Contenido (inicio + final):
{sample}

IMPORTANTE - Criterios de evaluación:

1. **PAYWALL REAL (has_paywall = true)**:
   - El contenido narrativo está TRUNCADO o INCOMPLETO (corte abrupto en medio de la historia)
   - Hay mensaje explícito tipo "Suscríbete para SEGUIR leyendo" / "Subscribe to CONTINUE reading"
   - La información principal del artículo NO está disponible
   - Ejemplo: artículo sobre economía que solo muestra el titular y primer párrafo, luego pide suscripción

2. **NO ES PAYWALL (has_paywall = false)**:
   - El contenido tiene estructura narrativa COMPLETA (introducción → desarrollo → conclusión)
   - Hay varios párrafos con información coherente y sustancial
   - Puede haber mensajes tipo "Apóyanos" / "Hazte suscriptor" pero como CTA (call to action), NO bloqueando contenido
   - La noticia está completa aunque haya mensajes de donación/suscripción al final
   - Ejemplo: artículo de 4-5 párrafos completo + mensaje final "Ayúdanos a seguir haciendo periodismo"

3. **Señales de contenido COMPLETO**:
   - Múltiples párrafos con datos, citas, contexto
   - Narrativa coherente de inicio a fin
   - Presencia de conclusiones o cierres informativos

**REGLA DE ORO**: Si el artículo tiene suficiente contenido para entender la noticia completa (aunque tenga CTA de suscripción), NO es paywall.

En caso de duda → has_paywall = false (preferimos incluir contenido que descartarlo)

Responde SOLO en JSON:
{{
  "has_paywall": true/false
}}"""

        response = llm_client.call(
            prompt=user_prompt,
            system_prompt=system_prompt,
            model=model,
            temperature=0,
            max_tokens=20,  # Minimal for boolean JSON response
            response_format={"type": "json_object"},
            stage="04",
            operation="paywall_detection",
            run_date=None
        )

        # Parse JSON response
        result = json.loads(response)
        is_paywalled = result.get('has_paywall', False)

        logger.info(f"LLM paywall detection for {url}: {'PAYWALL' if is_paywalled else 'FREE'}")

        return is_paywalled

    except Exception as e:
        logger.error(f"Paywall detection failed for {url}: {e}")
        # On error, assume no paywall (conservative approach)
        return False


def extract_sample_for_paywall(html: str, max_chars: int = 1500) -> str:
    """
    Extract text sample from HTML for paywall detection.

    Takes beginning and end of visible content where paywalls typically appear.

    Args:
        html: HTML content
        max_chars: Maximum chars to extract (default: 1500)

    Returns:
        Text sample (beginning + end)
    """
    soup = BeautifulSoup(html, 'lxml')

    # Remove non-content tags
    for tag in soup(['script', 'style', 'noscript', 'iframe']):
        tag.decompose()

    full_text = soup.get_text(separator=' ', strip=True)

    # Take 1/3 from beginning, 2/3 from end (paywalls usually at end)
    beginning_chars = max_chars // 3
    ending_chars = (max_chars * 2) // 3

    beginning = full_text[:beginning_chars]
    ending = full_text[-ending_chars:] if len(full_text) > ending_chars else full_text

    return f"{beginning}\n\n[...]\n\n{ending}"
