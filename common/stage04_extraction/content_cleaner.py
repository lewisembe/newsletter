"""
Content Cleaner

Cleans extracted article content by removing boilerplate, ads, and noise.

Adapted from: old/newsletter_bot/src/content_processor.py
Author: Newsletter Utils Team
Created: 2025-11-13
"""

import re
import logging

logger = logging.getLogger(__name__)


def clean_content(content: str, max_length: int = None) -> str:
    """
    Clean extracted article content.

    Removes:
    - Excessive whitespace
    - Newsletter subscription prompts
    - Social media calls-to-action
    - Copyright notices
    - Common boilerplate patterns

    Args:
        content: Raw extracted content
        max_length: Optional maximum character length (truncates at sentence boundary)

    Returns:
        Cleaned content string
    """
    if not content:
        return ''

    # Remove excessive whitespace (multiple spaces/newlines → single space)
    content = re.sub(r'\s+', ' ', content)

    # Remove common boilerplate patterns
    boilerplate_patterns = [
        # Newsletter prompts
        r'Suscr[ií]bete.*?(?=\.|$)',
        r'Subscribe to.*?(?=\.|$)',
        r'Sign up for.*?(?=\.|$)',
        r'Regístrate.*?(?=\.|$)',
        r'Newsletter.*?(?=\.|$)',

        # Social media
        r'Follow us on.*?(?=\.|$)',
        r'Síguenos en.*?(?=\.|$)',
        r'Share this article.*?(?=\.|$)',
        r'Comparte este artículo.*?(?=\.|$)',

        # Copyright/legal
        r'Copyright \d{4}.*?(?=\.|$)',
        r'All rights reserved.*?(?=\.|$)',
        r'Todos los derechos reservados.*?(?=\.|$)',
        r'©.*?\d{4}.*?(?=\.|$)',

        # Cookie/tracking notices
        r'This website uses cookies.*?(?=\.|$)',
        r'Este sitio usa cookies.*?(?=\.|$)',
        r'We use cookies.*?(?=\.|$)',
        r'Usamos cookies.*?(?=\.|$)',

        # Ad markers
        r'Advertisement.*?(?=\.|$)',
        r'Publicidad.*?(?=\.|$)',
        r'Sponsored content.*?(?=\.|$)',
        r'Contenido patrocinado.*?(?=\.|$)',

        # Related links
        r'Related articles.*?(?=\.|$)',
        r'Artículos relacionados.*?(?=\.|$)',
        r'You might also like.*?(?=\.|$)',
        r'También te puede interesar.*?(?=\.|$)',

        # Read more prompts
        r'Read more:.*?(?=\.|$)',
        r'Lee más:.*?(?=\.|$)',
        r'Continue reading.*?(?=\.|$)',
        r'Continúa leyendo.*?(?=\.|$)',
    ]

    for pattern in boilerplate_patterns:
        content = re.sub(pattern, '', content, flags=re.IGNORECASE)

    # Remove URLs (they clutter content)
    content = re.sub(r'https?://\S+', '', content)

    # Remove email addresses
    content = re.sub(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', '', content)

    # Normalize punctuation spacing
    content = re.sub(r'\s+([.,!?;:])', r'\1', content)  # Remove space before punctuation
    content = re.sub(r'([.,!?;:])\s*', r'\1 ', content)  # Ensure space after punctuation

    # Remove multiple consecutive punctuation
    content = re.sub(r'([.,!?;:]){2,}', r'\1', content)

    # Trim whitespace
    content = content.strip()

    # Truncate if max_length specified
    if max_length and len(content) > max_length:
        content = truncate_at_sentence(content, max_length)

    logger.debug(f"Cleaned content: {len(content)} chars")
    return content


def truncate_at_sentence(text: str, max_chars: int) -> str:
    """
    Truncate text at sentence boundary near max_chars.

    Finds the last sentence ending (. ! ?) within the limit
    and cuts there for cleaner truncation.

    Args:
        text: Text to truncate
        max_chars: Maximum character limit

    Returns:
        Truncated text ending at sentence boundary
    """
    if len(text) <= max_chars:
        return text

    # Truncate roughly at limit
    truncated = text[:max_chars]

    # Find last sentence ending
    last_period = max(
        truncated.rfind('.'),
        truncated.rfind('!'),
        truncated.rfind('?')
    )

    # If we found a sentence ending in the last 20% of truncated text, use it
    if last_period > max_chars * 0.8:
        return truncated[:last_period + 1].strip()

    # Otherwise, just truncate with ellipsis
    return truncated.strip() + '...'


def remove_html_artifacts(text: str) -> str:
    """
    Remove common HTML artifacts that slip through extractors.

    Cleans:
    - HTML entities (&nbsp;, &amp;, etc.)
    - Inline CSS/JavaScript fragments
    - HTML comments

    Args:
        text: Text potentially containing HTML artifacts

    Returns:
        Cleaned text
    """
    import html

    # Decode HTML entities
    text = html.unescape(text)

    # Remove HTML comments
    text = re.sub(r'<!--.*?-->', '', text, flags=re.DOTALL)

    # Remove inline styles
    text = re.sub(r'style="[^"]*"', '', text, flags=re.IGNORECASE)

    # Remove script fragments
    text = re.sub(r'<script.*?</script>', '', text, flags=re.DOTALL | re.IGNORECASE)

    # Remove any remaining HTML tags
    text = re.sub(r'<[^>]+>', '', text)

    return text


def normalize_whitespace(text: str) -> str:
    """
    Normalize whitespace while preserving paragraph structure.

    Converts:
    - Multiple spaces → single space
    - Multiple newlines → double newline (paragraph break)

    Args:
        text: Text to normalize

    Returns:
        Text with normalized whitespace
    """
    # Preserve paragraph breaks (2+ newlines)
    text = re.sub(r'\n{3,}', '\n\n', text)

    # Single newlines become spaces
    text = re.sub(r'(?<!\n)\n(?!\n)', ' ', text)

    # Multiple spaces become single space
    text = re.sub(r' {2,}', ' ', text)

    # Trim lines
    lines = [line.strip() for line in text.split('\n')]
    text = '\n'.join(lines)

    return text.strip()
