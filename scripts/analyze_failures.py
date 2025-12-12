#!/usr/bin/env python3
"""
Analizar por qué fallaron URLs específicas en Stage 04
"""

import sys
import os
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import requests
from bs4 import BeautifulSoup
import json

# URLs que fallaron con "All extraction methods failed"
FAILED_URLS = {
    "El Mundo (directo)": "https://www.elmundo.es/internacional/2025/11/13/69157c691ee97cbdb6bfcc80-directo.html",
    "ABC 1": "https://www.abc.es/internacional/trump-premia-nuevos-aliados-america-latina-acuerdos-20251113232520-nt.html",
    "ABC 2": "https://www.abc.es/internacional/bbc-pide-disculpas-trump-edicion-discurso-motivos-20251113214443-nt.html",
    "Le Monde (live)": "https://www.lemonde.fr/international/live/2025/11/13/en-direct-guerre-en-ukraine-l-ex-president-georgien-mikheil-saakachvili-demande-a-kiev-de-l-inclure-dans-un-echange-de-prisonniers-avec-la-russie_6652765_3210.html",
    "Le Monde (podcast)": "https://www.lemonde.fr/podcasts/article/2025/11/12/dix-ans-du-13-novembre-le-bataclan-raconte-par-ceux-qui-ont-survecu_6653074_5463015.html",
}

def analyze_url(name, url):
    """Analizar una URL fallida"""
    print(f"\n{'='*80}")
    print(f"🔍 {name}")
    print(f"{'='*80}")
    print(f"URL: {url}")

    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers, timeout=10)

        print(f"\n1. FETCH:")
        print(f"   Status: {response.status_code}")
        print(f"   Size: {len(response.text):,} bytes")

        html = response.text
        soup = BeautifulSoup(html, 'lxml')

        # Analizar JSON-LD
        print(f"\n2. JSON-LD:")
        json_ld_scripts = soup.find_all('script', type='application/ld+json')
        print(f"   Scripts encontrados: {len(json_ld_scripts)}")

        if json_ld_scripts:
            for i, script in enumerate(json_ld_scripts[:2]):
                try:
                    data = json.loads(script.string)
                    items = data if isinstance(data, list) else [data]
                    for item in items[:1]:
                        item_type = item.get('@type', 'Unknown')
                        print(f"   [{i+1}] Type: {item_type}")

                        if item_type in ['NewsArticle', 'Article', 'LiveBlogPosting']:
                            article_body = item.get('articleBody', '')
                            if article_body:
                                print(f"       ✅ articleBody: {len(article_body)} chars")
                            else:
                                print(f"       ❌ articleBody: VACÍO")

                            # Campos especiales
                            if item_type == 'LiveBlogPosting':
                                print(f"       🔴 LIVE BLOG (contenido dinámico)")
                                coverage = item.get('liveBlogUpdate', [])
                                print(f"       Updates: {len(coverage) if isinstance(coverage, list) else 'N/A'}")

                except Exception as e:
                    print(f"   Error parsing JSON-LD: {e}")

        # Buscar paywall
        print(f"\n3. PAYWALL CHECK:")
        paywall_keywords = ['suscr', 'paywall', 'premium', 'exclusivo', 'abonné']
        text_lower = html.lower()
        found = [kw for kw in paywall_keywords if kw in text_lower]

        if found:
            print(f"   ⚠️  Palabras de paywall: {found[:3]}")

            # Ver si hay señal explícita de paywall
            if 'isAccessibleForFree' in html:
                print(f"   ℹ️  Campo 'isAccessibleForFree' presente en JSON-LD")
        else:
            print(f"   ✅ No hay señales obvias de paywall")

        # Analizar estructura
        print(f"\n4. ESTRUCTURA HTML:")

        # Tipo de contenido
        if '/live/' in url or '/directo' in url:
            print(f"   📺 Tipo: LIVE BLOG / DIRECTO")
        elif '/podcast' in url:
            print(f"   🎙️  Tipo: PODCAST")
        elif '/video' in url:
            print(f"   🎬 Tipo: VIDEO")
        else:
            print(f"   📄 Tipo: ARTÍCULO ESTÁNDAR")

        # Contar párrafos
        paragraphs = soup.find_all('p')
        print(f"   Párrafos <p>: {len(paragraphs)}")

        if paragraphs:
            total_text = ' '.join([p.get_text(strip=True) for p in paragraphs[:10]])
            word_count = len(total_text.split())
            print(f"   Palabras en primeros 10 <p>: {word_count}")

        # Texto visible total
        for tag in soup(['script', 'style', 'noscript']):
            tag.decompose()
        visible = soup.get_text(separator=' ', strip=True)
        visible_words = len(visible.split())
        print(f"   Palabras totales (texto visible): {visible_words}")

        print(f"\n5. DIAGNÓSTICO:")

        # Determinar causa
        if '/live/' in url or '/directo' in url:
            print(f"   🔴 CAUSA: Contenido LIVE/DIRECTO")
            print(f"      - Actualización continua")
            print(f"      - newspaper3k/readability no diseñados para live blogs")
            print(f"      - JSON-LD usa LiveBlogPosting (estructura diferente)")

        elif '/podcast' in url:
            print(f"   🎙️  CAUSA: Contenido PODCAST")
            print(f"      - Principalmente audio, no texto")
            print(f"      - Descripción mínima")

        elif found and 'isAccessibleForFree' in html:
            print(f"   🔒 CAUSA: PAYWALL")
            print(f"      - Requiere suscripción")
            print(f"      - Necesita cookies autenticadas")

        elif visible_words < 200:
            print(f"   ⚠️  CAUSA: Contenido insuficiente")
            print(f"      - Muy poco texto extraíble")
            print(f"      - Posible página especial (galería, infografía, etc.)")

        else:
            print(f"   ❓ CAUSA: Estructura HTML compleja")
            print(f"      - newspaper3k/readability no detectan contenido")
            print(f"      - Requiere extractor específico o LLM XPath")

    except Exception as e:
        print(f"\n❌ Error: {e}")


def main():
    print(f"{'='*80}")
    print(f"🔍 ANÁLISIS DE URLS QUE FALLARON EN STAGE 04")
    print(f"{'='*80}")

    for name, url in FAILED_URLS.items():
        try:
            analyze_url(name, url)
        except KeyboardInterrupt:
            print("\n⚠️  Interrumpido")
            break

    print(f"\n{'='*80}")
    print(f"✅ ANÁLISIS COMPLETADO")
    print(f"{'='*80}")


if __name__ == "__main__":
    main()
