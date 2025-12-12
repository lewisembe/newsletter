"""
Content Extractors

Multiple extraction methods for article content:
1. newspaper3k - Automatic extraction (70-80% success)
2. readability-lxml - Mozilla algorithm (fallback)
3. LLM XPath Discovery - Intelligent selector discovery
4. Selector-based - Generic extraction using CSS/XPath

Author: Newsletter Utils Team
Created: 2025-11-13
"""

import os
import json
import logging
from typing import Dict, Any, Optional
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


def extract_json_ld(html: str) -> Dict[str, Any]:
    """
    Extract content from JSON-LD structured data (schema.org).

    Many news sites (Financial Times, NYT, etc.) embed article content
    in <script type="application/ld+json"> tags using schema.org vocabulary.

    This extractor searches for NewsArticle/Article JSON-LD and extracts
    the articleBody field.

    Args:
        html: HTML content to extract from

    Returns:
        Dict with keys: success, content, word_count, method
    """
    try:
        soup = BeautifulSoup(html, 'lxml')

        # Find all JSON-LD scripts
        json_ld_scripts = soup.find_all('script', type='application/ld+json')

        for script in json_ld_scripts:
            try:
                data = json.loads(script.string)

                # Handle both single objects and arrays
                items = data if isinstance(data, list) else [data]

                for item in items:
                    # Check if this is a NewsArticle or Article
                    item_type = item.get('@type', '')

                    if item_type in ['NewsArticle', 'Article', 'BlogPosting']:
                        # Extract articleBody
                        content = item.get('articleBody', '')

                        if content:
                            word_count = len(content.split())

                            if word_count < 100:
                                logger.debug(f"JSON-LD: Content too short ({word_count} words)")
                                continue

                            logger.info(f"JSON-LD: Extracted {word_count} words from {item_type}")
                            return {
                                'success': True,
                                'content': content,
                                'word_count': word_count,
                                'method': 'json_ld'
                            }

            except json.JSONDecodeError as e:
                logger.debug(f"JSON-LD: Invalid JSON in script tag: {e}")
                continue
            except Exception as e:
                logger.debug(f"JSON-LD: Error parsing script: {e}")
                continue

        # No valid JSON-LD found
        logger.debug("JSON-LD: No NewsArticle/Article found in structured data")
        return {
            'success': False,
            'content': '',
            'word_count': 0,
            'method': 'json_ld',
            'error': 'No NewsArticle/Article JSON-LD found'
        }

    except Exception as e:
        logger.error(f"JSON-LD extraction unexpected error: {e}")
        return {
            'success': False,
            'content': '',
            'word_count': 0,
            'method': 'json_ld',
            'error': str(e)
        }


def extract_with_newspaper(html: str) -> Dict[str, Any]:
    """
    Extract content using newspaper3k library.

    newspaper3k uses heuristics to identify main content:
    - Looks for <article>, <main>, .post-content tags
    - Calculates text density in divs
    - Filters navigation, headers, footers automatically

    Args:
        html: HTML content to extract from

    Returns:
        Dict with keys: success, content, word_count, method
    """
    try:
        from newspaper import Article
        from newspaper import ArticleException

        # Create Article without downloading (we already have HTML)
        article = Article('')
        article.set_html(html)
        article.parse()

        content = article.text.strip()
        word_count = len(content.split())

        if word_count < 100:
            logger.debug(f"newspaper3k: Content too short ({word_count} words)")
            return {
                'success': False,
                'content': content,
                'word_count': word_count,
                'method': 'newspaper',
                'error': f'Content too short ({word_count} words)'
            }

        logger.debug(f"newspaper3k: Extracted {word_count} words")
        return {
            'success': True,
            'content': content,
            'word_count': word_count,
            'method': 'newspaper'
        }

    except ArticleException as e:
        logger.debug(f"newspaper3k failed: {e}")
        return {
            'success': False,
            'content': '',
            'word_count': 0,
            'method': 'newspaper',
            'error': str(e)
        }
    except Exception as e:
        logger.error(f"newspaper3k unexpected error: {e}")
        return {
            'success': False,
            'content': '',
            'word_count': 0,
            'method': 'newspaper',
            'error': str(e)
        }


def extract_with_readability(html: str) -> Dict[str, Any]:
    """
    Extract content using readability-lxml (Mozilla algorithm).

    readability assigns scores to DOM nodes based on:
    - Text amount
    - Text/HTML ratio
    - Presence of <p> tags
    - Absence of <nav>, <aside> tags

    Args:
        html: HTML content to extract from

    Returns:
        Dict with keys: success, content, word_count, method
    """
    try:
        from readability import Document
        import html2text

        doc = Document(html)
        content_html = doc.summary()

        # Convert HTML to plain text
        h = html2text.HTML2Text()
        h.ignore_links = False
        h.ignore_images = True
        h.body_width = 0  # Don't wrap text
        content = h.handle(content_html).strip()

        word_count = len(content.split())

        if word_count < 100:
            logger.debug(f"readability: Content too short ({word_count} words)")
            return {
                'success': False,
                'content': content,
                'word_count': word_count,
                'method': 'readability',
                'error': f'Content too short ({word_count} words)'
            }

        logger.debug(f"readability: Extracted {word_count} words")
        return {
            'success': True,
            'content': content,
            'word_count': word_count,
            'method': 'readability'
        }

    except Exception as e:
        logger.error(f"readability failed: {e}")
        return {
            'success': False,
            'content': '',
            'word_count': 0,
            'method': 'readability',
            'error': str(e)
        }


def extract_with_selector(
    html: str,
    selector: str,
    selector_type: str = 'css'
) -> Dict[str, Any]:
    """
    Extract content using a specific CSS selector or XPath.

    Used by:
    - XPath cache (reusing discovered selectors)
    - LLM XPath discovery (after selector is found)

    Args:
        html: HTML content
        selector: CSS selector or XPath string
        selector_type: 'css' or 'xpath'

    Returns:
        Dict with keys: success, content, word_count, method
    """
    try:
        if selector_type == 'xpath':
            # Use lxml for XPath
            from lxml import html as lxml_html
            tree = lxml_html.fromstring(html)
            elements = tree.xpath(selector)

            # Extract text from each element
            paragraphs = []
            for elem in elements:
                try:
                    text = elem.text_content().strip()
                    if text and len(text) > 20:  # Filter very short paragraphs
                        paragraphs.append(text)
                except Exception as e:
                    logger.debug(f"Error extracting text from element: {e}")
                    continue

        else:  # CSS selector
            soup = BeautifulSoup(html, 'lxml')
            elements = soup.select(selector)

            paragraphs = [
                elem.get_text(strip=True)
                for elem in elements
                if len(elem.get_text(strip=True)) > 20
            ]

        content = '\n\n'.join(paragraphs)
        word_count = len(content.split())

        if word_count < 100:
            logger.debug(f"Selector extraction: Content too short ({word_count} words)")
            return {
                'success': False,
                'content': content,
                'word_count': word_count,
                'method': f'selector_{selector_type}',
                'error': f'Content too short ({word_count} words)'
            }

        logger.debug(f"Selector extraction: Extracted {word_count} words using {selector}")
        return {
            'success': True,
            'content': content,
            'word_count': word_count,
            'method': f'selector_{selector_type}',
            'selector_used': selector
        }

    except Exception as e:
        logger.error(f"Selector extraction failed ({selector_type}): {e}")
        return {
            'success': False,
            'content': '',
            'word_count': 0,
            'method': f'selector_{selector_type}',
            'error': str(e)
        }


def extract_with_llm_xpath(
    html: str,
    url: str,
    llm_client: Any,
    model: str = None
) -> Dict[str, Any]:
    """
    Use LLM to discover XPath/CSS selector and extract content (ENHANCED VERSION).

    This enhanced version uses a multi-step analysis process:
    1. Analyze HTML structure to identify article containers
    2. Generate multiple candidate selectors
    3. Test each selector and rank by quality
    4. Return best working selector

    Process:
    1. Extract HTML structure (first 12000 chars for better context)
    2. Ask LLM to analyze and identify MULTIPLE candidate selectors
    3. Test each selector and pick the one with best results
    4. Return result with selector for caching

    Args:
        html: Full HTML content
        url: URL being extracted (for context)
        llm_client: LLM client instance
        model: Model to use (defaults to MODEL_XPATH_DISCOVERY from env)

    Returns:
        Dict with keys: success, content, word_count, method, selector_used, confidence
    """
    if model is None:
        model = os.getenv('MODEL_XPATH_DISCOVERY', 'gpt-4o-mini')

    try:
        # Use more HTML for better analysis (12K chars covers most article structures)
        html_sample = html[:12000]

        # Extract domain for context
        from urllib.parse import urlparse
        domain = urlparse(url).netloc

        logger.debug(f"LLM XPath discovery for {url} (sample: {len(html_sample)} chars)")

        system_prompt = """Eres un experto de élite en web scraping, análisis de HTML y extracción de contenido.
Tu especialidad es identificar selectores CSS/XPath precisos para extraer contenido de artículos periodísticos de cualquier sitio web."""

        user_prompt = f"""Analiza este HTML de un artículo de noticias y descubre los MEJORES selectores para extraer el contenido.

🔗 URL: {url}
🌐 Dominio: {domain}

📄 HTML (primeros 12000 caracteres):
{html_sample}

🎯 OBJETIVO:
Identifica 3 CANDIDATOS de selectores ordenados de mejor a peor para extraer el CONTENIDO PRINCIPAL del artículo (los párrafos del cuerpo del texto).

📋 PROCESO DE ANÁLISIS (sigue estos pasos mentalmente):

PASO 1 - IDENTIFICAR CONTENEDORES PRINCIPALES:
- Busca tags semánticos: <article>, <main>, <section>
- Identifica divs con clases significativas: "article", "story", "content", "body", "post"
- Observa IDs relevantes: "article-body", "story-content", "main-content"

PASO 2 - ANALIZAR ESTRUCTURA DE PÁRRAFOS:
- ¿Dónde están los <p> tags con más texto?
- ¿Hay un contenedor que agrupe múltiples párrafos?
- ¿Los párrafos están dentro de article, div.content, o section?

PASO 3 - EXCLUIR RUIDO:
- Ignora: <nav>, <header>, <footer>, <aside>
- Ignora clases: "sidebar", "related", "comments", "ad", "promo", "newsletter"
- Ignora contenido corto (< 50 caracteres por párrafo)

PASO 4 - CONSTRUIR SELECTORES:
Prioridad de selectores (de más específico a más genérico):
1. Por ID específico: "#article-body p", "#story-content p"
2. Por clase del article: "article.story p", ".article-content p"
3. Por estructura semántica: "article p", "main article p"
4. Por clase genérica: ".content p", ".post-body p"

CRITERIOS DE UN BUEN SELECTOR:
✅ Específico (evita capturar navegación o sidebars)
✅ Robusto (no depende de índices numéricos)
✅ Captura TODOS los párrafos del artículo
✅ Ignora elementos irrelevantes (ads, comentarios)

EJEMPLOS DE BUENOS SELECTORES POR SITIO:

New York Times:
- "article#story p" o "section[name='articleBody'] p"

The Guardian:
- ".article-body-commercial-selector p" o "#maincontent article p"

El País:
- "article.a_c p" o "#cuerpo_noticia p"

Financial Times:
- ".article__content-body p" o "#storyBox p"

RESPUESTA JSON (sin explicaciones, solo selectores):
{{
  "candidates": [
    {{
      "selector": "<MEJOR selector CSS/XPath>",
      "selector_type": "css",
      "confidence": 85
    }},
    {{
      "selector": "<segundo mejor>",
      "selector_type": "css",
      "confidence": 70
    }},
    {{
      "selector": "<fallback genérico>",
      "selector_type": "css",
      "confidence": 50
    }}
  ]
}}

IMPORTANTE: Selectores deben terminar en "p" o "//p". Prioriza CSS sobre XPath.

JSON:"""

        response = llm_client.call(
            prompt=user_prompt,
            system_prompt=system_prompt,
            model=model,
            temperature=0.2,
            max_tokens=300,  # Reduced from 1000 (no reasoning needed)
            response_format={"type": "json_object"},
            stage="04",
            operation="xpath_discovery_enhanced",
            run_date=None
        )

        result = json.loads(response)

        # Extract candidates (no analysis needed)
        candidates = result.get('candidates', [])

        if not candidates:
            logger.error("LLM returned no selector candidates")
            return {
                'success': False,
                'content': '',
                'word_count': 0,
                'method': 'llm_xpath',
                'error': 'LLM returned no selector candidates'
            }

        logger.info(f"LLM provided {len(candidates)} candidate selectors")

        # Try each candidate selector in order (best to worst)
        for i, candidate in enumerate(candidates, 1):
            selector = candidate.get('selector')
            selector_type = candidate.get('selector_type', 'css')
            confidence = candidate.get('confidence', 0)

            if not selector:
                continue

            logger.info(f"[Candidate {i}/{len(candidates)}] Testing: {selector} (confidence: {confidence}%)")

            # Extract using this candidate
            extraction = extract_with_selector(html, selector, selector_type)

            if extraction['success']:
                word_count = extraction['word_count']
                logger.info(f"✓ Candidate {i} SUCCESS: Extracted {word_count} words")

                # Add LLM-specific metadata
                extraction['method'] = 'llm_xpath'
                extraction['selector_used'] = selector
                extraction['selector_type'] = selector_type
                extraction['confidence'] = confidence
                extraction['candidate_rank'] = i
                extraction['total_candidates'] = len(candidates)

                return extraction
            else:
                logger.warning(f"✗ Candidate {i} FAILED: {extraction.get('error', 'Unknown error')}")

        # All candidates failed
        logger.error(f"All {len(candidates)} candidate selectors failed")
        return {
            'success': False,
            'content': '',
            'word_count': 0,
            'method': 'llm_xpath',
            'error': f'All {len(candidates)} candidate selectors failed',
            'candidates_tested': len(candidates)
        }

    except json.JSONDecodeError as e:
        logger.error(f"LLM XPath discovery: Invalid JSON response: {e}")
        logger.error(f"Response: {response[:500] if 'response' in locals() else 'N/A'}")
        return {
            'success': False,
            'content': '',
            'word_count': 0,
            'method': 'llm_xpath',
            'error': f'Invalid JSON from LLM: {e}'
        }
    except Exception as e:
        logger.error(f"LLM XPath discovery failed: {e}")
        return {
            'success': False,
            'content': '',
            'word_count': 0,
            'method': 'llm_xpath',
            'error': str(e)
        }


def extract_with_llm_direct(
    html: str,
    url: str,
    title: str,
    llm_client: Any,
    model: str = None
) -> Dict[str, Any]:
    """
    Use LLM to directly extract article content from HTML (last resort fallback).

    This method doesn't try to discover selectors - instead, it asks the LLM
    to read the HTML and extract the article content directly.

    Used when all other methods (newspaper, readability, xpath) have failed.

    Process:
    1. Truncate HTML to ~15000 chars (balance between context and token cost)
    2. Ask LLM to identify and extract the main article text
    3. Return extracted content

    Args:
        html: Full HTML content
        url: URL being extracted (for context)
        title: Article title (helps LLM identify content)
        llm_client: LLM client instance
        model: Model to use (defaults to MODEL_XPATH_DISCOVERY from env)

    Returns:
        Dict with keys: success, content, word_count, method
    """
    if model is None:
        model = os.getenv('MODEL_XPATH_DISCOVERY', 'gpt-4o-mini')

    try:
        # Truncate HTML for LLM (balance between context and cost)
        # Most article content is in the first 15K chars
        html_sample = html[:15000]

        logger.debug(f"LLM direct extraction for {url} (sample: {len(html_sample)} chars)")

        system_prompt = "Eres un experto en extracción de contenido de artículos de noticias. Tu tarea es leer HTML y extraer solo el contenido principal del artículo."

        user_prompt = f"""Extrae el CONTENIDO PRINCIPAL de este artículo.

URL: {url}
Título: {title}

HTML (primeros 15000 caracteres):
{html_sample}

TAREA:
Lee el HTML y extrae SOLO el texto del artículo principal. Ignora:
- Navegación, headers, footers
- Barras laterales (sidebars)
- Anuncios y publicidad
- Enlaces relacionados
- Comentarios
- Formularios de suscripción

IMPORTANTE:
- Extrae TODOS los párrafos del contenido principal
- Mantén el orden original
- Separa párrafos con doble salto de línea
- NO incluyas título, metadatos, ni navegación

JSON (solo contenido, sin notas):
{{
  "article_content": "<contenido del artículo>",
  "confidence": 0-100
}}

JSON:"""

        response = llm_client.call(
            prompt=user_prompt,
            system_prompt=system_prompt,
            model=model,
            temperature=0.1,
            max_tokens=4000,  # Keep high - need full article
            response_format={"type": "json_object"},
            stage="04",
            operation="llm_direct_extraction",
            run_date=None
        )

        result = json.loads(response)
        content = result.get('article_content', '').strip()
        confidence = result.get('confidence', result.get('extraction_confidence', 0))

        if not content:
            logger.error("LLM returned empty content")
            return {
                'success': False,
                'content': '',
                'word_count': 0,
                'method': 'llm_direct',
                'error': 'LLM returned empty content'
            }

        word_count = len(content.split())

        if word_count < 100:
            logger.warning(f"LLM direct extraction: Content too short ({word_count} words)")
            return {
                'success': False,
                'content': content,
                'word_count': word_count,
                'method': 'llm_direct',
                'error': f'Content too short ({word_count} words)'
            }

        logger.info(f"LLM direct extraction: Extracted {word_count} words (confidence: {confidence}%)")

        return {
            'success': True,
            'content': content,
            'word_count': word_count,
            'method': 'llm_direct',
            'confidence': confidence
        }

    except json.JSONDecodeError as e:
        logger.error(f"LLM direct extraction: Invalid JSON response: {e}")
        return {
            'success': False,
            'content': '',
            'word_count': 0,
            'method': 'llm_direct',
            'error': f'Invalid JSON from LLM: {e}'
        }
    except Exception as e:
        logger.error(f"LLM direct extraction failed: {e}")
        return {
            'success': False,
            'content': '',
            'word_count': 0,
            'method': 'llm_direct',
            'error': str(e)
        }


def extract_content_with_cache(
    url: str,
    html: str,
    llm_client: Any,
    xpath_cache: Dict,
    title: str = "Untitled"
) -> Dict[str, Any]:
    """
    Orchestrator: Extract content using cascading fallback with cache.

    Extraction order:
    1. XPath Cache (if exists for domain) - FREE, instant
    2. JSON-LD (schema.org structured data) - FREE, standard
    3. newspaper3k - FREE, automatic
    4. readability - FREE, Mozilla algorithm
    5. LLM XPath Discovery - Paid, intelligent selector discovery
    6. LLM Direct Extraction - Paid, last resort (reads HTML directly)

    Each method's output is validated for completeness (if word_count < 500).
    If incomplete, continues to next method.

    Args:
        url: URL being extracted
        html: HTML content
        llm_client: LLM client instance
        xpath_cache: Loaded XPath cache dict
        title: Article title (for completeness validation)

    Returns:
        Dict with extraction result
    """
    from .xpath_cache import find_cached_xpath, update_xpath_cache
    from common.llm import validate_content_completeness

    # Load validation config
    validate_completeness = os.getenv('STAGE04_VALIDATE_COMPLETENESS', 'true').lower() == 'true'
    validate_threshold = int(os.getenv('STAGE04_VALIDATE_THRESHOLD', '500'))

    def check_completeness(result: Dict[str, Any], method_name: str) -> bool:
        """
        Validate if extracted content is complete.
        Returns True if complete, False if truncated.
        """
        if not result['success']:
            return False

        word_count = result['word_count']

        # Skip validation if disabled or word_count above threshold
        if not validate_completeness or word_count >= validate_threshold:
            logger.debug(f"{method_name}: Skipping completeness validation (word_count={word_count}, threshold={validate_threshold})")
            return True

        # Validate with LLM
        logger.info(f"{method_name}: Validating completeness (word_count={word_count} < {validate_threshold})")

        validation = validate_content_completeness(
            content=result['content'],
            title=title,
            url=url,
            llm_client=llm_client,
            stage="04"
        )

        is_complete = validation['is_complete']
        confidence = validation['confidence']
        reason = validation['reason']

        if is_complete:
            logger.info(f"✓ {method_name}: Content validated as COMPLETE (confidence: {confidence}%)")
            return True
        else:
            logger.warning(f"✗ {method_name}: Content detected as INCOMPLETE (confidence: {confidence}%)")
            logger.warning(f"  Reason: {reason}")
            if validation['truncation_signals']:
                logger.warning(f"  Signals: {', '.join(validation['truncation_signals'])}")
            return False

    # STEP 0: Try cached XPath if available
    cached_xpath = find_cached_xpath(url, xpath_cache)

    if cached_xpath:
        selector = cached_xpath['content_selector']
        selector_type = cached_xpath['selector_type']

        logger.info(f"[1/5] Trying cached XPath: {selector}")

        result = extract_with_selector(html, selector, selector_type)

        if result['success'] and check_completeness(result, "Cached XPath"):
            logger.info(f"✓ Extracted with cached XPath: {result['word_count']} words")
            result['method'] = 'xpath_cache'
            update_xpath_cache(url, selector, selector_type, cached_xpath.get('confidence', 80), success=True)
            return result
        else:
            logger.warning("Cached XPath failed or incomplete, marking and continuing to fallback...")
            update_xpath_cache(url, selector, selector_type, cached_xpath.get('confidence', 80), success=False)

    # STEP 1: JSON-LD (schema.org structured data)
    logger.info(f"[{2 if cached_xpath else 1}/5] Trying JSON-LD extraction")
    result = extract_json_ld(html)

    if result['success'] and check_completeness(result, "JSON-LD"):
        logger.info(f"✓ Extracted with JSON-LD: {result['word_count']} words")
        return result

    # STEP 2: newspaper3k
    logger.info(f"[{3 if cached_xpath else 2}/5] Trying newspaper3k")
    result = extract_with_newspaper(html)

    if result['success'] and check_completeness(result, "newspaper3k"):
        logger.info(f"✓ Extracted with newspaper3k: {result['word_count']} words")
        return result

    # STEP 3: readability
    logger.info(f"[{4 if cached_xpath else 3}/5] Trying readability")
    result = extract_with_readability(html)

    if result['success'] and check_completeness(result, "readability"):
        logger.info(f"✓ Extracted with readability: {result['word_count']} words")
        return result

    # STEP 4: LLM XPath Discovery
    logger.info(f"[{5 if cached_xpath else 4}/6] Trying LLM XPath discovery")
    result = extract_with_llm_xpath(html, url, llm_client)

    if result['success'] and check_completeness(result, "LLM XPath"):
        logger.info(f"✓ Extracted with LLM XPath: {result['word_count']} words")

        # Cache the discovered selector
        update_xpath_cache(
            url,
            result['selector_used'],
            result.get('selector_type', 'css'),
            result.get('confidence', 80),
            success=True
        )
        return result

    # STEP 5: LLM Direct Extraction (last resort)
    logger.info(f"[{6 if cached_xpath else 5}/6] Trying LLM direct extraction (last resort)")
    logger.warning("⚠️  All traditional methods failed. Using LLM to read HTML directly (this may incur higher token costs)")

    result = extract_with_llm_direct(html, url, title, llm_client)

    if result['success']:
        logger.info(f"✓ Extracted with LLM direct extraction: {result['word_count']} words")
        return result

    # STEP 6: All methods failed
    logger.error(f"✗ All extraction methods failed for {url} (including LLM direct extraction)")
    return {
        'success': False,
        'content': '',
        'word_count': 0,
        'method': 'failed',
        'error': 'All extraction methods failed (including LLM direct extraction)'
    }
