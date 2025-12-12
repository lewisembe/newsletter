#!/usr/bin/env python3
"""
Train Supervised Classifier - Entrena clasificadores supervisados sobre embeddings

Este script:
1. Carga URLs clasificadas de la base de datos
2. Genera embeddings usando el modelo configurado
3. Entrena múltiples clasificadores (LR, XGBoost, RF)
4. Evalúa y compara su rendimiento
5. Guarda el mejor modelo
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
from src.supervised_classifier import SupervisedClassifier

# Importar Embedder de poc_clustering
sys.path.insert(0, str(Path(__file__).parent.parent / "poc_clustering" / "src"))
from embedder import Embedder


def load_config(config_path: str = "config.yml") -> dict:
    """Carga configuración desde YAML"""
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def main():
    parser = argparse.ArgumentParser(
        description="Entrenar clasificador supervisado sobre embeddings"
    )
    parser.add_argument(
        "--config",
        type=str,
        default="config.yml",
        help="Path al archivo de configuración",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="models",
        help="Directorio para guardar modelos entrenados",
    )
    parser.add_argument(
        "--test-size",
        type=float,
        default=0.2,
        help="Proporción de datos para test (default: 0.2)",
    )
    parser.add_argument(
        "--models",
        type=str,
        nargs="+",
        default=["logistic_regression", "xgboost"],
        help="Modelos a entrenar (logistic_regression, xgboost, random_forest)",
    )
    parser.add_argument(
        "--max-urls",
        type=int,
        default=None,
        help="Límite de URLs a usar (None = todas)",
    )
    parser.add_argument(
        "--cv-folds",
        type=int,
        default=5,
        help="Número de folds para cross-validation",
    )
    args = parser.parse_args()

    print("=" * 70)
    print("Training Supervised Classifier on Embeddings")
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
    print(f"  Loaded {len(urls)} URLs for training")

    if len(urls) < 100:
        print("❌ Not enough URLs for training. Need at least 100.")
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

    print(f"  Train: {len(X_train)} samples")
    print(f"  Test: {len(X_test)} samples")

    # Verificar distribución estratificada
    train_dist = {}
    test_dist = {}
    for cat in y_train:
        train_dist[cat] = train_dist.get(cat, 0) + 1
    for cat in y_test:
        test_dist[cat] = test_dist.get(cat, 0) + 1

    print(f"\n  Train distribution:")
    for cat in sorted(train_dist.keys()):
        print(f"    {cat}: {train_dist[cat]}")

    print(f"\n  Test distribution:")
    for cat in sorted(test_dist.keys()):
        print(f"    {cat}: {test_dist[cat]}")

    # 4. Entrenar modelos
    print(f"\n🎯 Step 4: Training classifiers...")
    results = {}

    for model_type in args.models:
        print(f"\n{'=' * 70}")
        print(f"Model: {model_type}")
        print(f"{'=' * 70}")

        try:
            # Crear clasificador
            clf = SupervisedClassifier(model_type=model_type)

            # Entrenar con cross-validation
            train_metrics = clf.train(
                X_train, y_train, cv_folds=args.cv_folds, verbose=True
            )

            # Evaluar en test set
            test_metrics = clf.evaluate(X_test, y_test, verbose=True)

            # Guardar modelo
            output_dir = Path(args.output_dir)
            output_dir.mkdir(parents=True, exist_ok=True)
            model_path = output_dir / f"classifier_{model_type}.pkl"
            clf.save(str(model_path))

            # Guardar resultados
            results[model_type] = {
                "train_metrics": train_metrics,
                "test_metrics": test_metrics,
                "model_path": str(model_path),
            }

        except Exception as e:
            print(f"  ❌ Error training {model_type}: {e}")
            import traceback
            traceback.print_exc()
            continue

    # 5. Comparar resultados
    print(f"\n📊 Step 5: Comparison of Results")
    print(f"{'=' * 70}")

    print(f"\n{'Model':<25} {'CV Accuracy':<15} {'Test Accuracy':<15} {'F1 (macro)':<12}")
    print(f"{'-' * 70}")

    best_model = None
    best_accuracy = 0

    for model_type, res in results.items():
        cv_acc = res["train_metrics"].get("cv_mean", 0)
        test_acc = res["test_metrics"]["accuracy"]
        test_f1 = res["test_metrics"]["f1_macro"]

        cv_str = f"{cv_acc:.3f}" if cv_acc else "N/A"
        print(f"{model_type:<25} {cv_str:<15} {test_acc:<15.3f} {test_f1:<12.3f}")

        if test_acc > best_accuracy:
            best_accuracy = test_acc
            best_model = model_type

    if best_model:
        print(f"\n✅ Best model: {best_model} (accuracy: {best_accuracy:.3f})")

        # Copiar mejor modelo como "best_classifier.pkl"
        best_path = Path(results[best_model]["model_path"])
        best_copy = best_path.parent / "best_classifier.pkl"
        import shutil
        shutil.copy(best_path, best_copy)
        print(f"  ✓ Best model copied to: {best_copy}")

    # 6. Resumen final
    execution_time = time.time() - start_time
    print(f"\n{'=' * 70}")
    print(f"✅ TRAINING COMPLETED")
    print(f"  Total time: {execution_time:.1f}s ({execution_time/60:.1f}m)")
    print(f"  Models trained: {len(results)}")
    print(f"  Best accuracy: {best_accuracy:.1%}")
    print(f"  Models saved in: {args.output_dir}")
    print(f"{'=' * 70}")


if __name__ == "__main__":
    main()
