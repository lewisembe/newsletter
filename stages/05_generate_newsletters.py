#!/usr/bin/env python3
"""
Stage 05: Generate Newsletters - AI-Powered News Digest Creation

This script generates newsletter content in a narrative prose style, acting as a "radio host"
who reads all the news and distills it into an engaging, coherent narrative.

The LLM receives:
- Headlines from all ranked articles
- Full content from top N most important articles
- Context about categories and related articles

The LLM generates:
- A narrative newsletter in prose format (like a radio news briefing)
- Editorial introduction with overview and context
- Connected storytelling that weaves articles together
- Final output in Markdown/HTML for email/Telegram distribution

Key Features:
- Template-based prompt system for different newsletter styles
- Configurable number of articles with full content
- Full article content sent to LLM (leveraging large context windows)
- Multiple output formats (Markdown, HTML)
- Database tracking and logging

Author: Newsletter Utils Team
Created: 2025-11-13
"""

import os
import sys
import json
import argparse
import logging
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from pathlib import Path
from typing import List, Dict, Any, Optional
from urllib.parse import urlparse

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
from jinja2 import Environment, FileSystemLoader, select_autoescape
from common.postgres_db import PostgreSQLURLDatabase
from common.llm import LLMClient
from common.logging_utils import setup_rotating_file_logger

# Load environment variables
load_dotenv()

# Configuration
MODEL_WRITER = os.getenv('MODEL_WRITER', 'gpt-4o-mini')
STAGE05_MAX_SUMMARY_LENGTH = int(os.getenv('STAGE05_MAX_SUMMARY_LENGTH', '150'))  # Reserved for future use
STAGE05_TOP_WITH_CONTENT = int(os.getenv('STAGE05_TOP_WITH_CONTENT', '10'))
# STAGE05_MAX_CONTENT_TOKENS removed - now sending full article content without truncation

# Setup logging
logger = logging.getLogger(__name__)


def setup_logging(run_date: str, verbose: bool = False) -> str:
    """
    Setup logging for Stage 05.

    Args:
        run_date: Date string for log directory
        verbose: Enable verbose logging

    Returns:
        Path to log file
    """
    log_file = setup_rotating_file_logger(
        run_date,
        "05_generate_newsletters.log",
        log_level=logging.INFO,
        verbose=verbose,
    )

    logger.info(f"Stage 05 logging initialized: {log_file}")
    return str(log_file)


def load_prompt_template(template_name: str) -> Dict[str, str]:
    """
    Load prompt template from templates directory.

    Args:
        template_name: Name of template (e.g., 'default', 'tech_focus', 'minimal')

    Returns:
        Dictionary with 'system_prompt' and 'user_prompt_template' keys
    """
    templates_dir = Path("templates") / "prompts"
    template_file = templates_dir / f"{template_name}.json"

    if not template_file.exists():
        logger.warning(f"Template {template_name} not found, using default")
        template_file = templates_dir / "default.json"

    if not template_file.exists():
        logger.error(f"Default template not found at {template_file}")
        raise FileNotFoundError(f"No prompt templates found in {templates_dir}")

    with open(template_file, 'r', encoding='utf-8') as f:
        return json.load(f)


def truncate_content(content: str, max_tokens: int = 1000) -> str:
    """
    Truncate article content to fit token budget.

    Uses a simple heuristic: ~4 characters = 1 token.
    Takes beginning and end of article (most important info usually there).

    Args:
        content: Full article content
        max_tokens: Maximum tokens to include

    Returns:
        Truncated content
    """
    if not content:
        return ""

    max_chars = max_tokens * 4

    if len(content) <= max_chars:
        return content

    # Take 70% from beginning, 30% from end
    beginning_chars = int(max_chars * 0.7)
    ending_chars = max_chars - beginning_chars

    beginning = content[:beginning_chars]
    ending = content[-ending_chars:]

    return f"{beginning}\n\n[... contenido truncado ...]\n\n{ending}"


def fetch_article_data(db: PostgreSQLURLDatabase, url_ids: List[int], top_n_with_content: int) -> List[Dict[str, Any]]:
    """
    Fetch article data from database for newsletter generation.

    IMPORTANT: This function now searches through ALL ranked URLs to find
    the first N articles with successfully extracted content, rather than
    only checking the first N positions. This ensures we utilize all
    successfully extracted content from Stage 04's replacement strategy.

    Args:
        db: Database instance
        url_ids: List of URL IDs from ranked JSON (ordered by rank)
        top_n_with_content: Number of articles with full content to include

    Returns:
        List of article dictionaries with metadata and content
    """
    articles = []
    articles_with_content_count = 0

    for idx, url_id in enumerate(url_ids):
        url_data = db.get_url_by_id(url_id)

        if not url_data:
            logger.warning(f"URL ID {url_id} not found in database")
            continue

        article = {
            'rank': idx + 1,
            'id': url_data['id'],
            'url': url_data['url'],
            'title': url_data['title'],
            'source': urlparse(url_data['source']).netloc if url_data['source'] else 'Unknown',
            'categoria_tematica': url_data.get('categoria_tematica', 'Sin categoría'),
            'category': url_data.get('categoria_tematica', 'Sin categoría'),  # Alias for template compatibility
            'extracted_at': url_data.get('extracted_at', ''),
            'has_full_content': False,
            'full_content': None,
            'word_count': 0,
            'extraction_status': url_data.get('extraction_status', 'unknown')
        }

        # Check if this article has successfully extracted content
        if url_data.get('extraction_status') == 'success' and url_data.get('full_content'):
            # Include full content if we haven't reached our target yet
            if articles_with_content_count < top_n_with_content:
                article['has_full_content'] = True
                # Send full content without truncation (leveraging modern LLM context windows)
                article['full_content'] = url_data['full_content']
                article['word_count'] = url_data.get('word_count', 0)
                articles_with_content_count += 1
                logger.debug(
                    f"Article #{idx+1} (ID: {url_id}, rank {article['rank']}) included with full content "
                    f"({articles_with_content_count}/{top_n_with_content})"
                )

        articles.append(article)

    logger.info(
        f"Fetched {len(articles)} total articles, {articles_with_content_count} with full content "
        f"(target: {top_n_with_content})"
    )

    if articles_with_content_count < top_n_with_content:
        logger.warning(
            f"⚠️  Only found {articles_with_content_count} articles with content, "
            f"target was {top_n_with_content}. Stage 04 may have had extraction failures."
        )

    return articles


def build_llm_context(articles: List[Dict[str, Any]], ranked_data: Dict[str, Any]) -> str:
    """
    Build context string for LLM with articles data.

    Structure (optimized for LLM comprehension):
    1. First: ALL headlines (overview) - gives LLM complete panorama
    2. Then: Full content for top N articles - detailed context for most important news

    This allows LLM to:
    - See the complete news landscape first
    - Make better connections between topics
    - Avoid anchoring bias on first articles with content

    Args:
        articles: List of article dictionaries
        ranked_data: Original ranked JSON data with scores and reasons

    Returns:
        Formatted context string
    """
    context_parts = []

    # Newsletter metadata
    context_parts.append(f"FECHA: {ranked_data.get('run_date', 'Unknown')}")
    context_parts.append(f"TOTAL ARTÍCULOS: {len(articles)}")
    context_parts.append("")

    # PART 1: ALL HEADLINES FIRST (complete overview)
    context_parts.append(f"=== PANORAMA COMPLETO - TODOS LOS TITULARES ({len(articles)} artículos) ===")
    context_parts.append("")
    context_parts.append("A continuación se presenta un índice completo de todas las noticias rankeadas.")
    context_parts.append("Los artículos marcados con ✓ tienen contenido completo disponible más abajo.")
    context_parts.append("")

    for article in articles:
        marker = "✓" if article['has_full_content'] else " "
        context_parts.append(
            f"[{article['rank']}] {marker} **{article['title']}** | "
            f"URL: {article['url']} | "
            f"Fuente: {article['source']} | "
            f"Categoría: {article['categoria_tematica']}"
        )

    context_parts.append("")
    context_parts.append("=" * 80)
    context_parts.append("")

    # PART 2: FULL CONTENT FOR TOP ARTICLES (detailed context)
    articles_with_content = [a for a in articles if a['has_full_content']]
    if articles_with_content:
        context_parts.append(f"=== ARTÍCULOS PRINCIPALES CON CONTENIDO COMPLETO ({len(articles_with_content)} artículos) ===")
        context_parts.append("")
        context_parts.append("A continuación se presenta el contenido completo de los artículos más importantes:")
        context_parts.append("")

        for article in articles_with_content:
            context_parts.append(f"## [{article['rank']}] {article['title']}")
            context_parts.append(f"**URL:** {article['url']}")
            context_parts.append(f"**Fuente:** {article['source']}")
            context_parts.append(f"**Categoría:** {article['categoria_tematica']}")
            context_parts.append("")
            context_parts.append("**Contenido completo:**")
            context_parts.append(article['full_content'])
            context_parts.append("")
            context_parts.append("-" * 80)
            context_parts.append("")

    context = "\n".join(context_parts)

    # Safety check: warn if context is approaching LLM limits
    estimated_tokens = len(context) / 4  # Rough heuristic: ~4 chars = 1 token
    max_safe_tokens = int(os.getenv('STAGE05_MAX_TOTAL_CONTEXT_TOKENS', '100000'))

    if estimated_tokens > max_safe_tokens:
        logger.warning(
            f"⚠️  CONTEXT SIZE WARNING: Context is very large ({estimated_tokens:.0f} estimated tokens). "
            f"This exceeds the safety limit of {max_safe_tokens} tokens and may approach model limits. "
            f"Consider reducing STAGE05_TOP_WITH_CONTENT or using a model with larger context window."
        )
    elif estimated_tokens > (max_safe_tokens * 0.8):
        logger.warning(
            f"Context size is approaching limits ({estimated_tokens:.0f} estimated tokens, "
            f"limit: {max_safe_tokens}). Monitor for potential issues."
        )
    else:
        logger.info(f"Context size: ~{estimated_tokens:.0f} tokens (within safe limits)")

    return context


def derobotize_text(
    llm_client: LLMClient,
    narrative: str,
    run_date: str
) -> str:
    """
    Remove formulaic patterns and make text sound more human.

    Args:
        llm_client: LLM client instance
        narrative: Newsletter narrative
        run_date: Run date for token tracking

    Returns:
        Humanized narrative
    """
    logger = logging.getLogger(__name__)

    # Detect robotic patterns
    robotic_indicators = [
        "complejo tablero",
        "vasto tablero",
        "maraña de",
        "intrincado entramado",
        "este acto de",
        "en este contexto",
        "en este sentido",
        "cabe destacar",
        "es menester",
        "en el ámbito de",
        "en otro frente",
        "simultáneamente",
        "mientras tanto"
    ]

    narrative_lower = narrative.lower()
    detected_patterns = [p for p in robotic_indicators if p in narrative_lower]

    if len(detected_patterns) < 3:
        logger.info("  ✓ Text already sounds natural (few robotic patterns detected)")
        return narrative

    logger.warning(f"  ⚠️ Detected {len(detected_patterns)} robotic patterns, humanizing...")

    humanization_prompt = f"""El siguiente texto de newsletter suena demasiado formulaico y robótico.
Tu tarea es REESCRIBIRLO para que suene como una persona real explicando noticias.

TEXTO ACTUAL (ROBÓTICO):
{narrative}

PATRONES ROBÓTICOS DETECTADOS:
{', '.join(detected_patterns)}

TAREA DE HUMANIZACIÓN:

1. **Elimina frases formulaicas:**
   - "complejo tablero", "vasto tablero" → eliminar o reemplazar con lenguaje directo
   - "maraña de", "intrincado entramado" → simplificar
   - "en este contexto", "en este sentido", "cabe destacar" → eliminar conectores artificiales
   - "mientras tanto", "simultáneamente" → usar transiciones más naturales o directas

2. **Varía la estructura de frases:**
   - NO todos los párrafos deben empezar igual
   - Alterna frases cortas y largas
   - Ejemplo: "300.000 euros. Tres tuberías. Un hombre." (corto y directo)

3. **Haz que suene conversacional:**
   - Como si explicaras las noticias a un amigo inteligente en un café
   - Usa ritmo natural del habla
   - No temas ser directo cuando convenga

4. **Mantén TODO el contenido:**
   - NO elimines ninguna noticia
   - NO quites datos o contexto importante
   - SOLO cambia el estilo, no el contenido

5. **Ejemplos de transformación:**
   - ANTES: "En este contexto, Italia ha extraditado..."
   - DESPUÉS: "Italia extradita..."

   - ANTES: "Este acto de sabotaje, que exacerbó la crisis, se suma a la compleja maraña..."
   - DESPUÉS: "El sabotaje agravó la crisis energética europea."

   - ANTES: "En el ámbito militar, Ucrania enfrenta..."
   - DESPUÉS: "Ucrania enfrenta..." (directo al grano)

IMPORTANTE: Devuelve SOLO el texto humanizado (sin explicaciones).
"""

    humanized = llm_client.call(
        prompt=humanization_prompt,
        system_prompt="Eres un editor que convierte texto formulaico en prosa natural y conversacional, manteniendo todo el contenido.",
        model="gpt-4o",
        temperature=0.4,
        max_tokens=8000,
        stage="05",
        operation="derobotize",
        run_date=run_date
    )

    logger.info(f"  ✓ Text humanized ({len(detected_patterns)} patterns removed)")
    return humanized.strip()


def verify_and_complete_coverage(
    llm_client: LLMClient,
    narrative: str,
    articles: List[Dict[str, Any]],
    run_date: str
) -> str:
    """
    Verify that ALL articles are mentioned in the narrative.
    If any articles are missing, force integration using function calling.

    Args:
        llm_client: LLM client instance
        narrative: Generated newsletter narrative
        articles: Complete list of articles (must all be mentioned)
        run_date: Run date for token tracking

    Returns:
        Narrative with all articles guaranteed to be mentioned
    """
    logger = logging.getLogger(__name__)

    # Build article reference list for verification
    article_refs = []
    for i, article in enumerate(articles, 1):
        article_refs.append({
            "index": i,
            "title": article['title'],
            "url": article['url'],
            "categoria": article.get('categoria_tematica', 'N/A')
        })

    # Function calling schema
    tools = [
        {
            "type": "function",
            "function": {
                "name": "verify_article_coverage",
                "description": "Verify which articles from the list are mentioned in the narrative",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "mentioned_articles": {
                            "type": "array",
                            "description": "List of article indices that ARE mentioned in the narrative",
                            "items": {"type": "integer"}
                        },
                        "missing_articles": {
                            "type": "array",
                            "description": "List of article indices that are NOT mentioned in the narrative",
                            "items": {"type": "integer"}
                        }
                    },
                    "required": ["mentioned_articles", "missing_articles"]
                }
            }
        }
    ]

    verification_prompt = f"""Analiza la siguiente narrativa de newsletter y verifica qué artículos de la lista están mencionados.

ARTÍCULOS QUE DEBEN ESTAR MENCIONADOS:
{json.dumps(article_refs, indent=2, ensure_ascii=False)}

NARRATIVA A VERIFICAR:
{narrative}

TAREA:
Identifica qué artículos de la lista (por índice) están mencionados en la narrativa.
Un artículo se considera "mencionado" si:
- Su tema principal aparece explícitamente
- Hay referencia clara al evento/noticia
- Se puede identificar inequívocamente en el texto

USA LA FUNCIÓN para reportar mentioned_articles y missing_articles."""

    try:
        # Call OpenAI directly for function calling (not through LLMClient wrapper)
        from openai import OpenAI
        client = OpenAI()

        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "Eres un verificador que identifica qué artículos están mencionados en una narrativa."},
                {"role": "user", "content": verification_prompt}
            ],
            tools=tools,
            tool_choice={"type": "function", "function": {"name": "verify_article_coverage"}},
            temperature=0.1,
            max_tokens=500
        )

        # Parse function call response
        if response.choices[0].message.tool_calls:
            function_args = json.loads(response.choices[0].message.tool_calls[0].function.arguments)
            mentioned = set(function_args.get('mentioned_articles', []))
            missing = set(function_args.get('missing_articles', []))

            logger.info(f"  Coverage verification: {len(mentioned)}/{len(articles)} articles mentioned")

            if missing:
                logger.warning(f"  ⚠️ {len(missing)} articles missing from narrative: {sorted(missing)}")
                logger.info("  Forcing integration of missing articles...")

                # Build list of missing articles with full context
                missing_articles_data = []
                for idx in sorted(missing):
                    if 1 <= idx <= len(articles):
                        article = articles[idx - 1]
                        missing_articles_data.append({
                            "index": idx,
                            "title": article['title'],
                            "url": article['url'],
                            "categoria": article.get('categoria_tematica', 'N/A'),
                            "content_snippet": article.get('full_content', '')[:300] if article.get('has_full_content') else ""
                        })

                # Force integration
                integration_prompt = f"""Tienes una narrativa de newsletter que NO menciona TODOS los artículos requeridos.

NARRATIVA ACTUAL:
{narrative}

ARTÍCULOS QUE FALTAN (DEBES integrarlos):
{json.dumps(missing_articles_data, indent=2, ensure_ascii=False)}

TAREA CRÍTICA:
Reescribe la narrativa integrando los artículos faltantes de forma natural.
- NO cambies la estructura general
- Añade 1-3 frases por cada artículo faltante en el lugar apropiado
- Mantén la cohesión narrativa
- Usa transiciones elegantes

**PROHIBIDO:**
- NO añadas listas de URLs al final
- NO pongas los artículos faltantes como bullet points o lista separada
- CADA artículo debe estar INTEGRADO en un párrafo narrativo, no listado aparte

IMPORTANTE: Devuelve SOLO la narrativa completa (sin explicaciones ni listas al final)."""

                integrated_narrative = llm_client.call(
                    prompt=integration_prompt,
                    system_prompt="Integra artículos faltantes en una narrativa manteniendo fluidez y cohesión.",
                    model="gpt-4o",
                    temperature=0.3,
                    max_tokens=8000,
                    stage="05",
                    operation="integrate_missing",
                    run_date=run_date
                )

                logger.info(f"  ✓ Successfully integrated {len(missing)} missing articles")
                return integrated_narrative
            else:
                logger.info("  ✓ All articles are mentioned in narrative")
                return narrative

        else:
            logger.warning("  Function calling didn't return expected format, assuming all mentioned")
            return narrative

    except Exception as e:
        logger.error(f"  Error during coverage verification: {e}")
        logger.warning("  Proceeding with original narrative (verification failed)")
        return narrative


def validate_and_fix_conclusion(
    llm_client: LLMClient,
    narrative: str,
    run_date: str
) -> str:
    """
    Validate that the conclusion is not empty rhetoric.
    If it contains prohibited phrases, regenerate it.

    Args:
        llm_client: LLM client instance
        narrative: Newsletter narrative
        run_date: Run date for token tracking

    Returns:
        Narrative with validated/fixed conclusion
    """
    logger = logging.getLogger(__name__)

    # List of prohibited phrases (empty rhetoric)
    prohibited_phrases = [
        "solo el tiempo",
        "el futuro nos dirá",
        "veremos qué depara",
        "tiempo lo dirá",
        "¿aprenderemos de nuestros errores?",
        "¿hacia dónde vamos?",
        "en conclusión",
        "en resumen",
        "para concluir",
        "interconexión de estos eventos",
        "complejidad del mundo actual",
        "tiempos convulsos"
    ]

    # Check if conclusion has prohibited phrases
    conclusion_start = max(len(narrative) - 500, 0)  # Last 500 chars
    conclusion = narrative[conclusion_start:].lower()

    has_prohibited = any(phrase in conclusion for phrase in prohibited_phrases)

    if has_prohibited:
        logger.warning("  ⚠️ Conclusion contains empty rhetoric, regenerating...")

        # Find where conclusion starts (usually last 1-2 paragraphs)
        paragraphs = narrative.split('\n\n')
        if len(paragraphs) >= 2:
            main_body = '\n\n'.join(paragraphs[:-1])  # Everything except last paragraph
            old_conclusion = paragraphs[-1]
        else:
            main_body = narrative
            old_conclusion = ""

        regeneration_prompt = f"""La siguiente newsletter tiene una conclusión con retórica vacía que debe ser reemplazada.

CUERPO PRINCIPAL (conservar tal cual):
{main_body}

CONCLUSIÓN ACTUAL (CON RETÓRICA VACÍA):
{old_conclusion}

TAREA:
Escribe UNA nueva conclusión (1-2 párrafos) que:
- Tenga insight ESPECÍFICO con datos concretos
- O implicación concreta verificable
- O pregunta con sustancia real (no retórica)

PROHIBIDO:
- "solo el tiempo dirá", "el futuro nos dirá"
- "en conclusión", "en resumen"
- Preguntas retóricas vacías
- Generalidades filosóficas

EJEMPLO BUENO:
"Si Europa corta el gas ruso en febrero, Gazprom pierde €36B de €80B anuales (45%). ¿Sobrevivirá el régimen de Putin a ese golpe económico, considerando que el presupuesto militar depende de esos ingresos?"

Devuelve SOLO la nueva conclusión (sin el cuerpo)."""

        new_conclusion = llm_client.call(
            prompt=regeneration_prompt,
            system_prompt="Eres un editor que reemplaza conclusiones vacías por análisis concretos.",
            model="gpt-4o",
            temperature=0.3,
            max_tokens=500,
            stage="05",
            operation="fix_conclusion",
            run_date=run_date
        )

        # Reconstruct narrative with new conclusion
        fixed_narrative = main_body + "\n\n" + new_conclusion.strip()
        logger.info("  ✓ Conclusion regenerated with concrete analysis")
        return fixed_narrative

    else:
        logger.info("  ✓ Conclusion is substantive (no empty rhetoric)")
        return narrative


def summarize_article_with_mini(
    llm_client: LLMClient,
    article: Dict[str, Any],
    run_date: str,
    db: Optional[PostgreSQLURLDatabase] = None
) -> Dict[str, Any]:
    """
    Summarize a full article using gpt-4o-mini with structured JSON output.
    Caches summary in database to avoid regenerating.

    Args:
        llm_client: LLM client instance
        article: Article dictionary with full_content
        run_date: Run date for token tracking
        db: Database instance (optional, for caching)

    Returns:
        Dictionary with structured summary:
        {
            "titular_clave": str,
            "hechos_principales": List[str],
            "datos_clave": {"cifras": List[str], "fechas": List[str], "magnitudes": List[str]},
            "contexto": str,
            "implicaciones": {"principal": str, "conexiones": List[str]},
            "temas_relacionados": List[str],
            "prioridad_narrativa": str
        }
    """
    # Check if summary already exists in database
    if db and article.get('id'):
        cached_summary = db.get_article_summary(article['id'])
        if cached_summary:
            try:
                summary_dict = json.loads(cached_summary)
                logger.debug(f"Using cached JSON summary for article ID {article['id']}")
                return summary_dict
            except (json.JSONDecodeError, TypeError) as e:
                # Invalid JSON in cache - will regenerate
                logger.warning(f"Invalid JSON in cached summary for article ID {article['id']}: {e}. Regenerating...")
                # Continue to generate new summary below

    system_prompt = """Eres un analista que resume noticias en formato JSON estructurado para facilitar su integración narrativa.

Genera un resumen con este schema JSON exacto:

{
  "titular_clave": "Frase de 10-20 palabras que captura la esencia del artículo",
  "hechos_principales": [
    "Punto clave 1 (conciso, directo)",
    "Punto clave 2",
    "Punto clave 3",
    "..."
  ],
  "datos_clave": {
    "cifras": ["Números, porcentajes, cantidades relevantes"],
    "fechas": ["Fechas importantes mencionadas"],
    "magnitudes": ["Comparaciones, récords, contexto cuantitativo"]
  },
  "contexto": "1-3 frases de background necesario para entender la noticia",
  "implicaciones": {
    "principal": "Por qué importa esta noticia, qué significa",
    "conexiones": ["Temas relacionados: economía, política, tecnología, etc."]
  },
  "temas_relacionados": ["tag1", "tag2", "tag3"],
  "prioridad_narrativa": "alta|media|baja"
}

CRITERIOS PRIORIDAD:
- alta: Impacto significativo, datos duros, novedad alta, relevancia clara
- media: Relevante pero no crítico, actualización de tema conocido
- baja: Contextual, de apoyo, baja novedad

REGLAS:
- "hechos_principales": 3-5 bullets máximo, solo lo esencial
- "datos_clave": Si no hay cifras/fechas relevantes, usa arrays vacíos []
- "contexto": Mínimo necesario, sin redundar con hechos
- "implicaciones.conexiones": Temas que se relacionan con esta noticia
- "temas_relacionados": 2-4 tags máximo

Devuelve SOLO el JSON, sin texto adicional."""

    user_prompt = f"""Título: {article['title']}
Fuente: {article['source']}
Categoría: {article['categoria_tematica']}

Contenido completo:
{article['full_content']}

---

Genera el resumen estructurado en formato JSON."""

    try:
        response = llm_client.call(
            prompt=user_prompt,
            system_prompt=system_prompt,
            model="gpt-4o-mini",
            response_format={"type": "json_object"},  # Guarantee valid JSON
            temperature=0.3,
            max_tokens=500,
            stage="05",
            operation="summarize_article",
            run_date=run_date
        )

        # Parse JSON response
        summary_dict = json.loads(response)

        # Validate required fields (use defaults if missing)
        summary_dict.setdefault("titular_clave", article['title'][:100])
        summary_dict.setdefault("hechos_principales", [])
        summary_dict.setdefault("datos_clave", {"cifras": [], "fechas": [], "magnitudes": []})
        summary_dict.setdefault("contexto", "")
        summary_dict.setdefault("implicaciones", {"principal": "", "conexiones": []})
        summary_dict.setdefault("temas_relacionados", [article.get('categoria_tematica', 'otros')])
        summary_dict.setdefault("prioridad_narrativa", "media")

        # Save to database as JSON string
        if db and article.get('id'):
            db.save_article_summary(article['id'], json.dumps(summary_dict, ensure_ascii=False))
            logger.debug(f"Cached JSON summary for article ID {article['id']}")

        return summary_dict

    except json.JSONDecodeError as e:
        logger.warning(f"Error parsing JSON summary for '{article['title']}': {e}")
        # Fallback: return minimal valid structure
        return {
            "titular_clave": article['title'],
            "hechos_principales": [article['full_content'][:200]],
            "datos_clave": {"cifras": [], "fechas": [], "magnitudes": []},
            "contexto": "",
            "implicaciones": {"principal": "", "conexiones": []},
            "temas_relacionados": [article.get('categoria_tematica', 'otros')],
            "prioridad_narrativa": "media"
        }
    except Exception as e:
        logger.warning(f"Error summarizing article '{article['title']}': {e}")
        # Fallback: return minimal valid structure
        return {
            "titular_clave": article['title'],
            "hechos_principales": [article['full_content'][:200] if article.get('full_content') else ""],
            "datos_clave": {"cifras": [], "fechas": [], "magnitudes": []},
            "contexto": "",
            "implicaciones": {"principal": "", "conexiones": []},
            "temas_relacionados": [article.get('categoria_tematica', 'otros')],
            "prioridad_narrativa": "media"
        }


def add_links_to_newsletter(
    llm_client: LLMClient,
    newsletter_content: str,
    articles: List[Dict[str, Any]],
    run_date: str
) -> str:
    """
    Add clickable links to the newsletter ensuring ALL articles are linked at least once.

    Uses gpt-4o for maximum accuracy. The goal is EXHAUSTIVE coverage: every single
    article URL must appear at least once as a clickable link in the narrative.

    Args:
        llm_client: LLM client instance
        newsletter_content: Generated newsletter with bold keywords
        articles: List of articles with URLs (ALL must be linked)
        run_date: Run date for token tracking

    Returns:
        Newsletter content with ALL articles linked at least once
    """
    # Build article reference list with index for tracking
    article_refs = []
    for idx, article in enumerate(articles, 1):
        article_refs.append(f"[{idx}] Título: {article['title']}\n    URL: {article['url']}")

    articles_list = "\n".join(article_refs)
    total_articles = len(articles)

    system_prompt = f"""Eres un editor experto que añade enlaces a newsletters.

TU MISIÓN CRÍTICA: Garantizar que TODOS los {total_articles} artículos de la lista aparezcan como enlaces clickeables en el texto.

REGLAS ABSOLUTAS:
1. **COBERTURA 100% OBLIGATORIA**: Cada uno de los {total_articles} artículos DEBE tener al menos UN enlace en el texto
2. Formato de enlace: [**texto relevante**](url) o [texto relevante](url)
3. El texto del enlace debe ser relevante al artículo (nombre de persona, evento, tema, etc.)
4. NO cambies el contenido narrativo, solo añade los enlaces
5. Si un artículo no tiene una mención clara, BUSCA la frase más relacionada y enlázala
6. Un mismo artículo puede tener múltiples enlaces si se menciona varias veces
7. NO inventes URLs - usa SOLO las URLs de la lista proporcionada

ESTRATEGIA PARA COBERTURA TOTAL:
- Primero identifica qué artículos YA están mencionados claramente → enlázalos
- Luego identifica artículos sin mención clara → busca frases relacionadas temáticamente y enlázalas
- Si un artículo no tiene ninguna frase relacionable, añade una mención breve y natural con su enlace

VERIFICACIÓN: Al terminar, asegúrate de que cada una de las {total_articles} URLs aparece al menos una vez como enlace.

IMPORTANTE: Preserva TODO el formato Markdown existente."""

    user_prompt = f"""NEWSLETTER ORIGINAL:

{newsletter_content}

---

LISTA COMPLETA DE ARTÍCULOS ({total_articles} artículos - TODOS deben aparecer como enlaces):

{articles_list}

---

TAREA:
1. Añade enlaces a TODOS los {total_articles} artículos en el texto narrativo
2. Cada URL debe aparecer al menos UNA vez como enlace clickeable
3. Usa el formato [**texto**](url) o [texto](url)
4. Si un artículo no tiene mención clara, busca la frase más relacionada o añade una mención natural

IMPORTANTE: Devuelve el newsletter COMPLETO con TODOS los enlaces añadidos.
Verifica que las {total_articles} URLs están presentes como enlaces antes de responder."""

    try:
        modified_content = llm_client.call(
            prompt=user_prompt,
            system_prompt=system_prompt,
            model="gpt-4o",  # Using gpt-4o for better accuracy and coverage
            temperature=0.2,  # Low temperature for precision
            max_tokens=12000,  # Increased for longer output with all links
            stage="05",
            operation="add_links_exhaustive",
            run_date=run_date
        )

        # Verify coverage
        linked_count = sum(1 for article in articles if article['url'] in modified_content)
        logger.info(f"Link coverage: {linked_count}/{total_articles} articles linked")

        if linked_count < total_articles:
            missing = [a['title'][:50] for a in articles if a['url'] not in modified_content]
            logger.warning(f"Missing links for {total_articles - linked_count} articles: {missing[:5]}...")

        return modified_content.strip()

    except Exception as e:
        logger.warning(f"Error adding links: {e}")
        logger.warning("Returning original content without links")
        return newsletter_content


def generate_newsletter_two_stage(
    llm_client: LLMClient,
    articles: List[Dict[str, Any]],
    ranked_data: Dict[str, Any],
    template: Dict[str, str],
    newsletter_config: Dict[str, Any],
    run_date: str,
    db: Optional[PostgreSQLURLDatabase] = None
) -> str:
    """
    Generate newsletter using 7-step approach:
    1. Summarize full articles with gpt-4o-mini (cheap) - CACHED in DB
    2. Generate main narrative with gpt-4o using summaries (quality)
    3. Complete narrative with remaining headlines using gpt-4o (quality + coverage)
    4. Verify 100% coverage with function calling (gpt-4o)
    5. Validate and fix conclusion for empty rhetoric (gpt-4o if needed)
    6. De-robotize text to remove formulaic patterns (gpt-4o)
    7. Add clickable links to bold keywords with gpt-4o-mini (precision)

    Args:
        llm_client: LLM client instance
        articles: List of article dictionaries
        ranked_data: Original ranked JSON data
        template: Prompt template dictionary
        newsletter_config: Newsletter configuration
        run_date: Run date for token tracking
        db: Database instance (for caching summaries)

    Returns:
        Complete newsletter content in Markdown with clickable links
    """
    # Separate articles with/without content
    articles_with_content = [a for a in articles if a['has_full_content']]
    articles_without_content = [a for a in articles if not a['has_full_content']]

    logger.info(f"📊 Seven-stage generation: {len(articles_with_content)} with content, {len(articles_without_content)} headlines only")

    # ========== STEP 1: Summarize articles with gpt-4o-mini ==========
    logger.info("📝 Step 1/7: Summarizing articles with gpt-4o-mini (with DB caching)...")
    summaries = []
    for i, article in enumerate(articles_with_content, 1):
        logger.info(f"  Summarizing {i}/{len(articles_with_content)}: {article['title'][:60]}...")
        summary = summarize_article_with_mini(llm_client, article, run_date, db)
        summaries.append({
            'rank': article['rank'],
            'title': article['title'],
            'source': article['source'],
            'categoria_tematica': article['categoria_tematica'],
            'url': article.get('url', ''),
            'summary': summary,  # Now a dict with structured JSON
            'related_articles': article.get('related_articles', [])  # v3.2: cluster context
        })

    # ========== STEP 2: Generate main narrative with gpt-4o ==========
    logger.info("🎨 Step 2/7: Generating main narrative with gpt-4o using summaries...")

    # Build context with structured summaries (leveraging JSON format)
    context_parts = []
    context_parts.append(f"FECHA: {ranked_data.get('run_date', 'Unknown')}")
    context_parts.append(f"ARTÍCULOS PRINCIPALES: {len(summaries)}")
    context_parts.append("")

    # v3.2/v3.3: Add instructions for using related articles (including historical)
    articles_with_related = sum(1 for s in summaries if s.get('related_articles'))
    historical_count = sum(
        sum(1 for r in s.get('related_articles', []) if r.get('is_historical'))
        for s in summaries
    )
    if articles_with_related > 0:
        context_parts.append("=== INSTRUCCIÓN ESPECIAL: VISIÓN 360° + CONTEXTO HISTÓRICO ===")
        context_parts.append("")
        context_parts.append("Algunos artículos incluyen '📎 ARTÍCULOS RELACIONADOS' que pueden ser:")
        context_parts.append("- Noticias del MISMO tema desde otras fuentes (mismo día)")
        context_parts.append("- **NOTICIAS HISTÓRICAS** del mismo tema (marcadas con 📜 y fecha)")
        context_parts.append("")
        context_parts.append("## CÓMO USAR ESTA INFORMACIÓN:")
        context_parts.append("")
        context_parts.append("### Para artículos del mismo día:")
        context_parts.append("- Perspectivas adicionales y datos complementarios")
        context_parts.append("- Contraste sutil si las fuentes difieren")
        context_parts.append("")
        context_parts.append("### Para artículos HISTÓRICOS (📜):")
        context_parts.append("- **USA ACTIVAMENTE** esta información para dar PROFUNDIDAD al análisis")
        context_parts.append("- Menciona cómo ha EVOLUCIONADO la historia: 'Hace X semanas...', 'Este desarrollo viene de...'")
        context_parts.append("- Conecta el presente con el pasado: qué cambió, qué se predijo, qué se cumplió")
        context_parts.append("- Incluye datos históricos relevantes que enriquezcan la narrativa actual")
        context_parts.append("- Muestra la TRAYECTORIA del tema: de dónde viene y hacia dónde va")
        context_parts.append("")
        context_parts.append("**IMPORTANTE:** No menciones que hay 'artículos relacionados'. Integra la información")
        context_parts.append("naturalmente como si fueras un experto que CONOCE la historia completa del tema.")
        context_parts.append("El lector debe percibir que tienes un conocimiento profundo y contextualizado.")
        context_parts.append("")
        if historical_count > 0:
            context_parts.append(f"📊 Tienes {historical_count} artículos históricos disponibles para dar profundidad.")
            context_parts.append("")

    context_parts.append("=== ARTÍCULOS PRINCIPALES (resúmenes estructurados) ===")
    context_parts.append("")

    for s in summaries:
        summary_data = s['summary']  # Dict with JSON structure

        # Header
        context_parts.append(f"## [{s['rank']}] {summary_data.get('titular_clave', s['title'])}")
        context_parts.append(f"**URL:** {s['url']}")
        context_parts.append(f"**Fuente:** {s['source']}")
        context_parts.append(f"**Categoría:** {s['categoria_tematica']}")
        context_parts.append(f"**Prioridad:** {summary_data.get('prioridad_narrativa', 'media')}")
        context_parts.append("")

        # Key facts
        hechos = summary_data.get('hechos_principales', [])
        if hechos:
            context_parts.append("**Hechos principales:**")
            for hecho in hechos:
                context_parts.append(f"• {hecho}")
            context_parts.append("")

        # Data (only if exists)
        datos = summary_data.get('datos_clave', {})
        cifras = datos.get('cifras', [])
        fechas = datos.get('fechas', [])
        magnitudes = datos.get('magnitudes', [])

        if cifras or fechas or magnitudes:
            context_parts.append("**Datos clave:**")
            if cifras:
                context_parts.append(f"  Cifras: {', '.join(cifras)}")
            if fechas:
                context_parts.append(f"  Fechas: {', '.join(fechas)}")
            if magnitudes:
                context_parts.append(f"  Magnitudes: {', '.join(magnitudes)}")
            context_parts.append("")

        # Context
        contexto = summary_data.get('contexto', '')
        if contexto:
            context_parts.append(f"**Contexto:** {contexto}")
            context_parts.append("")

        # Implications
        implicaciones = summary_data.get('implicaciones', {})
        principal = implicaciones.get('principal', '')
        conexiones = implicaciones.get('conexiones', [])

        if principal:
            context_parts.append(f"**Por qué importa:** {principal}")
        if conexiones:
            context_parts.append(f"**Conecta con:** {', '.join(conexiones)}")
        context_parts.append("")

        # v3.2: Add related articles from cluster for 360° context
        related_articles = s.get('related_articles', [])
        if related_articles:
            context_parts.append("**📎 ARTÍCULOS RELACIONADOS (mismo evento, distintas fuentes):**")
            context_parts.append("Usa esta información para enriquecer el resumen con perspectivas adicionales:")
            context_parts.append("")
            for related in related_articles:
                context_parts.append(f"  • **{related['title']}** ({related['source']})")
                if related.get('has_content') and related.get('full_content'):
                    # Include snippet of related content for context
                    content_snippet = related['full_content'][:500]
                    if len(related['full_content']) > 500:
                        content_snippet += "..."
                    context_parts.append(f"    Contenido: {content_snippet}")
                context_parts.append("")
            context_parts.append("")

        context_parts.append("-" * 80)
        context_parts.append("")

    context_summaries = "\n".join(context_parts)

    # Generate main narrative
    user_prompt_stage1 = template.get('user_prompt_template', '{context}').format(
        context=context_summaries,
        newsletter_name=newsletter_config.get('name', 'Newsletter'),
        date=ranked_data.get('run_date', 'Unknown')
    )

    system_prompt = template.get('system_prompt', 'You are a helpful assistant.')

    logger.info(f"  Calling gpt-4o for main narrative...")
    main_narrative = llm_client.call(
        prompt=user_prompt_stage1,
        system_prompt=system_prompt,
        model="gpt-4o",
        temperature=0.4,
        max_tokens=8000,
        stage="05",
        operation="generate_main_narrative",
        run_date=run_date
    )

    logger.info("  Main narrative generated successfully")

    # ========== STEP 3: Complete with headlines using gpt-4o ==========
    if articles_without_content:
        logger.info(f"🔗 Step 3/7: Completing narrative with {len(articles_without_content)} remaining headlines using gpt-4o...")

        # Load stage 2 template
        try:
            template_stage2 = load_prompt_template('default_stage2')
        except:
            logger.warning("Template default_stage2 not found, using inline prompt")
            template_stage2 = {
                'system_prompt': "Completa la newsletter integrando los titulares adicionales.",
                'user_prompt_template': "Narrativa:\n{existing_narrative}\n\nTitulares:\n{additional_headlines}"
            }

        # Build headlines list
        headlines_parts = []
        for article in articles_without_content:
            headlines_parts.append(
                f"[{article['rank']}] {article['title']} | "
                f"Fuente: {article['source']} | "
                f"Categoría: {article['categoria_tematica']}"
            )

        additional_headlines = "\n".join(headlines_parts)

        # Complete narrative
        user_prompt_stage2 = template_stage2.get('user_prompt_template', '{existing_narrative}\n\n{additional_headlines}').format(
            existing_narrative=main_narrative,
            additional_headlines=additional_headlines
        )

        system_prompt_stage2 = template_stage2.get('system_prompt', system_prompt)

        logger.info(f"  Calling gpt-4o to integrate {len(articles_without_content)} headlines...")
        complete_narrative = llm_client.call(
            prompt=user_prompt_stage2,
            system_prompt=system_prompt_stage2,
            model="gpt-4o",
            temperature=0.4,
            max_tokens=8000,
            stage="05",
            operation="complete_with_headlines",
            run_date=run_date
        )

        logger.info("  Narrative completed with all headlines")
    else:
        logger.info("  No additional headlines to integrate")
        complete_narrative = main_narrative

    # ========== STEP 4: Verify 100% coverage with function calling ==========
    logger.info("🔍 Step 4/7: Verifying 100% article coverage using gpt-4o with function calling...")
    complete_narrative_verified = verify_and_complete_coverage(
        llm_client,
        complete_narrative,
        articles,
        run_date
    )

    # ========== STEP 5: Validate and fix conclusion ==========
    logger.info("✅ Step 5/7: Validating conclusion for empty rhetoric...")
    final_narrative_clean = validate_and_fix_conclusion(
        llm_client,
        complete_narrative_verified,
        run_date
    )

    # ========== STEP 6: De-robotize text (remove formulaic patterns) ==========
    logger.info("🎭 Step 6/7: Humanizing text (removing robotic patterns)...")
    humanized_narrative = derobotize_text(
        llm_client,
        final_narrative_clean,
        run_date
    )

    # ========== STEP 7: Add clickable links to bold keywords ==========
    logger.info("🔗 Step 7/7: Adding clickable links to bold keywords using gpt-4o-mini...")
    final_narrative = add_links_to_newsletter(
        llm_client,
        humanized_narrative,
        articles,  # Pass all articles (with and without content)
        run_date
    )

    # ========== CLEANUP: Remove LLM meta-comments ==========
    # Sometimes the model adds comments like "He añadido enlaces..." at the end
    import re
    meta_patterns = [
        r'\n---\n\nHe añadido.*$',
        r'\n---\n\nHe integrado.*$',
        r'\n---\n\nHe incluido.*$',
        r'\n---\n\nCon esto.*$',
        r'\n---\n\nTodos los.*artículos.*$',
    ]
    for pattern in meta_patterns:
        final_narrative = re.sub(pattern, '', final_narrative, flags=re.IGNORECASE | re.DOTALL)

    logger.info("  Newsletter generation completed with links")
    return final_narrative


def generate_newsletter_with_llm(
    llm_client: LLMClient,
    articles: List[Dict[str, Any]],
    ranked_data: Dict[str, Any],
    template: Dict[str, str],
    newsletter_config: Dict[str, Any],
    run_date: str
) -> str:
    """
    Generate newsletter content using LLM.

    Args:
        llm_client: LLM client instance
        articles: List of article dictionaries
        ranked_data: Original ranked JSON data
        template: Prompt template dictionary
        newsletter_config: Newsletter configuration
        run_date: Run date for token tracking

    Returns:
        Generated newsletter content in Markdown
    """
    logger.info("Building context for LLM...")
    context = build_llm_context(articles, ranked_data)

    logger.info(f"Context size: {len(context)} characters")

    # Build user prompt from template
    user_prompt_template = template.get('user_prompt_template', '{context}')
    user_prompt = user_prompt_template.format(
        context=context,
        newsletter_name=newsletter_config.get('name', 'Newsletter'),
        date=ranked_data.get('run_date', 'Unknown')
    )

    system_prompt = template.get('system_prompt', 'You are a helpful assistant.')

    logger.info(f"Calling LLM with model: {MODEL_WRITER}")

    try:
        response = llm_client.call(
            prompt=user_prompt,
            system_prompt=system_prompt,
            model=MODEL_WRITER,
            temperature=0.4,  # Lower for analytical/institutional writing (precision over creativity)
            max_tokens=8000,  # Enough for long-form newsletter
            stage="05",
            operation="generate_newsletter",
            run_date=run_date
        )

        logger.info("Newsletter generated successfully")
        return response

    except Exception as e:
        logger.error(f"Error calling LLM: {e}")
        raise


def render_output_template(
    newsletter_content: str,
    articles: List[Dict[str, Any]],
    newsletter_config: Dict[str, Any],
    ranked_data: Dict[str, Any],
    output_format: str
) -> str:
    """
    Render final output using Jinja2 template.

    Args:
        newsletter_content: Generated newsletter text (Markdown)
        articles: List of article dictionaries
        newsletter_config: Newsletter configuration
        ranked_data: Original ranked data
        output_format: 'markdown' or 'html'

    Returns:
        Rendered output string
    """
    templates_dir = Path("templates") / "outputs"

    if output_format == 'html':
        template_file = "newsletter.html"
    else:
        template_file = "newsletter.md"

    env = Environment(
        loader=FileSystemLoader(templates_dir),
        autoescape=select_autoescape(['html', 'xml']) if output_format == 'html' else False
    )

    try:
        template = env.get_template(template_file)
    except Exception as e:
        logger.warning(f"Template {template_file} not found: {e}. Using raw content.")
        return newsletter_content

    rendered = template.render(
        newsletter_name=newsletter_config.get('title', newsletter_config.get('name', 'Newsletter')),
        newsletter_description=newsletter_config.get('description', ''),
        date=ranked_data.get('run_date', 'Unknown'),
        generated_at=datetime.now(ZoneInfo("Europe/Madrid")).strftime('%Y-%m-%d %H:%M:%S CET/CEST'),
        content=newsletter_content,
        articles=articles,
        total_articles=len(articles),
        articles_with_content=len([a for a in articles if a['has_full_content']])
    )

    return rendered


def save_newsletter(
    content: str,
    newsletter_name: str,
    run_date: str,
    output_format: str,
    newsletter_config: Dict[str, Any],
    force: bool = False
) -> str:
    """
    Save newsletter to file with execution parameters in filename.

    Args:
        content: Newsletter content
        newsletter_name: Name of newsletter
        run_date: Run date (YYYY-MM-DD)
        output_format: 'markdown' or 'html'
        newsletter_config: Newsletter configuration with categories, template, etc.
        force: Force overwrite if file exists

    Returns:
        Path to saved file
    """
    output_dir = Path("data") / "newsletters"
    output_dir.mkdir(parents=True, exist_ok=True)

    # Build filename with execution parameters
    timestamp = datetime.now(ZoneInfo("Europe/Madrid")).strftime('%H%M%S')

    # Get categories for filename
    categories = newsletter_config.get('categories', [])
    if categories:
        categories_str = '-'.join(sorted([c.lower() for c in categories]))
    else:
        categories_str = 'all'

    # Get template name (short form)
    template = newsletter_config.get('template', 'default')
    template_short = template.replace('_', '')[:8]  # Max 8 chars, no underscores

    ext = 'html' if output_format == 'html' else 'md'

    # Filename format: newsletter_{name}_{date}_{timestamp}_{categories}_{template}.{ext}
    filename = f"newsletter_{newsletter_name}_{run_date}_{timestamp}_{categories_str}_{template_short}.{ext}"
    output_path = output_dir / filename

    if output_path.exists() and not force:
        logger.warning(f"Newsletter file already exists: {output_path}")
        logger.info("Use --force to overwrite")
        return str(output_path)

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(content)

    logger.info(f"Newsletter saved: {output_path}")
    return str(output_path)


def generate_context_report(
    newsletter_name: str,
    run_date: str,
    ranked_data: Dict[str, Any],
    all_url_ids: List[int],
    articles: List[Dict[str, Any]],
    articles_with_content: List[Dict[str, Any]],
    newsletter_config: Dict[str, Any],
    newsletter_content: str,
    db: PostgreSQLURLDatabase
) -> str:
    """
    Generate detailed execution context report for debugging and verification.

    This report includes:
    - Newsletter configuration
    - Initial ranked URLs order
    - URLs selected for content extraction
    - Actual extraction results
    - Full content for successfully extracted articles
    - Categories for each URL
    - Execution metadata

    Args:
        newsletter_name: Name of newsletter
        run_date: Run date (YYYY-MM-DD)
        ranked_data: Original ranked JSON data
        all_url_ids: List of URL IDs processed
        articles: All articles data
        articles_with_content: Articles with successfully extracted content
        newsletter_config: Newsletter configuration
        newsletter_content: Generated newsletter content
        db: Database connection

    Returns:
        Path to saved report file
    """
    from datetime import datetime
    from zoneinfo import ZoneInfo

    logger.info("Building context report...")

    # Build report structure
    report = {
        "metadata": {
            "newsletter_name": newsletter_name,
            "run_date": run_date,
            "generated_at": datetime.now(ZoneInfo("Europe/Madrid")).isoformat(),
            "stage": "05_generate_newsletters"
        },
        "configuration": {
            "max_articles": len(all_url_ids),
            "top_with_content": len(articles_with_content),
            "expected_categories": newsletter_config.get('categories', []),
            "ranked_file_categories": ranked_data.get('metadata', {}).get('categories_filter'),
            "template": newsletter_config.get('template', 'default'),
            "model_writer": os.getenv('MODEL_WRITER', 'gpt-4o-mini'),
            "output_format": newsletter_config.get('output_format', 'markdown')
        },
        "ranked_data": {
            "total_urls_in_ranked_file": len(ranked_data.get('headlines', [])),
            "urls_selected_for_processing": len(all_url_ids),
            "initial_ranked_order": []
        },
        "content_extraction": {
            "urls_requested_for_content": [],
            "urls_successfully_extracted": [],
            "urls_failed_extraction": [],
            "extraction_stats": {
                "total_requested": 0,
                "total_success": 0,
                "total_failed": 0,
                "success_rate": 0.0
            }
        },
        "articles": [],
        "newsletter_preview": {
            "word_count": len(newsletter_content.split()),
            "char_count": len(newsletter_content),
            "first_500_chars": newsletter_content[:500] + "..." if len(newsletter_content) > 500 else newsletter_content
        }
    }

    # Populate initial ranked order from ranked_data
    for idx, headline in enumerate(ranked_data.get('headlines', [])[:len(all_url_ids)], 1):
        report['ranked_data']['initial_ranked_order'].append({
            "rank": idx,
            "url_id": headline.get('id'),
            "url": headline.get('url'),
            "title": headline.get('title'),
            "source": headline.get('source'),
            "category": headline.get('categoria_tematica', 'Unknown')
        })

    # Populate articles with detailed info
    for idx, article in enumerate(articles, 1):
        url_data = db.get_url_by_id(article['id'])

        article_info = {
            "processing_rank": idx,
            "url_id": article['id'],
            "url": article['url'],
            "title": article['title'],
            "source": article['source'],
            "category": article.get('categoria_tematica', 'Unknown'),
            "has_full_content": article.get('has_full_content', False),
            "extraction_status": url_data.get('extraction_status', 'unknown'),
            "extraction_method": url_data.get('content_extraction_method'),
            "extraction_error": url_data.get('extraction_error'),
            "word_count": article.get('word_count', 0),
            "archive_url": url_data.get('archive_url')
        }

        # Add full content if available
        if article.get('has_full_content') and article.get('full_content'):
            article_info['full_content'] = article['full_content']
            article_info['content_preview'] = article['full_content'][:500] + "..." if len(article['full_content']) > 500 else article['full_content']

            # Add to successfully extracted list
            report['content_extraction']['urls_successfully_extracted'].append({
                "rank": idx,
                "url_id": article['id'],
                "url": article['url'],
                "title": article['title'],
                "method": url_data.get('content_extraction_method'),
                "word_count": article.get('word_count', 0)
            })
        else:
            # Add to failed/not extracted list
            if url_data.get('extraction_status') in ['failed', 'pending']:
                report['content_extraction']['urls_failed_extraction'].append({
                    "rank": idx,
                    "url_id": article['id'],
                    "url": article['url'],
                    "title": article['title'],
                    "status": url_data.get('extraction_status'),
                    "error": url_data.get('extraction_error')
                })

        report['articles'].append(article_info)

    # Track which URLs were requested for content extraction (top N)
    top_n = len(articles_with_content)
    report['content_extraction']['urls_requested_for_content'] = [
        {
            "rank": idx + 1,
            "url_id": article['id'],
            "url": article['url'],
            "title": article['title']
        }
        for idx, article in enumerate(articles[:top_n])
    ]

    # Update extraction stats
    report['content_extraction']['extraction_stats'] = {
        "total_requested": len(report['content_extraction']['urls_requested_for_content']),
        "total_success": len(report['content_extraction']['urls_successfully_extracted']),
        "total_failed": len(report['content_extraction']['urls_failed_extraction']),
        "success_rate": round(
            len(report['content_extraction']['urls_successfully_extracted']) /
            max(len(report['content_extraction']['urls_requested_for_content']), 1) * 100,
            2
        )
    }

    # Save report to file with execution parameters in filename
    output_dir = Path("data") / "newsletters"
    output_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(ZoneInfo("Europe/Madrid")).strftime('%H%M%S')

    # Get categories for filename
    categories = newsletter_config.get('categories', [])
    if categories:
        categories_str = '-'.join(sorted([c.lower() for c in categories]))
    else:
        categories_str = 'all'

    # Get template name (short form)
    template = newsletter_config.get('template', 'default')
    template_short = template.replace('_', '')[:8]  # Max 8 chars, no underscores

    # Filename format: context_report_{name}_{date}_{timestamp}_{categories}_{template}.json
    filename = f"context_report_{newsletter_name}_{run_date}_{timestamp}_{categories_str}_{template_short}.json"
    output_path = output_dir / filename

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    logger.info(f"Context report saved: {output_path}")
    logger.info(f"Report contains {len(report['articles'])} articles, "
                f"{len(articles_with_content)} with full content")

    return str(output_path)


def main():
    """Main execution function (refactored for DB-centric approach)."""
    parser = argparse.ArgumentParser(
        description='Stage 05: Generate newsletter from ranked URLs with content (reads from database)'
    )

    parser.add_argument(
        '--newsletter-name',
        required=True,
        help='Name of newsletter'
    )

    parser.add_argument(
        '--date',
        required=True,
        help='Run date (YYYY-MM-DD)'
    )

    parser.add_argument(
        '--output-format',
        choices=['markdown', 'html', 'both'],
        default='markdown',
        help='Output format (default: markdown)'
    )

    parser.add_argument(
        '--template',
        default='default',
        help='Prompt template name (default: default)'
    )

    parser.add_argument(
        '--skip-llm',
        action='store_true',
        help='Skip LLM generation (template only)'
    )

    parser.add_argument(
        '--force',
        action='store_true',
        help='Force regeneration even if output exists'
    )

    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Enable verbose logging'
    )

    parser.add_argument(
        '--related-window-days',
        type=int,
        default=0,
        help='Days back to look for related articles from same cluster (0 = same day only, 365 = 1 year)'
    )

    args = parser.parse_args()

    # Setup logging
    setup_logging(args.date, args.verbose)

    logger.info("="*80)
    logger.info("STAGE 05: GENERATE NEWSLETTER")
    logger.info("="*80)
    logger.info(f"Newsletter: {args.newsletter_name}")
    logger.info(f"Run date: {args.date}")
    logger.info(f"Output format: {args.output_format}")
    logger.info(f"Template: {args.template}")
    logger.info(f"Related window: {args.related_window_days} days back")

    # Start timing
    import time
    stage_start_time = time.time()

    # Initialize database
    db = PostgreSQLURLDatabase(os.getenv('DATABASE_URL'))

    # Get ranking run from database
    ranking_run = db.get_ranking_run(args.newsletter_name, args.date)
    if not ranking_run:
        logger.error(f"No ranking found for {args.newsletter_name} on {args.date}")
        logger.error("Run Stage 03 first to generate ranking")
        return {
            "status": "failed",
            "error": f"No ranking found for {args.newsletter_name} on {args.date}"
        }

    ranking_run_id = ranking_run['id']
    logger.info(f"Ranking run ID: {ranking_run_id}")

    # Get ALL ranked URLs from database (both with and without content)
    all_ranked_urls = db.get_ranked_urls(ranking_run_id)
    logger.info(f"Total ranked URLs: {len(all_ranked_urls)}")

    # Transform to article format expected by generate_newsletter_two_stage()
    articles = []
    for ranked_url in all_ranked_urls:
        categoria = ranked_url.get('categoria_tematica', 'Sin categoría')
        article = {
            'id': ranked_url['id'],
            'rank': ranked_url['rank'],
            'url': ranked_url['url'],
            'title': ranked_url['title'],
            'source': urlparse(ranked_url['source']).netloc if ranked_url.get('source') else 'Unknown',
            'categoria_tematica': categoria,
            'category': categoria,  # Alias for Jinja2 template compatibility
            'has_full_content': (ranked_url.get('extraction_status') == 'success' and ranked_url.get('full_content') is not None),
            'full_content': ranked_url.get('full_content'),
            'word_count': ranked_url.get('word_count', 0),
            'extraction_status': ranked_url.get('extraction_status', 'unknown'),
            'related_url_ids': [],  # v3.2: cluster-related articles
            'related_articles': []  # v3.2: full data of related articles
        }

        # v3.2: Load related articles from cluster deduplication (same-day related)
        related_url_ids_json = ranked_url.get('related_url_ids')
        if related_url_ids_json:
            try:
                related_ids = json.loads(related_url_ids_json)
                article['related_url_ids'] = related_ids

                # Fetch related articles data for 360° context
                related_articles = []
                for related_id in related_ids:
                    related_data = db.get_url_by_id(related_id)
                    if related_data:
                        related_articles.append({
                            'id': related_data['id'],
                            'title': related_data['title'],
                            'source': urlparse(related_data['source']).netloc if related_data.get('source') else 'Unknown',
                            'url': related_data['url'],
                            'full_content': related_data.get('full_content'),
                            'word_count': related_data.get('word_count', 0),
                            'has_content': related_data.get('extraction_status') == 'success' and related_data.get('full_content') is not None,
                            'extracted_at': related_data.get('extracted_at')
                        })
                article['related_articles'] = related_articles
            except (json.JSONDecodeError, TypeError):
                pass

        # v3.3: Load historical related articles from cluster with time window
        related_window_days = getattr(args, 'related_window_days', 0)
        cluster_id = ranked_url.get('cluster_id')
        if cluster_id and related_window_days > 0:
            # Get articles from same cluster within time window
            historical_related = db.get_cluster_related_articles(
                cluster_id=cluster_id,
                exclude_url_id=ranked_url['id'],
                reference_date=args.date,
                max_days_back=related_window_days,
                limit=10
            )

            # Add historical articles not already in related_articles
            existing_ids = {r['id'] for r in article.get('related_articles', [])}
            for hist_data in historical_related:
                if hist_data['id'] not in existing_ids:
                    article['related_articles'].append({
                        'id': hist_data['id'],
                        'title': hist_data['title'],
                        'source': urlparse(hist_data['source']).netloc if hist_data.get('source') else 'Unknown',
                        'url': hist_data['url'],
                        'full_content': hist_data.get('full_content'),
                        'word_count': hist_data.get('word_count', 0),
                        'has_content': hist_data.get('extraction_status') == 'success' and hist_data.get('full_content') is not None,
                        'extracted_at': hist_data.get('extracted_at'),
                        'is_historical': True  # Flag to indicate historical context
                    })
                    existing_ids.add(hist_data['id'])

        articles.append(article)

    # Log cluster context stats
    articles_with_related = sum(1 for a in articles if a.get('related_articles'))
    total_related = sum(len(a.get('related_articles', [])) for a in articles)
    total_historical = sum(
        sum(1 for r in a.get('related_articles', []) if r.get('is_historical'))
        for a in articles
    )
    if articles_with_related > 0:
        logger.info(f"Cluster context: {articles_with_related} articles have {total_related} related articles for 360° view")
        if total_historical > 0:
            logger.info(f"  └─ Historical context: {total_historical} articles from past {args.related_window_days} days")

    articles_with_content = [a for a in articles if a['has_full_content']]
    logger.info(f"Articles with full content: {len(articles_with_content)}")

    if len(articles_with_content) == 0:
        logger.error("No articles have full content. Did Stage 04 run successfully?")
        execution_time = time.time() - stage_start_time
        return {
            "status": "failed",
            "error": "No articles have full content",
            "urls_used": 0,
            "execution_time": execution_time
        }

    # Parse categories from ranking run
    import json as json_module
    categories_filter = json_module.loads(ranking_run['categories_filter']) if ranking_run['categories_filter'] else []

    # Newsletter configuration
    newsletter_config = {
        'name': args.newsletter_name,
        'title': os.getenv('NEWSLETTER_TITLE', args.newsletter_name),
        'description': os.getenv('NEWSLETTER_DESCRIPTION', ''),
        'template': args.template,
        'output_format': args.output_format,
        'categories': categories_filter,
    }

    # Build ranked_data structure for compatibility with existing functions
    ranked_data = {
        'run_date': args.date,
        'newsletter_name': args.newsletter_name,
        'execution_params': {
            'categories_filter': categories_filter,
            'ranker_method': ranking_run['ranker_method']
        }
    }

    # Generate newsletter
    if args.skip_llm:
        logger.info("Skipping LLM generation (--skip-llm)")
        newsletter_content = "# Newsletter\n\n[LLM generation skipped]\n\n## Articles\n\n"
        newsletter_content += "\n".join([f"- {a['title']}" for a in articles])
    else:
        # Load prompt template
        logger.info(f"Loading prompt template: {args.template}")
        try:
            template = load_prompt_template(args.template)
        except Exception as e:
            logger.error(f"Error loading template: {e}")
            return 1

        # Initialize LLM client
        llm_client = LLMClient()

        # Generate newsletter with LLM using two-stage approach
        logger.info("Generating newsletter content with LLM (3-step approach)...")
        try:
            newsletter_content = generate_newsletter_two_stage(
                llm_client,
                articles,
                ranked_data,
                template,
                newsletter_config,
                args.date,
                db  # Pass db for summary caching
            )
        except Exception as e:
            logger.error(f"Error generating newsletter: {e}")
            return 1

    # Render output(s)
    formats_to_generate = ['markdown', 'html'] if args.output_format == 'both' else [args.output_format]
    output_files = []

    for output_format in formats_to_generate:
        logger.info(f"Rendering {output_format} output...")
        try:
            rendered_content = render_output_template(
                newsletter_content,
                articles,
                newsletter_config,
                ranked_data,
                output_format
            )

            output_file = save_newsletter(
                rendered_content,
                args.newsletter_name,
                args.date,
                output_format,
                newsletter_config,
                args.force
            )
            output_files.append(output_file)

        except Exception as e:
            logger.error(f"Error rendering {output_format}: {e}")

    # Generate execution context report
    logger.info("Generating execution context report...")
    try:
        context_report_file = generate_context_report(
            newsletter_name=args.newsletter_name,
            run_date=args.date,
            ranked_data=ranked_data,
            all_url_ids=[a['id'] for a in articles],
            articles=articles,
            articles_with_content=articles,
            newsletter_config=newsletter_config,
            newsletter_content=newsletter_content,
            db=db
        )
        logger.info(f"Context report saved: {context_report_file}")
        output_files.append(context_report_file)
    except Exception as e:
        logger.error(f"Failed to generate context report: {e}")
        import traceback
        logger.error(traceback.format_exc())

    # Calculate execution time and tokens used
    execution_time = time.time() - stage_start_time

    # Track tokens used (if LLM was used)
    tokens_used = 0
    if not args.skip_llm:
        # TODO: Extract actual token usage from LLM client if available
        tokens_used = 0  # Placeholder

    # Save newsletter to database (v3.1)
    logger.info("Saving newsletter to database...")
    try:
        # Get content by format
        content_markdown = None
        content_html = None
        output_file_md = None
        output_file_html = None

        for output_file in output_files:
            if output_file.endswith('.md'):
                output_file_md = output_file
                # Read markdown content
                with open(output_file, 'r', encoding='utf-8') as f:
                    content_markdown = f.read()
            elif output_file.endswith('.html'):
                output_file_html = output_file
                # Read HTML content
                with open(output_file, 'r', encoding='utf-8') as f:
                    content_html = f.read()
            elif output_file.endswith('.json'):
                context_report_file = output_file

        # Get ranking_run_id
        ranking_run = db.get_ranking_run(args.newsletter_name, args.date)
        ranking_run_id = ranking_run['id'] if ranking_run else None

        if content_markdown:  # Only save if we have markdown content
            newsletter_id = db.save_newsletter(
                newsletter_name=args.newsletter_name,
                run_date=args.date,
                content_markdown=content_markdown,
                content_html=content_html,
                template_name=args.template,
                output_format=args.output_format,
                articles_count=len(articles),
                articles_with_content=len([a for a in articles if a.get('full_content')]),
                ranking_run_id=ranking_run_id,
                total_tokens_used=tokens_used,
                generation_duration_seconds=execution_time,
                output_file_md=output_file_md,
                output_file_html=output_file_html,
                context_report_file=context_report_file if 'context_report_file' in locals() else None,
                categories=newsletter_config.get('categories'),
                generation_method='4-step',
                model_summarizer='gpt-4o-mini',
                model_writer='gpt-4o'
            )
            logger.info(f"✓ Newsletter saved to database (ID: {newsletter_id})")
        else:
            logger.warning("No markdown content found, skipping database save")

    except Exception as e:
        logger.error(f"Failed to save newsletter to database: {e}")
        import traceback
        logger.error(traceback.format_exc())

    # Summary
    logger.info("="*80)
    logger.info("STAGE 05 COMPLETED")
    logger.info("="*80)
    logger.info(f"Total articles: {len(articles)}")
    logger.info(f"Execution time: {execution_time:.2f}s")
    logger.info(f"Output files generated: {len(output_files)}")
    for output_file in output_files:
        logger.info(f"  - {output_file}")

    print("\n" + "="*80)
    print("STAGE 05 SUMMARY")
    print("="*80)
    print(f"Newsletter: {args.newsletter_name}")
    print(f"Date: {args.date}")
    print(f"Total articles: {len(articles)}")
    print(f"\nOutput files:")
    for output_file in output_files:
        print(f"  - {output_file}")
    print("="*80)

    # Return metadata for orchestrator
    return {
        "status": "success",
        "urls_used": len(articles),
        "output_files": output_files,
        "tokens_used": tokens_used,
        "execution_time": execution_time
    }


if __name__ == '__main__':
    result = main()
    if isinstance(result, dict):
        # Called from orchestrator or programmatically
        sys.exit(0 if result["status"] == "success" else 1)
    else:
        # Legacy CLI usage
        sys.exit(result)
