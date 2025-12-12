#!/usr/bin/env python3
"""
PoC Category Classification - Script principal

Clasifica titulares usando embeddings y compara con clasificación LLM.
Genera informe markdown con métricas y análisis.
"""

import argparse
import time
import yaml
from datetime import datetime
from pathlib import Path
import sys
import tracemalloc

# Importar módulos del PoC
from src.db_loader import DBLoader
from src.comparison_analyzer import ComparisonAnalyzer

# Importar Embedder de poc_clustering
sys.path.insert(0, str(Path(__file__).parent.parent / "poc_clustering" / "src"))
from embedder import Embedder

# Importar CategoryClassifier local
from src.category_classifier import CategoryClassifier


def load_config(config_path: str = "config.yml") -> dict:
    """Carga configuración desde YAML"""
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def format_time(seconds: float) -> str:
    """Formatea tiempo en formato legible"""
    if seconds < 60:
        return f"{seconds:.1f}s"
    elif seconds < 3600:
        mins = int(seconds // 60)
        secs = int(seconds % 60)
        return f"{mins}m {secs}s"
    else:
        hours = int(seconds // 3600)
        mins = int((seconds % 3600) // 60)
        return f"{hours}h {mins}m"


def format_memory(bytes_used: int) -> str:
    """Formatea memoria en MB"""
    mb = bytes_used / (1024 * 1024)
    return f"{mb:.1f} MB"


def generate_markdown_report(
    analyzer: ComparisonAnalyzer,
    config: dict,
    stats: dict,
    output_path: str,
):
    """
    Genera informe markdown con resultados de la comparación.

    Args:
        analyzer: ComparisonAnalyzer con resultados
        config: Configuración
        stats: Estadísticas de ejecución
        output_path: Path al archivo de salida
    """
    lines = []

    # Header
    lines.append("# 📊 Informe de Clasificación por Categorías")
    lines.append(f"**Método:** Embeddings vs LLM (ground truth)")
    lines.append(f"**Modelo:** {config['model']['name']}")
    lines.append(f"**Generado:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append("")
    lines.append("---")
    lines.append("")

    # Resumen ejecutivo
    lines.append("## 📈 Resumen Ejecutivo")
    lines.append("")
    metrics = analyzer.get_metrics()
    lines.append(f"- **Total de URLs analizadas:** {metrics['total_samples']}")
    lines.append(f"- **Accuracy:** {metrics['accuracy']:.2%}")
    lines.append(f"- **Precision (macro):** {metrics['precision_macro']:.3f}")
    lines.append(f"- **Recall (macro):** {metrics['recall_macro']:.3f}")
    lines.append(f"- **F1-Score (macro):** {metrics['f1_macro']:.3f}")
    lines.append("")

    correct = sum(1 for r in analyzer.results if r["correct"])
    incorrect = metrics['total_samples'] - correct
    lines.append(f"- **Correctos:** {correct} ({correct/metrics['total_samples']*100:.1f}%)")
    lines.append(f"- **Incorrectos:** {incorrect} ({incorrect/metrics['total_samples']*100:.1f}%)")
    lines.append("")
    lines.append("---")
    lines.append("")

    # Métricas por categoría
    lines.append("## 📊 Métricas por Categoría")
    lines.append("")
    per_cat_metrics = analyzer.get_per_category_metrics()

    lines.append("| Categoría | Precision | Recall | F1-Score | Support |")
    lines.append("|-----------|-----------|--------|----------|---------|")
    for cat in sorted(per_cat_metrics.keys()):
        m = per_cat_metrics[cat]
        lines.append(
            f"| {cat:12} | {m['precision']:.3f} | {m['recall']:.3f} | "
            f"{m['f1']:.3f} | {m['support']:4d} |"
        )
    lines.append("")
    lines.append("---")
    lines.append("")

    # Matriz de confusión
    lines.append("## 🔍 Matriz de Confusión")
    lines.append("")
    cm, labels = analyzer.get_confusion_matrix()

    # Tabla markdown
    header = "| Verdadero \\ Predicho | " + " | ".join(labels) + " |"
    separator = "|" + "|".join(["-" * 10 for _ in range(len(labels) + 1)]) + "|"
    lines.append(header)
    lines.append(separator)
    for i, true_label in enumerate(labels):
        row = f"| {true_label:12} |"
        for j in range(len(labels)):
            row += f" {cm[i][j]:4d} |"
        lines.append(row)
    lines.append("")
    lines.append("---")
    lines.append("")

    # Patrones de confusión
    lines.append("## ⚠️ Patrones de Confusión Más Frecuentes")
    lines.append("")
    confusion_patterns = analyzer.get_confusion_patterns()
    if confusion_patterns:
        for llm_cat, emb_cat, count in confusion_patterns[:10]:
            lines.append(f"- **{llm_cat} → {emb_cat}:** {count} casos")
        lines.append("")
    else:
        lines.append("No hay errores de clasificación.")
        lines.append("")
    lines.append("---")
    lines.append("")

    # Análisis de errores con ejemplos
    if config["comparison"]["error_analysis"]["include_examples"]:
        lines.append("## 📝 Ejemplos de Errores de Clasificación")
        lines.append("")
        max_examples = config["comparison"]["error_analysis"]["max_examples_per_error"]
        errors = analyzer.get_error_analysis(max_examples_per_error=max_examples)

        if errors:
            for error_type, examples in sorted(errors.items())[:10]:
                lines.append(f"### {error_type}")
                lines.append("")
                for i, ex in enumerate(examples, 1):
                    lines.append(f"{i}. **{ex['title']}**")
                    lines.append(f"   Confianza: {ex['confidence']:.3f}")
                    lines.append("")
                lines.append("---")
                lines.append("")
        else:
            lines.append("No hay errores de clasificación para mostrar.")
            lines.append("")
            lines.append("---")
            lines.append("")

    # Estadísticas de confianza
    lines.append("## 📊 Estadísticas de Confianza (Similarity Scores)")
    lines.append("")
    conf_stats = analyzer.get_confidence_stats()

    lines.append("| Métrica | Correctos | Incorrectos | Todos |")
    lines.append("|---------|-----------|-------------|-------|")

    stat_names = ["mean", "median", "std", "min", "max"]
    for stat in stat_names:
        correct_val = conf_stats["correct"].get(stat, 0)
        incorrect_val = conf_stats["incorrect"].get(stat, 0)
        all_val = conf_stats["all"].get(stat, 0)
        lines.append(
            f"| {stat:7} | {correct_val:.3f} | {incorrect_val:.3f} | {all_val:.3f} |"
        )
    lines.append("")
    lines.append("---")
    lines.append("")

    # Comparación de rendimiento (timing, memoria)
    if config["output"]["include_performance_comparison"]:
        lines.append("## ⚡ Comparación de Rendimiento")
        lines.append("")
        lines.append("### Embeddings (este PoC)")
        lines.append(f"- **Tiempo total:** {format_time(stats['execution_time'])}")
        lines.append(f"- **Carga de modelo:** {format_time(stats['model_load_time'])}")
        lines.append(f"- **Generación embeddings:** {format_time(stats['embedding_time'])}")
        lines.append(f"- **Clasificación:** {format_time(stats['classification_time'])}")
        lines.append(f"- **Memoria pico:** {format_memory(stats['peak_memory'])}")
        lines.append(f"- **Costo:** $0 (local)")
        lines.append("")

        lines.append("### LLM (método actual)")
        lines.append(f"- **Modelo:** gpt-4o-mini")
        lines.append(f"- **Tiempo estimado:** ~15-30s para 180 URLs (batch)")
        lines.append(f"- **Costo estimado:** ~$0.02-0.04 por ejecución")
        lines.append(f"- **Dependencia:** API externa (OpenAI)")
        lines.append("")
        lines.append("---")
        lines.append("")

    # Configuración utilizada
    lines.append("## ⚙️ Configuración Utilizada")
    lines.append("")
    lines.append(f"- **Modelo embeddings:** {config['model']['name']}")
    lines.append(f"- **Método clasificación:** {config['classification']['method']}")
    lines.append(f"- **Umbral similitud:** {config['classification']['similarity_threshold']}")
    lines.append(f"- **Usar ejemplos:** {config['classification']['use_examples']}")
    lines.append(f"- **Ejemplos por categoría:** {config['classification']['examples_per_category']}")
    lines.append(f"- **Estrategia embedding categoría:** {config['classification']['category_embedding_strategy']}")
    lines.append("")

    # Dataset info
    lines.append("### Dataset")
    filters = config["database"]["filters"]
    lines.append(f"- **Fecha desde:** {filters['date_from'] or 'Sin filtro'}")
    lines.append(f"- **Fecha hasta:** {filters['date_to'] or 'Sin filtro'}")
    lines.append(f"- **Max URLs:** {filters['max_urls'] or 'Sin límite'}")
    lines.append(f"- **Categorías filtradas:** {filters['categories_filter'] or 'Todas'}")
    lines.append("")

    # Footer
    lines.append("---")
    lines.append(f"*Informe generado por poc_category_classification v1.0*")

    # Escribir archivo
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print(f"\n✅ Informe generado: {output_path}")


def main():
    parser = argparse.ArgumentParser(
        description="PoC de clasificación por categorías con embeddings"
    )
    parser.add_argument(
        "--config",
        type=str,
        default="config.yml",
        help="Path al archivo de configuración YAML",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Path al archivo de salida (default: auto-generado en output/)",
    )
    args = parser.parse_args()

    # Timestamp inicio
    start_time = time.time()
    tracemalloc.start()

    print("=" * 60)
    print("PoC Category Classification - Embeddings vs LLM")
    print("=" * 60)

    # Cargar configuración
    print(f"\n📄 Loading config: {args.config}")
    config = load_config(args.config)

    # Resolver paths relativos
    db_path = Path(__file__).parent / config["database"]["path"]
    categories_path = Path(__file__).parent / config["categories"]["config_path"]

    # 1. Cargar datos
    print("\n📦 Step 1: Loading classified URLs from database...")
    db_loader = DBLoader(str(db_path))

    # Mostrar estadísticas generales
    general_stats = db_loader.get_classification_stats()
    print(f"  Total URLs in DB: {general_stats['total_urls']}")
    print(f"  Classified URLs: {general_stats['total_classified']}")
    print(f"  Classification rate: {general_stats['classification_rate']:.1%}")

    # Cargar URLs filtradas
    filters = config["database"]["filters"]
    urls = db_loader.load_classified_urls(
        date_from=filters.get("date_from"),
        date_to=filters.get("date_to"),
        categories_filter=filters.get("categories_filter"),
        max_urls=filters.get("max_urls"),
        require_categoria=filters.get("require_categoria", True),
    )
    print(f"  Loaded {len(urls)} URLs for analysis")

    if not urls:
        print("❌ No URLs found with filters. Exiting.")
        return

    # Mostrar distribución de categorías
    category_dist = {}
    for url in urls:
        cat = url["categoria_tematica"]
        category_dist[cat] = category_dist.get(cat, 0) + 1
    print(f"\n  Category distribution:")
    for cat, count in sorted(category_dist.items(), key=lambda x: x[1], reverse=True):
        print(f"    {cat}: {count}")

    # 2. Inicializar embedder
    print(f"\n🤖 Step 2: Loading embedding model...")
    model_config = config["model"]
    model_load_start = time.time()

    embedder = Embedder(
        model_name=model_config["name"],
        cache_dir=str(Path(__file__).parent / model_config["cache_dir"]),
        device=model_config["device"],
        batch_size=model_config["batch_size"],
    )

    model_load_time = time.time() - model_load_start
    print(f"  Model loaded in {format_time(model_load_time)}")

    # 3. Inicializar clasificador
    print(f"\n🎯 Step 3: Initializing category classifier...")
    classification_config = config["classification"]

    classifier = CategoryClassifier(
        categories_config_path=str(categories_path),
        embedder=embedder,
        method=classification_config["method"],
        similarity_threshold=classification_config["similarity_threshold"],
        use_examples=classification_config["use_examples"],
        examples_per_category=classification_config["examples_per_category"],
        category_embedding_strategy=classification_config["category_embedding_strategy"],
        categories_to_exclude=config["categories"].get("exclude", []),
    )

    # 4. Clasificar titulares
    print(f"\n🔍 Step 4: Classifying {len(urls)} URLs with embeddings...")
    embedding_start = time.time()

    titles = [url["title"] for url in urls]
    predictions = classifier.classify_batch(titles, show_progress=True)

    classification_time = time.time() - embedding_start
    print(f"  Classification completed in {format_time(classification_time)}")

    # 5. Análisis de resultados
    print(f"\n📊 Step 5: Analyzing results...")
    analyzer = ComparisonAnalyzer()

    for url, (pred_cat, confidence) in zip(urls, predictions):
        analyzer.add_result(
            url_id=url["id"],
            title=url["title"],
            llm_category=url["categoria_tematica"],
            embedding_category=pred_cat,
            confidence=confidence,
        )

    # Mostrar resumen
    print(analyzer.get_summary())

    # 6. Generar informe
    print(f"\n📝 Step 6: Generating report...")

    execution_time = time.time() - start_time
    current, peak_memory = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    stats = {
        "execution_time": execution_time,
        "model_load_time": model_load_time,
        "embedding_time": embedding_start - model_load_start - model_load_time,
        "classification_time": classification_time,
        "peak_memory": peak_memory,
    }

    # Determinar output path
    if args.output:
        output_path = args.output
    else:
        output_dir = Path(__file__).parent / config["output"]["output_dir"]
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = output_dir / f"classification_report_{timestamp}.md"

    generate_markdown_report(analyzer, config, stats, str(output_path))

    # 7. Exportar CSV si configurado
    if config["output"].get("export_csv", True):
        csv_path = str(output_path).replace(".md", ".csv")
        analyzer.export_to_csv(csv_path)
        print(f"✅ CSV exported: {csv_path}")

    # Resumen final
    print("\n" + "=" * 60)
    print("✅ COMPLETED")
    print(f"Total execution time: {format_time(execution_time)}")
    print(f"Peak memory usage: {format_memory(peak_memory)}")
    print("=" * 60)


if __name__ == "__main__":
    main()
