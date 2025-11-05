"""
OpenAI Client Module
Handles article classification and newsletter generation using OpenAI API
"""
from openai import OpenAI
import logging
from typing import List, Dict, Optional
import json

from config import settings

logger = logging.getLogger(__name__)


class OpenAIClient:
    """Client for OpenAI API operations"""

    def __init__(self):
        """Initialize OpenAI client"""
        self.client = OpenAI(api_key=settings.OPENAI_API_KEY)
        self.classification_model = settings.CLASSIFICATION_MODEL
        self.newsletter_model = settings.NEWSLETTER_MODEL

    def classify_article(self, article: Dict, available_topics: List[str]) -> str:
        """
        Classify an article into one of the predefined topics

        Args:
            article: Article dictionary with 'title' and 'content_truncated'
            available_topics: List of available topic names

        Returns:
            Topic name (one of the available topics)
        """
        title = article.get('title', '')
        content = article.get('content_truncated', '')

        if not title or not available_topics:
            logger.warning("Cannot classify: missing title or topics")
            return 'Sin Clasificar'

        try:
            # Construct prompt
            prompt = self._build_classification_prompt(title, content, available_topics)

            # Call OpenAI API
            response = self.client.chat.completions.create(
                model=self.classification_model,
                messages=[
                    {"role": "system", "content": "Eres un experto clasificador de noticias. Clasifica artículos en las categorías proporcionadas."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=50
            )

            # Extract classification
            classification = response.choices[0].message.content.strip()

            # Validate that classification is one of the available topics
            if classification in available_topics:
                logger.info(f"Classified '{title[:50]}' as '{classification}'")
                return classification
            else:
                # Try to find closest match
                classification_lower = classification.lower()
                for topic in available_topics:
                    if topic.lower() in classification_lower or classification_lower in topic.lower():
                        logger.info(f"Matched '{classification}' to '{topic}'")
                        return topic

                logger.warning(f"Classification '{classification}' not in available topics, using first topic")
                return available_topics[0] if available_topics else 'Sin Clasificar'

        except Exception as e:
            logger.error(f"Error classifying article: {e}")
            return available_topics[0] if available_topics else 'Sin Clasificar'

    def _build_classification_prompt(self, title: str, content: str, topics: List[str]) -> str:
        """Build prompt for classification"""
        topics_str = '\n'.join([f"- {topic}" for topic in topics])

        prompt = f"""Clasifica el siguiente artículo en UNA de estas categorías:

{topics_str}

Título: {title}

Contenido: {content[:800]}

Responde SOLO con el nombre exacto de la categoría, sin explicaciones adicionales."""

        return prompt

    def classify_articles_batch(self, articles: List[Dict], available_topics: List[str]) -> List[Dict]:
        """
        Classify multiple articles (adds 'tema' field to each)

        Args:
            articles: List of article dictionaries
            available_topics: List of available topic names

        Returns:
            List of articles with 'tema' field added
        """
        for article in articles:
            topic = self.classify_article(article, available_topics)
            article['tema'] = topic

        return articles

    def generate_newsletter(self, articles: List[Dict], topics: List[str]) -> str:
        """
        Generate a newsletter from classified articles

        Args:
            articles: List of classified articles with 'tema' field
            topics: List of topic names

        Returns:
            Generated newsletter content (HTML/Markdown)
        """
        if not articles:
            logger.warning("No articles to generate newsletter from")
            return "No hay artículos disponibles para esta edición."

        try:
            # Group articles by topic
            articles_by_topic = self._group_articles_by_topic(articles)

            # Build prompt
            prompt = self._build_newsletter_prompt(articles_by_topic, topics)

            # Call OpenAI API
            response = self.client.chat.completions.create(
                model=self.newsletter_model,
                messages=[
                    {"role": "system", "content": self._get_newsletter_system_prompt()},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=3000
            )

            # Extract newsletter
            newsletter = response.choices[0].message.content.strip()

            logger.info(f"Generated newsletter with {len(articles)} articles")

            return newsletter

        except Exception as e:
            logger.error(f"Error generating newsletter: {e}")
            return f"Error al generar newsletter: {e}"

    def _group_articles_by_topic(self, articles: List[Dict]) -> Dict[str, List[Dict]]:
        """Group articles by their topic"""
        grouped = {}

        for article in articles:
            topic = article.get('tema', 'Sin Clasificar')
            if topic not in grouped:
                grouped[topic] = []
            grouped[topic].append(article)

        return grouped

    def _get_newsletter_system_prompt(self) -> str:
        """Get system prompt for newsletter generation"""
        return """Eres un editor experto de newsletters financieras y de negocios. Tu trabajo es crear newsletters elegantes, informativas y fáciles de leer.

Características de tu estilo:
- Narrativo pero conciso (resumen ejecutivo)
- Uso estratégico de **negritas** para destacar puntos clave
- Bullets (•) para listar detalles importantes
- Lenguaje profesional pero accesible
- Conectas las noticias cuando hay relación temática
- Incluyes contexto relevante sin ser repetitivo

Estructura:
1. Título atractivo de la newsletter
2. Breve introducción (2-3 líneas)
3. Secciones por tema con:
   - Título de sección en negrita
   - Narrativa que conecta las noticias del tema
   - Detalles clave en bullets
   - Enlaces a las fuentes
4. Cierre breve (opcional)

Formato: Markdown para fácil lectura."""

    def _build_newsletter_prompt(self, articles_by_topic: Dict[str, List[Dict]], topics: List[str]) -> str:
        """Build prompt for newsletter generation"""
        # Build articles summary
        articles_summary = []

        for topic in topics:
            if topic in articles_by_topic:
                articles_summary.append(f"\n## {topic}\n")

                for article in articles_by_topic[topic]:
                    title = article.get('title', 'Sin título')
                    summary = article.get('summary', '')
                    # Use full content for newsletter, not truncated
                    content = article.get('content', article.get('content_truncated', ''))[:1000]
                    url = article.get('url', '')
                    archive_url = article.get('url_sin_paywall', '')
                    source = article.get('source', 'Fuente desconocida')
                    date = article.get('published_date', '')

                    articles_summary.append(f"""
### {title}
**Fuente:** {source} | **Fecha:** {date}
**URL Original:** {url}
**URL Sin Paywall:** {archive_url}

**Resumen:** {summary}

**Contenido:** {content}

---
""")

        articles_text = '\n'.join(articles_summary)

        prompt = f"""Genera una newsletter profesional y elegante basada en los siguientes artículos de noticias, agrupados por tema.

{articles_text}

IMPORTANTE:
- Crea una narrativa cohesiva para cada sección temática
- Usa **negritas** para destacar información clave
- Usa bullets (•) para listar detalles importantes
- Incluye todos los enlaces (tanto original como sin paywall)
- El tono debe ser de resumen ejecutivo: conciso pero informativo
- Conecta las noticias cuando tengan relación
- No copies textualmente el contenido, sintetiza los puntos clave

Genera la newsletter ahora:"""

        return prompt

    def extract_date_with_ai(self, html_content: str) -> Optional[str]:
        """
        Extract publication date from HTML using AI (fallback method)

        Args:
            html_content: HTML snippet containing potential date information

        Returns:
            Date string or None
        """
        try:
            prompt = f"""Extrae la fecha de publicación del siguiente HTML.
Responde SOLO con la fecha en formato YYYY-MM-DD HH:MM:SS o YYYY-MM-DD.
Si no encuentras la fecha, responde "NO_ENCONTRADA".

HTML:
{html_content[:1000]}

Fecha:"""

            response = self.client.chat.completions.create(
                model=self.classification_model,
                messages=[
                    {"role": "system", "content": "Eres un extractor de fechas experto."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                max_tokens=50
            )

            date_str = response.choices[0].message.content.strip()

            if date_str and date_str != "NO_ENCONTRADA":
                logger.info(f"Extracted date with AI: {date_str}")
                return date_str

        except Exception as e:
            logger.error(f"Error extracting date with AI: {e}")

        return None


# Convenience functions
def get_client() -> OpenAIClient:
    """Get an OpenAIClient instance"""
    return OpenAIClient()


if __name__ == '__main__':
    # Test OpenAI client
    client = OpenAIClient()

    # Test classification
    test_article = {
        'title': 'Fed Raises Interest Rates by 0.5%',
        'content_truncated': 'The Federal Reserve announced today a significant interest rate hike...'
    }

    test_topics = ['Economía', 'Política', 'Tecnología', 'Negocios']

    print("Testing classification...")
    classification = client.classify_article(test_article, test_topics)
    print(f"Classification: {classification}")
