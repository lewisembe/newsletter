"""
Hashtag Generator - Generación de hashtags descriptivos usando LLM
"""

import os
import re
from typing import List, Optional
from openai import OpenAI

# Note: .env is loaded by the main script (stages/01_extract_urls.py)
# No need to load it here to avoid path resolution issues


class HashtagGenerator:
    """Genera hashtags descriptivos para clusters usando LLM"""

    def __init__(
        self,
        model: str = "gpt-4o-mini",
        temperature: float = 0.3,
        max_tokens: int = 50,
    ):
        """
        Args:
            model: Modelo de OpenAI a usar
            temperature: Temperatura para generación (0-1)
            max_tokens: Máximo de tokens a generar
        """
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens

        # Inicializar cliente OpenAI (opcional)
        api_key = os.getenv("OPENAI_API_KEY")
        self.client = None
        if api_key:
            try:
                self.client = OpenAI(api_key=api_key)
            except Exception as exc:
                print(f"⚠️  No se pudo inicializar OpenAI ({exc}). Se usará modo fallback.")
        else:
            print("ℹ️  OPENAI_API_KEY no definido. Hashtags usarán modo fallback.")

    def generate(
        self,
        titles: List[str],
        max_titles: int = 5,
    ) -> str:
        """
        Genera hashtag para un cluster de noticias.

        Args:
            titles: Lista de titulares del cluster
            max_titles: Máximo de titulares a enviar al LLM

        Returns:
            Hashtag generado (ej: "#ReformaFiscalSanchez")
        """
        if not titles:
            return "#Unknown"

        # Limitar número de titulares para no saturar el prompt
        sample_titles = titles[:max_titles]

        # Construir prompt
        prompt = self._build_prompt(sample_titles)

        if self.client:
            try:
                # Llamar a OpenAI
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {
                            "role": "system",
                            "content": "Eres un experto en análisis de noticias. Tu tarea es generar hashtags concisos y descriptivos.",
                        },
                        {"role": "user", "content": prompt},
                    ],
                    temperature=self.temperature,
                    max_tokens=self.max_tokens,
                )

                hashtag = response.choices[0].message.content.strip()

                # Limpiar y validar hashtag
                hashtag = self._clean_hashtag(hashtag)

                return hashtag

            except Exception as e:
                print(f"Error generating hashtag with LLM: {e}")
                # Continuar con fallback

        # Fallback: usar extracción simple
        return self._fallback_hashtag(sample_titles)

    def _build_prompt(self, titles: List[str]) -> str:
        """Construye el prompt para el LLM"""
        titles_str = "\n".join([f"- {title}" for title in titles])

        prompt = f"""Analiza estos titulares de noticias que hablan sobre el mismo evento o historia:

{titles_str}

Genera UN SOLO hashtag descriptivo que capture el tema central común.

REQUISITOS:
- Formato: #PalabrasClave (sin espacios, CamelCase)
- Máximo 3 palabras
- Debe ser específico y descriptivo
- En español si los titulares son en español
- NO incluir explicaciones, SOLO el hashtag

EJEMPLOS:
- #ReformaFiscal
- #CumbreG20Madrid
- #SancionesRusia
- #HuelgaTransporte

HASHTAG:"""

        return prompt

    def _clean_hashtag(self, hashtag: str) -> str:
        """
        Limpia y valida el hashtag generado.

        Args:
            hashtag: Hashtag raw del LLM

        Returns:
            Hashtag limpio
        """
        # Remover espacios y saltos de línea
        hashtag = hashtag.strip()

        # Extraer primer hashtag si hay múltiples
        hashtag_match = re.search(r"#\w+", hashtag)
        if hashtag_match:
            hashtag = hashtag_match.group(0)
        else:
            # Si no tiene #, añadirlo
            hashtag = "#" + re.sub(r"[^\w]", "", hashtag)

        # Limitar longitud
        if len(hashtag) > 30:
            hashtag = hashtag[:30]

        # Si quedó vacío, usar default
        if hashtag == "#":
            hashtag = "#News"

        return hashtag

    def _fallback_hashtag(self, titles: List[str]) -> str:
        """
        Genera hashtag simple sin LLM (fallback).

        Extrae las palabras más comunes (excluyendo stopwords) y las convierte en hashtag.

        Args:
            titles: Lista de titulares

        Returns:
            Hashtag generado
        """
        # Stopwords comunes en español
        stopwords = {
            "el", "la", "los", "las", "un", "una", "de", "del", "y", "en",
            "para", "por", "con", "sin", "sobre", "tras", "entre", "a",
            "ante", "desde", "hasta", "se", "es", "su", "sus", "que", "como",
        }

        # Contar palabras
        word_counts = {}
        for title in titles:
            words = re.findall(r"\b\w+\b", title.lower())
            for word in words:
                if word not in stopwords and len(word) > 3:
                    word_counts[word] = word_counts.get(word, 0) + 1

        # Obtener top 2 palabras
        if not word_counts:
            return "#News"

        top_words = sorted(word_counts.items(), key=lambda x: x[1], reverse=True)[:2]
        hashtag_words = [word.capitalize() for word, _ in top_words]
        hashtag = "#" + "".join(hashtag_words)

        return hashtag


if __name__ == "__main__":
    # Test
    print("Testing HashtagGenerator...")

    generator = HashtagGenerator(
        model="gpt-4o-mini",
        temperature=0.3,
    )

    # Test con titulares de ejemplo
    test_clusters = [
        [
            "Sánchez anuncia nueva reforma fiscal para 2026",
            "El Gobierno presenta su plan de reforma tributaria",
            "Hacienda aprueba cambios en IRPF y sociedades",
        ],
        [
            "Apple lanza nuevo iPhone 16 con IA integrada",
            "La nueva generación de iPhone llega a España",
            "iPhone 16: características y precio oficial",
        ],
        [
            "El Madrid gana la Champions League por decimoquinta vez",
            "Ancelotti celebra su quinta Champions como entrenador",
            "La final de la Champions bate récords de audiencia",
        ],
    ]

    print("\nGenerating hashtags:")
    for i, titles in enumerate(test_clusters, 1):
        print(f"\nCluster {i}:")
        for title in titles:
            print(f"  - {title}")

        hashtag = generator.generate(titles)
        print(f"  → {hashtag}")

    # Test fallback
    print("\n\nTesting fallback (without LLM):")
    test_fallback = HashtagGenerator(model="invalid")
    fallback_hashtag = test_fallback._fallback_hashtag(test_clusters[0])
    print(f"Fallback hashtag: {fallback_hashtag}")
