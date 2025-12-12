"""
LLM utilities for OpenAI API interactions.
Provides functions for URL filtering, classification, ranking, and content generation.
"""

import os
import json
import logging
from typing import List, Dict, Optional, Any
from openai import OpenAI
from dotenv import load_dotenv
from .token_tracker import log_tokens

load_dotenv()
logger = logging.getLogger(__name__)


class LLMClient:
    """Client for OpenAI API interactions with fallback support."""

    def __init__(self, api_key: Optional[str] = None, api_key_id: Optional[int] = None, enable_fallback: bool = True):
        """
        Initialize OpenAI client with optional fallback support.

        Args:
            api_key: OpenAI API key (defaults to OPENAI_API_KEY env var)
            api_key_id: Optional API key ID for fallback support (fetches from database)
            enable_fallback: If False, only use the primary key (no fallback)
        """
        self.api_key_id = api_key_id
        self.api_keys = []  # List of (id, alias, decrypted_key) tuples for fallback
        self.current_key_index = 0
        self.api_keys_used = set()  # Track which API key IDs were actually used
        self.enable_fallback = enable_fallback

        if api_key_id:
            # Load API keys with fallback from database
            self._load_api_keys_from_db(api_key_id, load_fallbacks=enable_fallback)
            if not self.api_keys:
                raise ValueError(f"No valid API keys found for ID {api_key_id}")
            # Use first key (primary)
            self.api_key = self.api_keys[0][2]
            if enable_fallback:
                logger.info(f"OpenAI client initialized with API key ID {api_key_id} ({len(self.api_keys)} keys available including fallbacks)")
            else:
                logger.info(f"OpenAI client initialized with API key ID {api_key_id} (fallback DISABLED - only this key will be used)")
        else:
            # Legacy mode: single API key
            self.api_key = api_key or os.getenv('OPENAI_API_KEY')
            if not self.api_key:
                raise ValueError("OpenAI API key not found. Set OPENAI_API_KEY environment variable.")
            logger.info("OpenAI client initialized (single key mode)")

        self.client = OpenAI(api_key=self.api_key)

    def _load_api_keys_from_db(self, primary_key_id: int, load_fallbacks: bool = True):
        """
        Load API keys with fallback support from database.

        Args:
            primary_key_id: Primary API key ID to use (will be first in list)
            load_fallbacks: If False, only load the primary key (no fallback keys)
        """
        try:
            from .postgres_db import PostgreSQLURLDatabase
            from .encryption import get_encryption_manager

            database_url = os.getenv("DATABASE_URL")
            if not database_url:
                logger.error("DATABASE_URL not set, cannot load API keys from database")
                return

            db = PostgreSQLURLDatabase(database_url)
            encryption_manager = get_encryption_manager()

            # Get primary key to determine user_id
            primary_key = db.get_api_key_by_id(primary_key_id)
            if not primary_key:
                logger.error(f"Primary API key ID {primary_key_id} not found")
                return

            # Use the same user_id as the primary key for fallback keys
            user_id = primary_key.get('user_id')

            if load_fallbacks:
                # Get API keys in priority order (primary first, then fallbacks from same user)
                api_keys_data = db.get_api_keys_with_fallback(
                    primary_api_key_id=primary_key_id,
                    user_id=user_id  # Load keys from same user (None = admin keys)
                )
                logger.info(f"Loading API keys for {'admin' if user_id is None else f'user {user_id}'} with fallback enabled")
            else:
                # Only load the primary key (no fallbacks)
                api_keys_data = [primary_key] if primary_key else []
                logger.info(f"Fallback disabled: loading only primary key ID {primary_key_id}")

            # Decrypt keys and store as tuples
            for key_data in api_keys_data:
                try:
                    decrypted_key = encryption_manager.decrypt(key_data['encrypted_key'])
                    self.api_keys.append((
                        key_data['id'],
                        key_data['alias'],
                        decrypted_key
                    ))
                    logger.debug(f"Loaded API key: {key_data['alias']} (ID: {key_data['id']})")
                except Exception as e:
                    logger.error(f"Failed to decrypt API key {key_data['alias']}: {e}")

            if self.api_keys:
                logger.info(f"Loaded {len(self.api_keys)} API keys (1 primary + {len(self.api_keys)-1} fallback)")
            else:
                logger.warning(f"No API keys loaded for primary key ID {primary_key_id}")

        except Exception as e:
            logger.error(f"Error loading API keys from database: {e}")

    def _switch_to_next_key(self):
        """
        Switch to next available fallback key.

        Returns:
            True if switched successfully, False if no more keys available
        """
        if not self.api_keys or self.current_key_index >= len(self.api_keys) - 1:
            return False

        self.current_key_index += 1
        key_id, key_alias, decrypted_key = self.api_keys[self.current_key_index]

        self.api_key = decrypted_key
        self.client = OpenAI(api_key=self.api_key)

        logger.warning(f"Switched to fallback API key: {key_alias} (ID: {key_id})")
        return True

    def get_api_keys_used(self) -> List[int]:
        """
        Get list of API key IDs that were actually used during execution.

        Returns:
            List of API key IDs in order of usage (primary first, then fallbacks)
        """
        return list(self.api_keys_used)

    def call(
        self,
        prompt: str,
        system_prompt: str = "You are a helpful assistant.",
        model: str = "gpt-4o-mini",
        temperature: float = 0.3,
        max_tokens: int = 2000,
        response_format: Optional[Dict[str, str]] = None,
        stage: str = "unknown",
        operation: str = "api_call",
        run_date: Optional[str] = None
    ) -> str:
        """
        Make a call to OpenAI API with automatic fallback support.

        If the primary API key runs out of credits, automatically switches to fallback keys.

        Args:
            prompt: User prompt
            system_prompt: System prompt
            model: Model to use
            temperature: Sampling temperature
            max_tokens: Maximum tokens in response
            response_format: Optional response format (e.g., {"type": "json_object"})
            stage: Stage number for token tracking (e.g., "01")
            operation: Operation name for token tracking
            run_date: Run date for token tracking

        Returns:
            Response text from the model

        Raises:
            Exception: If all API keys (primary + fallbacks) fail
        """
        from openai import RateLimitError, AuthenticationError

        max_retries = len(self.api_keys) if self.api_keys else 1
        last_exception = None

        for attempt in range(max_retries):
            try:
                messages = [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt}
                ]

                kwargs = {
                    "model": model,
                    "messages": messages,
                    "temperature": temperature,
                    "max_tokens": max_tokens
                }

                if response_format:
                    kwargs["response_format"] = response_format

                # Log current key being used
                current_key_info = ""
                if self.api_keys:
                    key_id, key_alias, _ = self.api_keys[self.current_key_index]
                    current_key_info = f" (using key: {key_alias}, ID: {key_id})"

                logger.debug(f"Calling OpenAI API with model: {model}{current_key_info}")
                response = self.client.chat.completions.create(**kwargs)

                content = response.choices[0].message.content

                # Track token usage
                usage = response.usage
                input_tokens = usage.prompt_tokens
                output_tokens = usage.completion_tokens

                logger.debug(f"Received response ({len(content)} chars, {input_tokens} input tokens, {output_tokens} output tokens){current_key_info}")

                # Log to token tracker (with API key ID if available)
                api_key_id_for_tracking = self.api_keys[self.current_key_index][0] if self.api_keys else None
                # Propagate newsletter execution context to token tracker when available
                newsletter_execution_id = None
                env_news = os.getenv("TOKEN_TRACKER_NEWSLETTER_EXECUTION_ID")
                if env_news and env_news.isdigit():
                    newsletter_execution_id = int(env_news)
                log_tokens(
                    stage=stage,
                    model=model,
                    operation=operation,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    run_date=run_date,
                    api_key_id=api_key_id_for_tracking,
                    newsletter_execution_id=newsletter_execution_id
                )

                # Track API key usage
                if api_key_id_for_tracking:
                    self.api_keys_used.add(api_key_id_for_tracking)

                # Update API key usage stats in database
                if api_key_id_for_tracking:
                    try:
                        from .postgres_db import PostgreSQLURLDatabase
                        database_url = os.getenv("DATABASE_URL")
                        if database_url:
                            db = PostgreSQLURLDatabase(database_url)
                            db.update_api_key_usage(api_key_id_for_tracking)
                    except Exception as db_err:
                        logger.warning(f"Failed to update API key usage stats: {db_err}")

                return content

            except RateLimitError as e:
                last_exception = e
                error_str = str(e).lower()

                # Check if it's an insufficient quota error
                if "insufficient_quota" in error_str or "quota" in error_str:
                    if self.api_keys:
                        key_id, key_alias, _ = self.api_keys[self.current_key_index]
                        logger.warning(f"API key '{key_alias}' (ID: {key_id}) ran out of credits: {e}")

                        # Try to switch to next fallback key
                        if self._switch_to_next_key():
                            logger.info(f"Retrying with fallback key (attempt {attempt + 2}/{max_retries})...")
                            continue
                        else:
                            logger.error("No more fallback API keys available")
                            raise Exception(f"All API keys exhausted. Last error: {e}")
                    else:
                        logger.error(f"API key ran out of credits and no fallbacks configured: {e}")
                        raise
                else:
                    # Other rate limit error (not quota), don't retry
                    logger.error(f"Rate limit error (not quota): {e}")
                    raise

            except AuthenticationError as e:
                last_exception = e
                if self.api_keys:
                    key_id, key_alias, _ = self.api_keys[self.current_key_index]
                    logger.error(f"Authentication failed for API key '{key_alias}' (ID: {key_id}): {e}")

                    # Try next key
                    if self._switch_to_next_key():
                        logger.info(f"Retrying with next fallback key (attempt {attempt + 2}/{max_retries})...")
                        continue
                    else:
                        logger.error("No more fallback API keys available")
                        raise Exception(f"All API keys failed authentication. Last error: {e}")
                else:
                    logger.error(f"Authentication error: {e}")
                    raise

            except Exception as e:
                logger.error(f"OpenAI API call failed: {e}")
                raise

        # If we get here, all retries failed
        if last_exception:
            raise last_exception
        else:
            raise Exception("OpenAI API call failed after all retries")


def filter_news_urls(
    links: List[Dict[str, str]],
    source_name: str,
    llm_client: Optional[LLMClient] = None,
    model: Optional[str] = None,
    stage: str = "01",
    run_date: Optional[str] = None,
    batch_size: int = 50
) -> List[Dict[str, str]]:
    """
    Filter links to identify actual news articles vs navigation/ads.
    Processes links in batches for better LLM performance.

    Args:
        links: List of dicts with 'url' and 'title' keys
        source_name: Name of the source (for context)
        llm_client: LLMClient instance (creates new if None)
        model: Model to use (defaults to MODEL_URL_FILTER env var)
        stage: Stage number for token tracking
        run_date: Run date for token tracking
        batch_size: Number of links to process per LLM call (default 50)

    Returns:
        Filtered list of news article links
    """
    if not links:
        logger.warning("No links provided for filtering")
        return []

    if llm_client is None:
        llm_client = LLMClient()

    model = model or os.getenv('MODEL_URL_FILTER', 'gpt-4o-mini')

    # Load categories from YAML configuration
    import yaml
    from pathlib import Path

    categories_file = Path("config/categories.yml")
    try:
        with open(categories_file, 'r', encoding='utf-8') as f:
            categories_config = yaml.safe_load(f)

        categories = categories_config.get('categories', [])
        classification_rules = categories_config.get('classification_rules', [])

        # Build categories list for prompt with examples
        categories_text_parts = []
        for i, cat in enumerate(categories):
            cat_text = f'{i+1}. "{cat["id"]}" - {cat["description"]}'
            # Add examples if available
            if 'examples' in cat and cat['examples']:
                examples = "\n   ".join([f"• {ex}" for ex in cat['examples']])
                cat_text += f"\n   Ejemplos:\n   {examples}"
            categories_text_parts.append(cat_text)

        categories_text = "\n\n".join(categories_text_parts)

        # Build rules text
        rules_text = "\n".join([f"- {rule}" for rule in classification_rules])

    except Exception as e:
        logger.error(f"Failed to load categories from {categories_file}: {e}")
        # Fallback to default categories (new 3-category system)
        categories_text = """1. "contenido_noticia" - Artículos periodísticos que reportan HECHOS ACTUALES: noticias, reportajes, informes sobre eventos recientes.

2. "contenido_otros" - Contenido de TEXTO consumible que NO son reportes de hechos actuales: opinión, análisis, columnas, editoriales, ensayos, divulgación, filosofía, contenido atemporal o educativo.

3. "no_contenido" - Todo lo que NO es contenido consumible como texto: navegación, institucional, multimedia (videos, podcasts, galerías), servicios."""
        rules_text = """- Clasifica TODOS los enlaces, no descartes ninguno
- El criterio clave entre 'contenido_noticia' y 'contenido_otros' es: ¿reporta HECHOS ACTUALES o es OPINIÓN/ANÁLISIS?
- Videos, podcasts, galerías de fotos y contenido multimedia SIN texto sustancial van a 'no_contenido'
- Artículos "Live" o "Directo" (coberturas en vivo) van a 'no_contenido' (contenido fragmentado no procesable)
- Títulos que contengan tags HTML (<img, <div, <span, srcset=, etc.) van a 'no_contenido' (extracción defectuosa)
- URLs genéricas de sección (/economia/, /politica/) son 'no_contenido'
- Solo reportes objetivos de hechos recientes CON TEXTO SUSTANCIAL son 'contenido_noticia'"""

    system_prompt = f"""Eres un clasificador de enlaces web. Tu tarea es categorizar cada enlace según su tipo de contenido.

CRÍTICO: Prioriza el análisis de la ESTRUCTURA DE LA URL sobre el título. La URL es el indicador más confiable del tipo de contenido.

Analiza PRIMERO la URL y LUEGO el título para clasificar cada enlace en una de estas categorías:

CATEGORÍAS:
{categories_text}

IMPORTANTE:
{rules_text}

Responde ÚNICAMENTE con un JSON válido:
{{
  "classifications": [
    {{"id": 0, "category": "contenido_noticia"}},
    {{"id": 1, "category": "contenido_otros"}},
    {{"id": 2, "category": "no_contenido"}},
    ...
  ]
}}"""

    logger.info(f"Filtering {len(links)} links from {source_name} using LLM (batch_size={batch_size})")

    all_filtered_links = []

    # Process links in batches
    for batch_start in range(0, len(links), batch_size):
        batch_end = min(batch_start + batch_size, len(links))
        batch_links = links[batch_start:batch_end]

        # Prepare data for LLM with IDs relative to batch
        links_data = []
        for i, link in enumerate(batch_links):
            links_data.append({
                "id": i,
                "url": link['url'],
                "title": link['title']
            })

        user_prompt = f"""Clasifica estos enlaces extraídos de {source_name}.

IMPORTANTE: Analiza PRIMERO la estructura de la URL (patrones, paths, parámetros) y DESPUÉS el título.
- URLs con /search?, /data/, /indices/, /tearsheet/ son 'no_contenido'
- URLs de sección sin slug específico (ejemplo: /middle-east-war) son 'no_contenido'
- URLs con slugs únicos y específicos son candidatas a contenido

FILTROS CRÍTICOS DEL TÍTULO:
- Si el título contiene tags HTML como <img, <div, <span, srcset=, src=, alt=, width=, height= → clasificar como 'no_contenido'
- Si el título menciona "Vídeo", "Vidéos", "Video", "Live", "Directo", "En directo" → clasificar como 'no_contenido'
- Solo títulos de texto limpio sin HTML son válidos para 'contenido_noticia' o 'contenido_otros'

Datos a clasificar:
{json.dumps(links_data, ensure_ascii=False, indent=2)}

Responde con un JSON que incluya TODOS los enlaces clasificados:
{{
  "classifications": [
    {{"id": 0, "category": "contenido_noticia"}},
    {{"id": 1, "category": "contenido_otros"}},
    {{"id": 2, "category": "no_contenido"}},
    ...
  ]
}}"""

        try:
            logger.debug(f"Processing batch {batch_start}-{batch_end} ({len(batch_links)} links)")

            response = llm_client.call(
                prompt=user_prompt,
                system_prompt=system_prompt,
                model=model,
                temperature=0.2,
                max_tokens=2000,
                response_format={"type": "json_object"},
                stage=stage,
                operation=f"filter_urls_{source_name}_batch_{batch_start}",
                run_date=run_date
            )

            # Parse JSON response
            result = json.loads(response)
            classifications = result.get('classifications', [])

            # Add category to each link
            for classification in classifications:
                link_id = classification.get('id')
                category = classification.get('category', 'otros')

                if link_id < len(batch_links):
                    batch_links[link_id]['content_type'] = category

            # Log classification summary
            category_counts = {}
            for link in batch_links:
                cat = link.get('content_type', 'sin_clasificar')
                category_counts[cat] = category_counts.get(cat, 0) + 1

            logger.debug(f"Batch {batch_start}-{batch_end} classified: {', '.join(f'{k}={v}' for k, v in category_counts.items())}")

            # Include ALL links, not just news
            all_filtered_links.extend(batch_links)

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM JSON response for batch {batch_start}-{batch_end}: {e}")
            logger.error(f"Response was: {response}")
            # Fallback: include all links with 'sin_clasificar' category
            for link in batch_links:
                if 'content_type' not in link:
                    link['content_type'] = 'sin_clasificar'
            all_filtered_links.extend(batch_links)

        except Exception as e:
            logger.error(f"Error classifying batch {batch_start}-{batch_end}: {e}")
            # Fallback: include all links with 'sin_clasificar' category
            for link in batch_links:
                if 'content_type' not in link:
                    link['content_type'] = 'sin_clasificar'
            all_filtered_links.extend(batch_links)

    # Count by category
    final_counts = {}
    for link in all_filtered_links:
        cat = link.get('content_type', 'sin_clasificar')
        final_counts[cat] = final_counts.get(cat, 0) + 1

    logger.info(f"Classified {len(all_filtered_links)} links from {source_name}: {', '.join(f'{k}={v}' for k, v in sorted(final_counts.items()))}")

    return all_filtered_links


def classify_article(
    url: str,
    title: str,
    categories: List[str],
    llm_client: Optional[LLMClient] = None,
    model: Optional[str] = None
) -> str:
    """
    Classify an article into one of the predefined categories.

    Args:
        url: Article URL
        title: Article title
        categories: List of valid categories
        llm_client: LLMClient instance (creates new if None)
        model: Model to use (defaults to MODEL_CLASSIFIER env var)

    Returns:
        Category name
    """
    if llm_client is None:
        llm_client = LLMClient()

    model = model or os.getenv('MODEL_CLASSIFIER', 'gpt-4o-mini')

    system_prompt = """Eres un clasificador de artículos de noticias. Dada una lista cerrada de categorías, asigna exactamente UNA categoría que mejor represente el tema del artículo.

Responde ÚNICAMENTE con un JSON válido en el formato: {"categoria": "nombre_categoria"}"""

    user_prompt = f"""Clasifica este artículo en una de estas categorías:

Categorías disponibles: {', '.join(categories)}

Artículo:
- Título: {title}
- URL: {url}

Responde con un JSON en este formato exacto:
{{
  "categoria": "nombre_categoria"
}}"""

    try:
        response = llm_client.call(
            prompt=user_prompt,
            system_prompt=system_prompt,
            model=model,
            temperature=0.2,
            max_tokens=100,
            response_format={"type": "json_object"}
        )

        result = json.loads(response)
        categoria = result.get('categoria', categories[0])

        # Validate category is in allowed list
        if categoria not in categories:
            logger.warning(f"LLM returned invalid category '{categoria}', using first category as fallback")
            categoria = categories[0]

        return categoria

    except Exception as e:
        logger.error(f"Error classifying article: {e}")
        # Fallback to first category
        return categories[0]


def is_likely_collection_page(url: str, title: str) -> bool:
    """
    Heuristic to detect collection/archive pages (author pages, section pages, etc.)
    before making expensive LLM calls.

    Returns True if URL/title strongly suggest it's a collection page (no_contenido).

    Args:
        url: Full URL to analyze
        title: Page title extracted from link

    Returns:
        True if likely a collection page, False otherwise
    """
    import re

    # Extract path from URL
    match = re.search(r'https?://[^/]+(/[^?#]*)', url)
    if not match:
        return False

    path = match.group(1).strip('/')
    segments = [s for s in path.split('/') if s]

    # HEURISTIC 1: Very short path (1 segment) with short name (< 30 chars)
    # AND title is just 2-4 words, all title case (likely a name or section)
    if len(segments) == 1 and len(segments[0]) < 30:
        title_words = title.split()

        # Filter out empty strings
        title_words = [w for w in title_words if w]

        # Check if title is short (2-4 words) and looks like a name or section
        if 2 <= len(title_words) <= 4:
            # Check if all words start with uppercase (name-like)
            all_capitalized = all(w[0].isupper() for w in title_words if len(w) > 0)

            if all_capitalized:
                # Additional check: no common action verbs in title
                action_verbs = [
                    'announces', 'says', 'reveals', 'launches', 'unveils',
                    'reports', 'confirms', 'denies', 'claims', 'warns',
                    'announces', 'reports', 'shows', 'finds', 'discovers'
                ]
                has_verb = any(verb in title.lower() for verb in action_verbs)

                if not has_verb:
                    # Very likely an author or section page
                    logger.debug(f"Heuristic: '{url}' with title '{title}' looks like collection (short path + name-like title)")
                    return True

    # HEURISTIC 2: Common collection path patterns
    collection_patterns = [
        r'^author/[^/]+/?$',
        r'^authors/[^/]+/?$',
        r'^contributor/[^/]+/?$',
        r'^columnist/[^/]+/?$',
        r'^staff/[^/]+/?$',
        r'^writer/[^/]+/?$',
        r'^writers/[^/]+/?$',
        r'^profile/[^/]+/?$',
        r'^user/[^/]+/?$',
    ]

    for pattern in collection_patterns:
        if re.match(pattern, path, re.IGNORECASE):
            logger.debug(f"Heuristic: '{url}' matches collection pattern '{pattern}'")
            return True

    # HEURISTIC 3: Title is EXACTLY a proper name (2-3 words, title case, NO verbs)
    # AND URL path is short (1-2 segments)
    if len(segments) <= 2:
        title_words = [w for w in title.split() if w]

        if len(title_words) in [2, 3]:
            # Check if all words are capitalized (proper noun pattern)
            all_capitalized = all(w[0].isupper() for w in title_words)

            # Check for verbs
            common_verbs = [
                'is', 'are', 'was', 'were', 'has', 'have', 'will',
                'announces', 'says', 'reveals', 'launches', 'reports',
                'how', 'why', 'what', 'when', 'where'  # Question words often in article titles
            ]
            has_verb_or_question = any(word.lower() in common_verbs for word in title_words)

            if all_capitalized and not has_verb_or_question:
                logger.debug(f"Heuristic: '{url}' with title '{title}' looks like name/section (proper nouns, no verbs)")
                return True

    return False


def filter_content_urls(
    links: List[Dict[str, str]],
    source_name: str,
    llm_client: Optional[LLMClient] = None,
    model: Optional[str] = None,
    stage: str = "01",
    run_date: Optional[str] = None,
    batch_size: int = 50
) -> List[Dict[str, str]]:
    """
    Filter links to identify content vs non-content (LEVEL 1 classification).
    Processes links in batches for better LLM performance.

    This function only classifies content_type: 'contenido' or 'no_contenido'.
    It does NOT classify content_subtype (noticia vs otros).

    Args:
        links: List of dicts with 'url' and 'title' keys
        source_name: Name of the source (for context)
        llm_client: LLMClient instance (creates new if None)
        model: Model to use (defaults to MODEL_URL_FILTER env var)
        stage: Stage number for token tracking
        run_date: Run date for token tracking
        batch_size: Number of links to process per LLM call (default 50)

    Returns:
        List of links with 'content_type' field added
    """
    if not links:
        logger.warning("No links provided for filtering")
        return []

    if llm_client is None:
        llm_client = LLMClient()

    model = model or os.getenv('MODEL_URL_FILTER', 'gpt-4o-mini')

    # Load content_types from YAML configuration
    import yaml
    from pathlib import Path

    categories_file = Path("config/categories.yml")
    try:
        with open(categories_file, 'r', encoding='utf-8') as f:
            categories_config = yaml.safe_load(f)

        content_types = categories_config.get('content_types', [])
        classification_rules = categories_config.get('classification_rules', {}).get('level1_rules', [])

        # Build content_types list for prompt
        types_text_parts = []
        for i, ct in enumerate(content_types):
            ct_text = f'{i+1}. "{ct["id"]}" - {ct["description"]}'
            # Add examples if available
            if 'examples' in ct and ct['examples']:
                examples = "\n   ".join([f"• {ex}" for ex in ct['examples']])
                ct_text += f"\n   Ejemplos:\n   {examples}"
            types_text_parts.append(ct_text)

        types_text = "\n\n".join(types_text_parts)

        # Build rules text
        rules_text = "\n".join([f"- {rule}" for rule in classification_rules])

    except Exception as e:
        logger.error(f"Failed to load categories from {categories_file}: {e}")
        # Fallback to default
        types_text = """1. "contenido" - Contenido de texto consumible (artículos, noticias, opinión, análisis).

2. "no_contenido" - No es contenido consumible (navegación, institucional, multimedia, servicios)."""
        rules_text = """- PRIORIZA el análisis de la ESTRUCTURA DE LA URL
- URLs con /search?, /filter?, /login → no_contenido
- URLs CORTAS Y GENÉRICAS → no_contenido
- URLs con identificadores únicos → contenido"""

    system_prompt = f"""Eres un clasificador de enlaces web. Tu tarea es determinar si cada URL apunta a CONTENIDO CONSUMIBLE o NO.

NIVEL 1 - Tipos de contenido:
{types_text}

REGLAS DE CLASIFICACIÓN:

1. PÁGINAS DE COLECCIÓN (SIEMPRE 'no_contenido'):
   - Archivos de autor/columnista (ej: /pilita-clark, /john-smith)
   - Páginas de sección/categoría (ej: /technology, /opinion, /world)
   - Índices de blog/columna (ej: /lex, /alphaville, /unhedged)
   - Páginas de staff/colaboradores

   Señales clave de COLECCIÓN:
   * URL CORTA (1-2 segmentos) SIN identificador único
   * Título es SOLO un nombre propio o categoría (2-4 palabras, sin verbo ni contexto)
   * La URL parece "contenedor" que agruparía múltiples artículos

2. CONTENIDO INDIVIDUAL ('contenido'):
   - Tiene identificador ÚNICO en URL:
     * UUID (ej: /content/abc-123-def-456)
     * Fecha + slug (ej: /2025/11/09/article-title)
     * ID numérico (ej: /articles/12345)
     * Slug LARGO >40 caracteres específico
   - Título es descriptivo y específico (>5 palabras O contiene verbos/acciones)

3. PRUEBA DE MULTIPLICIDAD (úsala en casos ambiguos):
   Pregúntate: "¿Esta URL podría mostrar una LISTA de múltiples artículos de diferentes fechas?"
   - SI → 'no_contenido' (es página de colección/archivo)
   - NO → 'contenido' (es artículo individual)

   Ejemplos:
   - /pilita-clark con título "Pilita Clark" → podría listar artículos de esta autora → no_contenido
   - /content/abc-123 con título "New policy..." → NO puede listar múltiples → contenido

REGLAS TÉCNICAS:
{rules_text}

Responde ÚNICAMENTE con un JSON válido:
{{
  "classifications": [
    {{"id": 0, "content_type": "contenido"}},
    {{"id": 1, "content_type": "no_contenido"}},
    ...
  ]
}}"""

    logger.info(f"Filtering {len(links)} links from {source_name} using LLM (batch_size={batch_size})")

    # Pre-filter obvious collection pages using heuristics
    pre_filtered_collections = []
    needs_llm_classification = []

    for link in links:
        if is_likely_collection_page(link['url'], link['title']):
            # Mark as no_contenido without calling LLM
            link['content_type'] = 'no_contenido'
            link['content_subtype'] = None
            link['classification_method'] = 'heuristic'
            pre_filtered_collections.append(link)
        else:
            # Needs LLM classification
            needs_llm_classification.append(link)

    logger.info(f"Pre-filtered {len(pre_filtered_collections)} likely collection pages using heuristics, "
                f"{len(needs_llm_classification)} links need LLM classification")

    all_filtered_links = []

    # Add pre-filtered collection pages to results
    all_filtered_links.extend(pre_filtered_collections)

    # Process remaining links in batches with LLM
    for batch_start in range(0, len(needs_llm_classification), batch_size):
        batch_end = min(batch_start + batch_size, len(needs_llm_classification))
        batch_links = needs_llm_classification[batch_start:batch_end]

        # Prepare data for LLM with IDs relative to batch
        links_data = []
        for i, link in enumerate(batch_links):
            links_data.append({
                "id": i,
                "url": link['url'],
                "title": link['title']
            })

        user_prompt = f"""Clasifica estos enlaces extraídos de {source_name}.

NIVEL 1: Determina si cada URL apunta a CONTENIDO CONSUMIBLE o NO.

APLICA LA PRUEBA DE MULTIPLICIDAD a URLs ambiguas:
- ¿La URL podría mostrar MÚLTIPLES artículos de diferentes fechas?
  → SI = 'no_contenido' (colección)
  → NO = 'contenido' (artículo individual)

PATRONES ESPECÍFICOS A DETECTAR:

🚫 NO_CONTENIDO (páginas de colección):
- Nombres propios solos sin contexto: /pilita-clark, /john-smith, /jane-doe
  → Título: "Pilita Clark" (solo nombre) → Archivo de autor
- Secciones/categorías: /technology, /world, /business, /opinion
  → Título: "Technology" o "Technology News" → Índice de sección
- Blogs/columnas sin artículo: /lex, /alphaville, /unhedged
  → Título: "Unhedged" (nombre de columna) → Página de columna
- Herramientas/búsqueda: /search, /data, /tools, /login

✅ CONTENIDO (artículos individuales):
- Con UUID: /content/41b15d39-401d-4059-bdd2-60c19c6b2c83
  → Identificador único → Artículo específico
- Con fecha: /2025/11/09/government-announces-new-policy
  → Fecha + slug → Noticia del día
- Con ID numérico: /articles/12345
- Slugs largos específicos: /this-is-a-detailed-article-about-specific-topic
  → >40 caracteres, descriptivo → Artículo

CLAVE: Si título es SOLO 2-3 palabras Y URL es corta (1-2 segmentos) Y no hay identificador único
→ Muy probablemente es COLECCIÓN, no contenido

Datos a clasificar:
{json.dumps(links_data, ensure_ascii=False, indent=2)}

Responde con un JSON que incluya TODOS los enlaces clasificados:
{{
  "classifications": [
    {{"id": 0, "content_type": "contenido"}},
    {{"id": 1, "content_type": "no_contenido"}},
    ...
  ]
}}"""

        try:
            logger.debug(f"Processing batch {batch_start}-{batch_end} ({len(batch_links)} links)")

            response = llm_client.call(
                prompt=user_prompt,
                system_prompt=system_prompt,
                model=model,
                temperature=0.2,
                max_tokens=2000,
                response_format={"type": "json_object"},
                stage=stage,
                operation=f"filter_content_{source_name}_batch_{batch_start}",
                run_date=run_date
            )

            # Parse JSON response
            result = json.loads(response)
            classifications = result.get('classifications', [])

            # Add content_type to each link
            for classification in classifications:
                link_id = classification.get('id')
                content_type = classification.get('content_type', 'no_contenido')

                if link_id < len(batch_links):
                    batch_links[link_id]['content_type'] = content_type
                    batch_links[link_id]['content_subtype'] = None  # Will be set later if needed

            # Log classification summary
            type_counts = {}
            for link in batch_links:
                ct = link.get('content_type', 'sin_clasificar')
                type_counts[ct] = type_counts.get(ct, 0) + 1

            logger.debug(f"Batch {batch_start}-{batch_end} classified: {', '.join(f'{k}={v}' for k, v in type_counts.items())}")

            # Include ALL links
            all_filtered_links.extend(batch_links)

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM JSON response for batch {batch_start}-{batch_end}: {e}")
            logger.error(f"Response was: {response}")
            # Fallback: include all links with 'sin_clasificar'
            for link in batch_links:
                if 'content_type' not in link:
                    link['content_type'] = 'sin_clasificar'
                    link['content_subtype'] = None
            all_filtered_links.extend(batch_links)

        except Exception as e:
            logger.error(f"Error classifying batch {batch_start}-{batch_end}: {e}")
            # Fallback: include all links with 'sin_clasificar'
            for link in batch_links:
                if 'content_type' not in link:
                    link['content_type'] = 'sin_clasificar'
                    link['content_subtype'] = None
            all_filtered_links.extend(batch_links)

    # Count by type
    final_counts = {}
    for link in all_filtered_links:
        ct = link.get('content_type', 'sin_clasificar')
        final_counts[ct] = final_counts.get(ct, 0) + 1

    logger.info(f"Classified {len(all_filtered_links)} links from {source_name}: {', '.join(f'{k}={v}' for k, v in sorted(final_counts.items()))}")

    return all_filtered_links


def classify_thematic_categories_batch(
    urls: List[Dict[str, Any]],
    categories: List[Dict[str, Any]],
    llm_client: Optional[LLMClient] = None,
    model: Optional[str] = None,
    stage: str = "02",
    run_date: Optional[str] = None,
    batch_size: int = 30
) -> List[Dict[str, Any]]:
    """
    Classify URLs into thematic categories for newsletter filtering (Stage 02).

    Uses URL and title to determine the most appropriate thematic category
    (política, economía, tecnología, etc.)

    Args:
        urls: List of dicts with 'id', 'url', 'title' keys
        categories: List of category dicts with 'id', 'name', 'description', 'examples'
        llm_client: LLMClient instance (creates new if None)
        model: Model to use (defaults to MODEL_CLASSIFIER env var)
        stage: Stage number for token tracking
        run_date: Run date for token tracking
        batch_size: Number of URLs to process per LLM call (default 30)

    Returns:
        List of dicts with added 'categoria_tematica' field
    """
    if not urls:
        logger.warning("No URLs provided for thematic classification")
        return []

    if llm_client is None:
        llm_client = LLMClient()

    model = model or os.getenv('MODEL_CLASSIFIER', 'gpt-4o-mini')

    # Build categories text with definitions
    category_ids = [cat['id'] for cat in categories]
    categories_list = ', '.join(f'"{cat_id}"' for cat_id in category_ids)

    # Build detailed category descriptions
    categories_detail = []
    for cat in categories:
        cat_text = f"  • {cat['id']} ({cat['name']}): {cat['description']}"
        if cat.get('examples'):
            examples = cat['examples'][:3]  # Limit to 3 examples
            cat_text += f"\n    Ejemplos: {'; '.join(examples)}"
        categories_detail.append(cat_text)

    categories_description = '\n'.join(categories_detail)

    system_prompt = f"""Eres un clasificador de contenido periodístico. Tu tarea es asignar EXACTAMENTE UNA categoría temática a cada artículo.

CATEGORÍAS DISPONIBLES:

{categories_description}

INSTRUCCIONES:
- Analiza el URL y el título para determinar el tema principal
- Asigna la categoría que MEJOR represente el contenido
- Lee atentamente la DESCRIPCIÓN de cada categoría
- Fíjate en los EJEMPLOS proporcionados para entender el alcance de cada categoría
- Si hay múltiples categorías posibles, elige la que MEJOR se ajuste al enfoque principal del artículo
- IMPORTANTE:
  * "sociedad" incluye: lifestyle, moda, cultura, entretenimiento, celebrities, opinión
  * "politica" incluye: gobierno, partidos, justicia, educación
  * "economia" incluye: finanzas, empresas, mercados, energía
  * "tecnologia" incluye: innovación, ciencia, salud
  * "geopolitica" incluye: relaciones internacionales, diplomacia, crisis humanitarias globales, acuerdos internacionales
  * "otros" es para contenido inclasificable

Responde ÚNICAMENTE con un JSON válido:
{{
  "classifications": [
    {{"id": 0, "categoria_tematica": "politica"}},
    {{"id": 1, "categoria_tematica": "sociedad"}},
    ...
  ]
}}"""

    logger.info(f"Classifying {len(urls)} URLs into thematic categories (batch_size={batch_size})")

    all_classified_urls = []

    # Process URLs in batches
    for batch_start in range(0, len(urls), batch_size):
        batch_end = min(batch_start + batch_size, len(urls))
        batch_urls = urls[batch_start:batch_end]

        # Prepare data for LLM
        urls_data = []
        for i, url_data in enumerate(batch_urls):
            urls_data.append({
                "id": i,
                "url": url_data['url'],
                "title": url_data.get('title', '')
            })

        user_prompt = f"""Clasifica estos artículos en categorías temáticas.

CATEGORÍAS DISPONIBLES: {categories_list}

Datos a clasificar:
{json.dumps(urls_data, ensure_ascii=False, indent=2)}

Responde con un JSON que incluya TODOS los artículos clasificados:
{{
  "classifications": [
    {{"id": 0, "categoria_tematica": "nombre_categoria"}},
    {{"id": 1, "categoria_tematica": "nombre_categoria"}},
    ...
  ]
}}"""

        try:
            logger.debug(f"Processing batch {batch_start}-{batch_end} ({len(batch_urls)} URLs)")

            response = llm_client.call(
                prompt=user_prompt,
                system_prompt=system_prompt,
                model=model,
                temperature=0.2,
                max_tokens=1500,
                response_format={"type": "json_object"},
                stage=stage,
                operation=f"classify_thematic_batch_{batch_start}",
                run_date=run_date
            )

            # Parse JSON response
            result = json.loads(response)
            classifications = result.get('classifications', [])

            # Add categoria_tematica to each URL
            for classification in classifications:
                url_id = classification.get('id')
                categoria = classification.get('categoria_tematica', category_ids[0])

                # Validate category
                if categoria not in category_ids:
                    logger.warning(f"LLM returned invalid category '{categoria}', using first category as fallback")
                    categoria = category_ids[0]

                if url_id < len(batch_urls):
                    batch_urls[url_id]['categoria_tematica'] = categoria

            # Log classification summary
            category_counts = {}
            for url_data in batch_urls:
                cat = url_data.get('categoria_tematica', 'sin_clasificar')
                category_counts[cat] = category_counts.get(cat, 0) + 1

            logger.debug(f"Batch {batch_start}-{batch_end} classified: {', '.join(f'{k}={v}' for k, v in category_counts.items())}")

            all_classified_urls.extend(batch_urls)

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM JSON response for batch {batch_start}-{batch_end}: {e}")
            logger.error(f"Response was: {response}")
            # Fallback: use first category
            for url_data in batch_urls:
                if 'categoria_tematica' not in url_data:
                    url_data['categoria_tematica'] = category_ids[0]
            all_classified_urls.extend(batch_urls)

        except Exception as e:
            logger.error(f"Error classifying batch {batch_start}-{batch_end}: {e}")
            # Fallback: use first category
            for url_data in batch_urls:
                if 'categoria_tematica' not in url_data:
                    url_data['categoria_tematica'] = category_ids[0]
            all_classified_urls.extend(batch_urls)

    # Count by category
    final_counts = {}
    for url_data in all_classified_urls:
        cat = url_data.get('categoria_tematica', 'sin_clasificar')
        final_counts[cat] = final_counts.get(cat, 0) + 1

    logger.info(f"Thematic classification complete: {len(all_classified_urls)} URLs classified: "
               f"{', '.join(f'{k}={v}' for k, v in sorted(final_counts.items()))}")

    return all_classified_urls


def classify_content_temporality_batch(
    urls: List[Dict[str, Any]],
    llm_client: Optional[LLMClient] = None,
    model: Optional[str] = None,
    stage: str = "02",
    run_date: Optional[str] = None,
    batch_size: int = 30
) -> List[Dict[str, Any]]:
    """
    Classify URLs by content temporality (temporal vs atemporal) for Stage 02.

    Temporal: Time-sensitive content (news, events, announcements)
    Atemporal: Timeless content (essays, reflections, analysis, evergreen)

    Args:
        urls: List of dicts with 'id', 'url', 'title' keys
        llm_client: LLMClient instance (creates new if None)
        model: Model to use (defaults to MODEL_CLASSIFIER env var)
        stage: Stage number for token tracking
        run_date: Run date for token tracking
        batch_size: Number of URLs to process per LLM call (default 30)

    Returns:
        List of dicts with added/updated 'content_subtype' field ('temporal' or 'atemporal')
    """
    if not urls:
        logger.warning("No URLs provided for temporality classification")
        return []

    if llm_client is None:
        llm_client = LLMClient()

    model = model or os.getenv('MODEL_CLASSIFIER', 'gpt-4o-mini')

    system_prompt = """Eres un clasificador de contenido. Tu tarea es determinar la TEMPORALIDAD del contenido.

CATEGORÍAS DE TEMPORALIDAD:

1. "temporal" - Contenido SENSIBLE AL TIEMPO, pierde relevancia rápidamente:
   - Noticias de eventos actuales
   - Anuncios y declaraciones
   - Reportes de sucesos específicos
   - Actualizaciones de situaciones en desarrollo
   - Cualquier cosa donde la FECHA es crucial para entender el contenido

   Ejemplos:
   • "Gobierno anuncia nuevas medidas económicas"
   • "Empresa X reporta ganancias del Q3"
   • "Manifestaciones en la capital terminan pacíficamente"

2. "atemporal" - Contenido INTEMPORAL, relevante independiente de cuándo se lee:
   - Ensayos y reflexiones
   - Análisis de largo plazo
   - Contenido educativo o divulgativo
   - Opiniones filosóficas o culturales
   - Guías y how-to
   - Cualquier cosa que podría publicarse hoy o hace 6 meses sin cambiar

   Ejemplos:
   • "Por qué la democracia necesita una prensa libre"
   • "Cómo entender la economía moderna"
   • "Reflexiones sobre el futuro del trabajo"

CLAVE: Pregúntate "¿Este contenido pierde relevancia si lo leo en 1-2 semanas?"
- SI → temporal
- NO → atemporal

Responde ÚNICAMENTE con un JSON válido:
{
  "classifications": [
    {"id": 0, "content_subtype": "temporal"},
    {"id": 1, "content_subtype": "atemporal"},
    ...
  ]
}"""

    logger.info(f"Classifying temporality for {len(urls)} URLs (batch_size={batch_size})")

    all_classified_urls = []

    # Process URLs in batches
    for batch_start in range(0, len(urls), batch_size):
        batch_end = min(batch_start + batch_size, len(urls))
        batch_urls = urls[batch_start:batch_end]

        # Prepare data for LLM
        urls_data = []
        for i, url_data in enumerate(batch_urls):
            urls_data.append({
                "id": i,
                "url": url_data['url'],
                "title": url_data.get('title', '')
            })

        user_prompt = f"""Clasifica la TEMPORALIDAD de estos contenidos.

¿Es contenido TEMPORAL (sensible al tiempo) o ATEMPORAL (intemporal)?

Datos a clasificar:
{json.dumps(urls_data, ensure_ascii=False, indent=2)}

Responde con un JSON que incluya TODOS los contenidos clasificados:
{{
  "classifications": [
    {{"id": 0, "content_subtype": "temporal"}},
    {{"id": 1, "content_subtype": "atemporal"}},
    ...
  ]
}}"""

        try:
            logger.debug(f"Processing batch {batch_start}-{batch_end} ({len(batch_urls)} URLs)")

            response = llm_client.call(
                prompt=user_prompt,
                system_prompt=system_prompt,
                model=model,
                temperature=0.2,
                max_tokens=1500,
                response_format={"type": "json_object"},
                stage=stage,
                operation=f"classify_temporality_batch_{batch_start}",
                run_date=run_date
            )

            # Parse JSON response
            result = json.loads(response)
            classifications = result.get('classifications', [])

            # Add content_subtype to each URL
            for classification in classifications:
                url_id = classification.get('id')
                content_subtype = classification.get('content_subtype', 'temporal')

                # Validate
                if content_subtype not in ['temporal', 'atemporal']:
                    logger.warning(f"LLM returned invalid subtype '{content_subtype}', using 'temporal' as fallback")
                    content_subtype = 'temporal'

                if url_id < len(batch_urls):
                    batch_urls[url_id]['content_subtype'] = content_subtype

            # Log classification summary
            subtype_counts = {}
            for url_data in batch_urls:
                st = url_data.get('content_subtype', 'sin_clasificar')
                subtype_counts[st] = subtype_counts.get(st, 0) + 1

            logger.debug(f"Batch {batch_start}-{batch_end} classified: {', '.join(f'{k}={v}' for k, v in subtype_counts.items())}")

            all_classified_urls.extend(batch_urls)

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM JSON response for batch {batch_start}-{batch_end}: {e}")
            logger.error(f"Response was: {response}")
            # Fallback: use 'temporal'
            for url_data in batch_urls:
                if 'content_subtype' not in url_data:
                    url_data['content_subtype'] = 'temporal'
            all_classified_urls.extend(batch_urls)

        except Exception as e:
            logger.error(f"Error classifying batch {batch_start}-{batch_end}: {e}")
            # Fallback: use 'temporal'
            for url_data in batch_urls:
                if 'content_subtype' not in url_data:
                    url_data['content_subtype'] = 'temporal'
            all_classified_urls.extend(batch_urls)

    # Count by subtype
    final_counts = {}
    for url_data in all_classified_urls:
        st = url_data.get('content_subtype', 'sin_clasificar')
        final_counts[st] = final_counts.get(st, 0) + 1

    logger.info(f"Temporality classification complete: {len(all_classified_urls)} URLs classified: "
               f"{', '.join(f'{k}={v}' for k, v in sorted(final_counts.items()))}")

    return all_classified_urls


def validate_content_completeness(
    content: str,
    title: str,
    url: str,
    llm_client: LLMClient,
    model: str = None,
    stage: str = "04",
    run_date: Optional[str] = None
) -> Dict[str, Any]:
    """
    IMPROVED: Robust content completeness validator with heuristics + LLM.

    Strategy:
    1. Use heuristics first for quick decisions (saves tokens)
    2. Only use LLM for borderline cases (200-400 words)
    3. Structured JSON responses (no verbose reasons)
    4. More lenient thresholds to avoid false negatives

    Args:
        content: Extracted text content
        title: Article title (for context)
        url: Article URL (for logging)
        llm_client: LLM client instance
        model: Model to use (defaults to MODEL_COMPLETENESS_VALIDATOR from env)
        stage: Stage number for token tracking
        run_date: Run date for token tracking

    Returns:
        Dict with keys:
            - is_complete (bool): True if content appears complete
            - confidence (int): 0-100 confidence score
            - reason (str): Brief explanation (for logging)
            - truncation_signals (list): List of detected truncation indicators
    """
    if model is None:
        model = os.getenv('MODEL_COMPLETENESS_VALIDATOR', 'gpt-4o-mini')

    word_count = len(content.split())

    # HEURISTIC 1: Very short content (< 150 words) is likely incomplete
    if word_count < 150:
        return {
            'is_complete': False,
            'confidence': 90,
            'reason': f'Too short ({word_count} words < 150 minimum)',
            'truncation_signals': ['word_count_too_low']
        }

    # HEURISTIC 2: Long content (>= 300 words) is very likely complete
    # Skip expensive LLM call
    if word_count >= 300:
        # Quick paywall check
        content_lower = content.lower()
        paywall_keywords = [
            'suscríbete para seguir leyendo',
            'subscribe to continue',
            'continue reading',
            'para seguir leyendo',
            'regístrate para leer',
            'sign up to read more'
        ]

        has_paywall = any(keyword in content_lower for keyword in paywall_keywords)

        if has_paywall:
            return {
                'is_complete': False,
                'confidence': 85,
                'reason': 'Paywall detected in content',
                'truncation_signals': ['paywall_prompt']
            }

        # No paywall + good length = complete
        return {
            'is_complete': True,
            'confidence': 95,
            'reason': f'Good length ({word_count} words) and no paywall detected',
            'truncation_signals': []
        }

    # HEURISTIC 3: For 150-299 words, use LLM validation but with optimized prompt
    try:
        # Only send last 600 chars for analysis (saves tokens)
        content_end = content[-600:] if len(content) > 600 else content

        # Get first 200 chars for context
        content_start = content[:200]

        system_prompt = """Valida si un artículo está completo analizando su final."""

        # Optimized prompt - focuses on ending, no verbose explanations
        user_prompt = f"""Analiza si este artículo ({word_count} palabras) está COMPLETO o TRUNCADO.

TÍTULO: {title}

INICIO (primeros 200 chars):
{content_start}

FINAL (últimos 600 chars):
{content_end}

REGLAS:
✓ COMPLETO si:
- Termina con punto final y frase completa
- Tiene cierre natural (conclusión/despedida)
- NO hay frases como "continúa leyendo", "suscríbete"

✗ TRUNCADO si:
- Termina abruptamente o con "..."
- Solo es introducción/lead
- Tiene prompts de paywall

RESPONDE JSON (SIN razones extensas):
{{
  "is_complete": true/false,
  "confidence": 0-100
}}"""

        response = llm_client.call(
            prompt=user_prompt,
            system_prompt=system_prompt,
            model=model,
            temperature=0.1,
            max_tokens=50,  # Reduced from 300
            response_format={"type": "json_object"},
            stage=stage,
            operation="validate_completeness",
            run_date=run_date
        )

        result = json.loads(response)

        is_complete = result.get('is_complete', False)
        confidence = result.get('confidence', 50)

        logger.debug(f"LLM validation: is_complete={is_complete}, confidence={confidence}% ({word_count} words)")

        return {
            'is_complete': is_complete,
            'confidence': confidence,
            'reason': f'LLM validated ({word_count} words)',
            'truncation_signals': [] if is_complete else ['llm_detected_truncation']
        }

    except json.JSONDecodeError as e:
        logger.error(f"Completeness validation: Invalid JSON response: {e}")
        # Fallback: assume complete if JSON parsing fails and word_count >= 200
        return {
            'is_complete': word_count >= 200,
            'confidence': 50,
            'reason': 'JSON parsing error, assuming complete',
            'truncation_signals': []
        }

    except Exception as e:
        logger.error(f"Completeness validation failed: {e}")
        # Fallback: assume complete if validation fails
        return {
            'is_complete': True,
            'confidence': 50,
            'reason': f'Validation error: {str(e)}',
            'truncation_signals': []
        }
