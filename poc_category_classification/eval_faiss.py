#!/usr/bin/env python3
"""
Evaluate FAISS KNN Classifier - Evalúa clasificador KNN con FAISS

Similar a train_classifier.py pero usando KNN en lugar de supervised learning.
No requiere training, solo indexa los embeddings existentes.
"""

import argparse
import time
import yaml
import sys
from pathlib import Path
from datetime import datetime
import numpy as np
from sklearn.model_selection import train_test_split

# Imports locales
from src.db_loader import DBLoader
from src.faiss_classifier import FAISSClassifier

# Importar Embedder de poc_clustering
sys.path.insert(0, str(Path(__file__).parent.parent / "poc_clustering" / "src"))
from embedder import Embedder


def load_config(config_path: str = "config.yml") -> dict:
    """Carga configuración desde YAML"""
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def main():
    parser = argparse.ArgumentParser(
        description="Evaluar clasificador FAISS KNN"
    )
    parser.add_argument(
        "--config",
        type=str,
        default="config.yml",
        help="Path al archivo de configuración",
    )
    parser.add_argument(
        "--test-size",
        type=float,
        default=0.2,
        help="Proporción de datos para test (default: 0.2)",
    )
    parser.add_argument(
        "--k",
        type=int,
        default=5,
        help="Número de vecinos K (default: 5)",
    )
    parser.add_argument(
        "--distance",
        type=str,
        choices=["cosine", "l2"],
        default="cosine",
        help="Métrica de distancia (default: cosine)",
    )
    parser.add_argument(
        "--max-urls",
        type=int,
        default=None,
        help="Límite de URLs a usar (None = todas)",
    )
    args = parser.parse_args()

    print("=" * 70)
    print("FAISS KNN Classifier Evaluation")
    print("=" * 70)

    start_time = time.time()

    # Cargar configuración
    print(f"\n📄 Loading config: {args.config}")
    config = load_config(args.config)

    # Resolver paths
    db_path = Path(__file__).parent / config["database"]["path"]

    # 1. Cargar URLs clasificadas
    print(f"\n📦 Step 1: Loading classified URLs from database...")
    db_loader = DBLoader(str(db_path))

    # Estadísticas generales
    stats = db_loader.get_classification_stats()
    print(f"  Total URLs in DB: {stats['total_urls']}")
    print(f"  Classified URLs: {stats['total_classified']}")

    # Cargar URLs
    max_urls = args.max_urls if args.max_urls else None
    urls = db_loader.load_classified_urls(
        max_urls=max_urls,
        require_categoria=True,
    )
    print(f"  Loaded {len(urls)} URLs for evaluation")

    if len(urls) < 100:
        print("❌ Not enough URLs for evaluation. Need at least 100.")
        return

    # Distribución de categorías
    category_counts = {}
    for url in urls:
        cat = url["categoria_tematica"]
        category_counts[cat] = category_counts.get(cat, 0) + 1

    print(f"\n  Category distribution:")
    for cat, count in sorted(category_counts.items(), key=lambda x: x[1], reverse=True):
        print(f"    {cat}: {count}")

    # 2. Generar embeddings
    print(f"\n🤖 Step 2: Generating embeddings...")
    model_config = config["model"]

    embedder = Embedder(
        model_name=model_config["name"],
        cache_dir=str(Path(__file__).parent / model_config["cache_dir"]),
        device=model_config["device"],
        batch_size=model_config["batch_size"],
    )

    titles = [url["title"] for url in urls]
    categories = [url["categoria_tematica"] for url in urls]

    print(f"  Embedding {len(titles)} titles...")
    embeddings = embedder.embed(titles, show_progress=True)
    print(f"  Embeddings shape: {embeddings.shape}")

    # 3. Split train/test
    print(f"\n📊 Step 3: Splitting train/test ({args.test_size:.0%} test)...")
    X_train, X_test, y_train, y_test = train_test_split(
        embeddings,
        categories,
        test_size=args.test_size,
        stratify=categories,
        random_state=42,
    )

    print(f"  Train: {len(X_train)} samples (will be indexed)")
    print(f"  Test: {len(X_test)} samples (will query index)")

    # 4. Construir índice FAISS
    print(f"\n🎯 Step 4: Building FAISS index...")
    clf = FAISSClassifier(k=args.k, distance_metric=args.distance)

    index_start = time.time()
    clf.fit(X_train, y_train)
    index_time = time.time() - index_start
    print(f"  Index built in {index_time:.2f}s")

    # 5. Evaluar
    print(f"\n📊 Step 5: Evaluating on test set...")
    eval_start = time.time()
    metrics = clf.evaluate(X_test, y_test, verbose=True)
    eval_time = time.time() - eval_start
    print(f"  Evaluation completed in {eval_time:.2f}s")
    print(f"  Speed: {len(X_test) / eval_time:.1f} predictions/second")

    # 6. Análisis detallado de algunos ejemplos
    print(f"\n🔍 Step 6: Sample predictions (first 5)...")
    results = clf.predict_with_neighbors(X_test[:5])

    for i, (result, true_label) in enumerate(zip(results, y_test[:5])):
        pred = result['prediction']
        conf = result['confidence']
        correct = "✓" if pred == true_label else "✗"

        print(f"\n  [{i+1}] {correct} Prediction: {pred} (confidence: {conf:.2f}) | True: {true_label}")
        print(f"      Vote distribution: {result['vote_distribution']}")
        print(f"      Neighbors:")
        for n in result['neighbors'][:3]:
            print(f"        - {n['label']} (distance: {n['distance']:.3f})")

    # 7. Resumen final
    execution_time = time.time() - start_time
    print(f"\n{'=' * 70}")
    print(f"✅ EVALUATION COMPLETED")
    print(f"  Total time: {execution_time:.1f}s ({execution_time/60:.1f}m)")
    print(f"  Index time: {index_time:.2f}s")
    print(f"  Eval time: {eval_time:.2f}s")
    print(f"")
    print(f"  Test Accuracy: {metrics['accuracy']:.1%}")
    print(f"  F1-Score: {metrics['f1_macro']:.3f}")
    print(f"  Avg Confidence: {metrics['avg_confidence']:.3f}")
    print(f"")
    print(f"  K neighbors: {args.k}")
    print(f"  Distance metric: {args.distance}")
    print(f"  Model: {model_config['name']}")
    print(f"{'=' * 70}")


if __name__ == "__main__":
    main()
