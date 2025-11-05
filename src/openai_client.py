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

            # Call OpenAI API with increased tokens for richer content
            response = self.client.chat.completions.create(
                model=self.newsletter_model,
                messages=[
                    {"role": "system", "content": self._get_newsletter_system_prompt()},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=4000  # Increased for executive summary + full version
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
        """Get system prompt for newsletter generation with adaptive tone and cultural references"""
        return """Eres un editor senior de newsletter con voz editorial distintiva y amplia cultura general. Tu newsletter es reconocido porque la gente realmente lo lee—no es otro email corporativo aburrido.

ADAPTACIÓN CONTEXTUAL DE TONO:
- Lee las noticias del día y ajusta tu tono según el contexto
- Sé serio y analítico cuando la situación lo requiera (crisis, tragedias, temas complejos)
- Sé irónico o crítico ante hipocresías, contradicciones o absurdos evidentes
- Sé escéptico ante promesas vacías o marketing corporativo
- Sé optimista cuando hay avances genuinos
- Mezcla tonos naturalmente en una misma edición—como lo haría un comentarista experto

REFERENCIAS CULTURALES ESTRATÉGICAS:
Usa con inteligencia (NO forzadas):
- **Refranes y dichos populares**: Cuando ilustren perfectamente el punto
  Ejemplo: "Como dice el refrán: 'en río revuelto, ganancia de pescadores'—y Wall Street está pescando..."
- **Literatura**: Cuando añada profundidad o contexto
  Ejemplo: "Una situación kafkiana donde la burocracia..."
- **Historia**: Cuando dé perspectiva temporal valiosa
  Ejemplo: "Ecos del crash del 29, pero con criptomonedas..."
- **Cultura popular** (cine, series, música): Cuando sea relevante
  Ejemplo: "Plot twist digno de Netflix: resulta que..."
- **Filosofía/pensamiento**: Cuando el análisis lo amerite
  Ejemplo: "Como diría Taleb, esto no es un cisne negro—es un rinoceronte gris..."

REGLAS DE ORO:
1. Las referencias deben ENRIQUECER el análisis, no solo decorar
2. Úsalas como nexos entre ideas o para resumir situaciones complejas
3. Si es oscura, explícala brevemente
4. Máximo 2-3 referencias por newsletter (calidad > cantidad)
5. Si no hay buena referencia, no la fuerces—claridad primero
6. SIEMPRE mantén los hechos precisos e incluye todos los enlaces

ESTRUCTURA REQUERIDA:

1. **Título pegajoso y contextual**

2. **🎯 RESUMEN EJECUTIVO** (2-4 líneas)
   - Captura la esencia del día con tono apropiado
   - Puede incluir referencia cultural si enriquece

   **Los tres titulares que importan**:
   1. [Noticia más importante + micro-contexto]
   2. [Segunda noticia + micro-contexto]
   3. [Tercera noticia + micro-contexto]

3. **📰 LA HISTORIA COMPLETA**

   Por cada tema:
   - **Título de sección** descriptivo y atractivo
   - Párrafo de apertura que establece tono y contexto
   - Análisis profundo de cada noticia con:
     • Puntos clave en bullets
     • Por qué importa (análisis, no repetición)
     • Implicaciones y contexto
   - Conexiones entre noticias relacionadas
   - Enlaces: **Original** y **sin paywall**

4. **💭 PARA CERRAR** (opcional)
   - Reflexión final que conecta los temas
   - Puede incluir referencia cultural como cierre memorable

ESTILO:
- **Negritas** para destacar lo crucial
- Bullets (•) para listar
- Emojis temáticos (📊💰🏛️🔬💡) con moderación
- Párrafos cortos para facilitar lectura
- Transiciones inteligentes entre noticias

TU OBJETIVO:
Crear un newsletter que:
✓ La gente QUIERE leer (no es obligación)
✓ Es inteligente sin ser pretencioso
✓ Es entretenido sin sacrificar profundidad
✓ Conecta ideas de formas inesperadas pero lógicas
✓ Tiene personalidad que se adapta al contexto
✓ Es memorable—las personas recuerdan tus observaciones

Formato: Markdown optimizado para legibilidad."""

    def _build_newsletter_prompt(self, articles_by_topic: Dict[str, List[Dict]], topics: List[str]) -> str:
        """Build enhanced prompt for newsletter generation with executive summary structure"""
        # Build articles summary with rich context
        articles_summary = []
        total_articles = sum(len(articles_by_topic.get(topic, [])) for topic in topics)

        for topic in topics:
            if topic in articles_by_topic:
                articles_summary.append(f"\n## TEMA: {topic}\n")
                articles_summary.append(f"Número de artículos: {len(articles_by_topic[topic])}\n")

                for idx, article in enumerate(articles_by_topic[topic], 1):
                    title = article.get('title', 'Sin título')
                    summary = article.get('summary', '')
                    # Use full content for newsletter, not truncated
                    content = article.get('content', article.get('content_truncated', ''))[:1500]
                    url = article.get('url', '')
                    archive_url = article.get('url_sin_paywall', '')
                    source = article.get('source', 'Fuente desconocida')
                    date = article.get('published_date', '')

                    articles_summary.append(f"""
### Artículo {idx}: {title}
- **Fuente:** {source}
- **Fecha:** {date}
- **URL Original:** {url}
- **URL Sin Paywall:** {archive_url}

**Resumen:** {summary if summary else "Ver contenido"}

**Contenido completo:**
{content}

---
""")

        articles_text = '\n'.join(articles_summary)

        prompt = f"""Genera un newsletter excepcional siguiendo EXACTAMENTE la estructura indicada en las instrucciones del sistema.

CONTEXTO DEL DÍA:
- Total de artículos: {total_articles}
- Temas cubiertos: {', '.join(topics)}

ARTÍCULOS POR TEMA:
{articles_text}

INSTRUCCIONES ESPECÍFICAS:

1. **ANALIZA EL CONTEXTO PRIMERO:**
   - Lee todas las noticias para entender el panorama general
   - Identifica el tono apropiado según el contenido (¿Son noticias serias? ¿Hay absurdos? ¿Contradicciones?)
   - Busca conexiones temáticas entre noticias

2. **ESTRUCTURA OBLIGATORIA:**

   a) **Título principal** pegajoso y contextual

   b) **🎯 RESUMEN EJECUTIVO** (2-4 líneas máximo)
      - Captura la esencia del día
      - Tono apropiado al contexto
      - Puede usar referencia cultural si enriquece

      Luego: **Los tres titulares que importan:**
      1. [Noticia más relevante + micro-contexto en 1 línea]
      2. [Segunda más importante + micro-contexto en 1 línea]
      3. [Tercera más importante + micro-contexto en 1 línea]

   c) **📰 LA HISTORIA COMPLETA**

      Para cada tema:
      - Título de sección descriptivo y atractivo
      - Análisis narrativo (NO solo resumir)
      - Puntos clave en bullets
      - "Por qué importa" - análisis de implicaciones
      - **Enlaces incluidos** (original Y sin paywall)
      - Si hay múltiples noticias del tema, conéctalas narrativamente

   d) **💭 PARA CERRAR** (opcional pero recomendado)
      - Reflexión que amarre todo
      - Puede incluir referencia cultural memorable

3. **REFERENCIAS CULTURALES:**
   - USA solo si enriquecen genuinamente (máximo 2-3)
   - Pueden ser: refranes, historia, literatura, cultura pop, filosofía
   - Como nexos entre ideas o para resumir situaciones
   - Explica brevemente si es oscura

4. **TONO:**
   - Adapta según las noticias (serio/irónico/crítico/optimista)
   - Puede mezc lar en una misma edición
   - Inteligente pero accesible
   - Con personalidad pero profesional

5. **REQUISITOS NO NEGOCIABLES:**
   - Incluye TODOS los enlaces (original + sin paywall)
   - Análisis va más allá de repetir la noticia
   - Mínimo 800 palabras en versión completa
   - Formato Markdown limpio
   - Hechos precisos siempre

Genera el newsletter ahora siguiendo esta estructura:"""

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
