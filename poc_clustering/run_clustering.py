#!/usr/bin/env python3
"""
PoC Clustering - Script principal

Ejecuta clustering de noticias relacionadas y genera informe markdown.
"""

import argparse
import time
import yaml
from datetime import datetime
from pathlib import Path
from typing import Dict, List
import tracemalloc

from src.db_loader import DBLoader
from src.embedder import Embedder
from src.cluster_manager import ClusterManager
from src.hashtag_generator import HashtagGenerator


def load_config(config_path: str = "config.yml") -> dict:
    """Carga configuración desde YAML y normaliza rutas relativas"""
    config_file = Path(config_path)
    with open(config_file, "r") as f:
        config = yaml.safe_load(f)

    # Normalizar rutas relativas basadas en la ubicación del archivo de config
    base_dir = config_file.parent.resolve()
    db_path = config["database"].get("path")
    if db_path:
        config["database"]["path"] = str((base_dir / db_path).resolve())

    model_cache = config["model"].get("cache_dir")
    if model_cache:
        config["model"]["cache_dir"] = str((base_dir / model_cache).resolve())

    config["_base_dir"] = str(base_dir)
    return config


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
    clusters_data: List[Dict],
    articles_by_id: Dict[int, Dict],
    config: dict,
    stats: dict,
    output_path: str,
):
    """
    Genera informe markdown con resultados del clustering.

    Args:
        clusters_data: Lista de clusters con hashtags
        articles_by_id: Mapping article_id -> article data
        config: Configuración
        stats: Estadísticas de ejecución
        output_path: Path al archivo de salida
    """
    date = stats["date"]
    category = stats.get("category", "todas")

    # Construir contenido markdown
    lines = []

    # Header
    lines.append("# 📊 Informe de Clustering de Noticias")
    lines.append(f"**Fecha:** {date}")
    lines.append(f"**Categoría:** {category}")
    lines.append(f"**Generado:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append("")
    lines.append("---")
    lines.append("")

    # Resumen ejecutivo
    lines.append("## 📈 Resumen Ejecutivo")
    lines.append("")
    lines.append(f"- **Total de artículos analizados:** {stats['total_articles']}")
    lines.append(f"- **Total de clusters detectados:** {stats['total_clusters']}")
    lines.append(f"- **Artículos agrupados:** {stats['clustered_articles']} ({stats['clustered_pct']:.1f}%)")
    lines.append(f"- **Artículos únicos (sin cluster):** {stats['unique_articles']} ({stats['unique_pct']:.1f}%)")

    if stats['total_clusters'] > 0:
        lines.append(f"- **Cluster más grande:** {stats['max_cluster_size']} artículos ({stats['max_cluster_hashtag']})")
        lines.append(f"- **Similitud promedio:** {stats['avg_similarity']:.2f}")

    lines.append("")
    lines.append("---")
    lines.append("")

    # Clusters principales
    lines.append("## 🎯 Clusters Principales")
    lines.append("")

    max_clusters = config["output"].get("max_clusters_detailed", 50)
    clusters_to_show = clusters_data[:max_clusters] if max_clusters > 0 else clusters_data

    for i, cluster in enumerate(clusters_to_show, 1):
        cluster_id = cluster["cluster_id"]
        hashtag = cluster["hashtag"]
        size = cluster["size"]
        avg_sim = cluster["avg_similarity"]
        articles = cluster["articles"]

        lines.append(f"### Cluster #{i}: {hashtag}")
        lines.append(f"**Tamaño:** {size} artículos | **Similitud promedio:** {avg_sim:.2f}")
        lines.append("")
        lines.append("**Artículos:**")

        for j, article_id in enumerate(articles, 1):
            article = articles_by_id[article_id]
            title = article["title"]
            url = article["url"]
            source = article["source"]
            extracted_at = article["extracted_at"]

            # Extraer dominio de source
            source_domain = source.replace("https://", "").replace("http://", "").split("/")[0]

            if config["output"].get("include_source", True):
                lines.append(f"{j}. **[{source_domain}]** {title}")
            else:
                lines.append(f"{j}. {title}")

            if config["output"].get("include_urls", True):
                lines.append(f"   `{url}`")

            lines.append(f"   *Extraído: {extracted_at}*")
            lines.append("")

        # Análisis del cluster (si hay suficientes artículos)
        if size >= 3:
            unique_sources = len(set(articles_by_id[aid]["source"] for aid in articles))
            lines.append(f"**Análisis:**")
            lines.append(f"Cobertura del evento por {unique_sources} medio(s) diferente(s).")
            lines.append("")

        lines.append("---")
        lines.append("")

    # Distribución de clusters
    lines.append("## 📊 Distribución de Clusters")
    lines.append("")

    distribution = stats["cluster_distribution"]
    lines.append("| Tamaño Cluster | Cantidad | % del Total |")
    lines.append("|----------------|----------|-------------|")

    for size_range, count in distribution.items():
        pct = (count / stats['total_clusters'] * 100) if stats['total_clusters'] > 0 else 0
        lines.append(f"| {size_range} | {count} | {pct:.1f}% |")

    lines.append("")
    lines.append("---")
    lines.append("")

    # Métricas de ejecución
    if config["output"].get("include_metrics", True):
        lines.append("## ⚙️ Métricas de Ejecución")
        lines.append("")
        lines.append(f"- **Tiempo de procesamiento:** {stats['processing_time']}")
        lines.append(f"- **Embeddings generados:** {stats['embeddings_generated']}")
        lines.append(f"- **Memoria usada:** {stats['memory_used']}")
        lines.append(f"- **Hashtags generados:** {stats['hashtags_generated']}")
        lines.append("")
        lines.append("---")
        lines.append("")

    # Configuración utilizada
    lines.append("## 🔍 Configuración Utilizada")
    lines.append("")
    lines.append(f"- **Modelo de embeddings:** {config['model']['name']}")
    lines.append(f"- **Threshold base:** {config['clustering']['similarity_threshold']}")
    lines.append(f"- **Threshold adaptativo:** {'Sí' if config['clustering']['adaptive_threshold'] else 'No'}")
    lines.append(f"- **Categoría:** {category}")
    lines.append(f"- **Min cluster size:** {config['clustering']['min_cluster_size']}")
    lines.append("")
    lines.append("---")
    lines.append("")

    # Footer
    lines.append("*Generado por poc_clustering v0.1.0*")

    # Escribir archivo
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print(f"\n✅ Informe generado: {output_path}")


def main():
    parser = argparse.ArgumentParser(
        description="PoC Clustering de noticias relacionadas"
    )
    parser.add_argument(
        "--date",
        type=str,
        default=datetime.now().strftime("%Y-%m-%d"),
        help="Fecha de noticias (YYYY-MM-DD)",
    )
    parser.add_argument(
        "--category",
        type=str,
        default=None,
        help="Filtrar por categoría temática",
    )
    parser.add_argument(
        "--config",
        type=str,
        default="config.yml",
        help="Path a archivo de configuración",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Modo verbose",
    )
    args = parser.parse_args()

    # Cargar configuración
    config = load_config(args.config)

    # Iniciar tracking de tiempo y memoria
    start_time = time.time()
    tracemalloc.start()

    print("=" * 60)
    print("PoC: Clustering de Noticias Relacionadas")
    print("=" * 60)
    print(f"Fecha: {args.date}")
    print(f"Categoría: {args.category or 'todas'}")
    print()

    # 1. Cargar artículos desde DB
    print("🗄️  Cargando artículos desde base de datos...")
    db_loader = DBLoader(config["database"]["path"])

    try:
        articles = db_loader.load_articles(
            date=args.date,
            category=args.category,
            content_type="contenido",
        )
    except FileNotFoundError as e:
        print(f"❌ Error: {e}")
        return

    if not articles:
        print(f"❌ No se encontraron artículos para {args.date}")
        if args.category:
            print(f"   Categoría: {args.category}")
        return

    print(f"   ✅ Cargados {len(articles)} artículos")

    # 2. Generar embeddings
    print("\n🔢 Generando embeddings...")
    embedder = Embedder(
        model_name=config["model"]["name"],
        cache_dir=config["model"]["cache_dir"],
        device=config["model"]["device"],
        batch_size=config["model"]["batch_size"],
    )

    titles = [article["title"] for article in articles]
    article_ids = [article["id"] for article in articles]

    embeddings = embedder.embed(titles, show_progress=True)
    print(f"   ✅ Embeddings generados: {embeddings.shape}")

    # 3. Clustering
    print("\n🔗 Ejecutando clustering...")
    cluster_manager = ClusterManager(
        embedding_dim=embedder.get_embedding_dim(),
        similarity_threshold=config["clustering"]["similarity_threshold"],
        adaptive_threshold=config["clustering"]["adaptive_threshold"],
        adaptive_k=config["clustering"]["adaptive_k"],
        max_neighbors=config["clustering"]["max_neighbors"],
    )

    cluster_map = cluster_manager.add_articles(embeddings, article_ids)
    clusters = cluster_manager.get_clusters()

    print(f"   ✅ Clusters detectados: {len(clusters)}")

    # Filtrar clusters por tamaño mínimo
    min_size = config["clustering"]["min_cluster_size"]
    filtered_clusters = {
        cid: members for cid, members in clusters.items() if len(members) >= min_size
    }

    print(f"   ✅ Clusters con ≥{min_size} artículos: {len(filtered_clusters)}")

    # 4. Generar hashtags
    print("\n🏷️  Generando hashtags...")
    hashtag_gen = HashtagGenerator(
        model=config["hashtag"]["llm_model"],
        temperature=config["hashtag"]["temperature"],
        max_tokens=config["hashtag"]["max_tokens"],
    )

    # Crear mapping article_id -> article data
    articles_by_id = {article["id"]: article for article in articles}

    # Generar hashtags y preparar datos para informe
    clusters_data = []

    for cluster_id, member_ids in filtered_clusters.items():
        # Obtener titulares del cluster
        cluster_titles = [articles_by_id[aid]["title"] for aid in member_ids]

        # Generar hashtag
        hashtag = hashtag_gen.generate(
            cluster_titles,
            max_titles=config["hashtag"]["max_titles_for_context"],
        )

        # Obtener estadísticas del cluster
        stats_cluster = cluster_manager.get_cluster_stats(cluster_id)

        clusters_data.append({
            "cluster_id": cluster_id,
            "hashtag": hashtag,
            "size": len(member_ids),
            "avg_similarity": stats_cluster.get("avg_similarity", 0.0),
            "articles": member_ids,
        })

        if args.verbose:
            print(f"   Cluster {cluster_id}: {hashtag} ({len(member_ids)} artículos)")

    # Ordenar clusters por tamaño (descendente)
    clusters_data.sort(key=lambda x: x["size"], reverse=True)

    print(f"   ✅ Hashtags generados: {len(clusters_data)}")

    # 5. Calcular estadísticas
    current_memory, peak_memory = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    elapsed_time = time.time() - start_time

    # Estadísticas
    total_articles = len(articles)
    clustered_articles = sum(len(members) for members in filtered_clusters.values())
    unique_articles = total_articles - clustered_articles

    # Distribución de tamaños
    distribution = {
        "2 artículos": sum(1 for c in clusters_data if c["size"] == 2),
        "3-5 artículos": sum(1 for c in clusters_data if 3 <= c["size"] <= 5),
        "6-10 artículos": sum(1 for c in clusters_data if 6 <= c["size"] <= 10),
        "11+ artículos": sum(1 for c in clusters_data if c["size"] >= 11),
    }

    stats = {
        "date": args.date,
        "category": args.category,
        "total_articles": total_articles,
        "total_clusters": len(clusters_data),
        "clustered_articles": clustered_articles,
        "clustered_pct": (clustered_articles / total_articles * 100) if total_articles > 0 else 0,
        "unique_articles": unique_articles,
        "unique_pct": (unique_articles / total_articles * 100) if total_articles > 0 else 0,
        "max_cluster_size": max((c["size"] for c in clusters_data), default=0),
        "max_cluster_hashtag": clusters_data[0]["hashtag"] if clusters_data else "",
        "avg_similarity": sum(c["avg_similarity"] for c in clusters_data) / len(clusters_data) if clusters_data else 0,
        "processing_time": format_time(elapsed_time),
        "embeddings_generated": len(embeddings),
        "memory_used": format_memory(peak_memory),
        "hashtags_generated": len(clusters_data),
        "cluster_distribution": distribution,
    }

    # 6. Generar informe markdown
    print("\n📝 Generando informe markdown...")
    base_dir = Path(config.get("_base_dir", ".")).resolve()
    output_dir_cfg = config.get("output", {}).get("directory")
    if output_dir_cfg:
        output_dir = Path(output_dir_cfg)
        if not output_dir.is_absolute():
            output_dir = (base_dir / output_dir_cfg).resolve()
    else:
        output_dir = base_dir / "output"
    output_dir.mkdir(exist_ok=True)

    output_filename = f"clustering_report_{args.date}"
    if args.category:
        output_filename += f"_{args.category}"
    output_filename += ".md"

    output_path = output_dir / output_filename

    generate_markdown_report(
        clusters_data=clusters_data,
        articles_by_id=articles_by_id,
        config=config,
        stats=stats,
        output_path=str(output_path),
    )

    # Resumen final
    print("\n" + "=" * 60)
    print("✅ Clustering completado")
    print("=" * 60)
    print(f"Artículos analizados: {total_articles}")
    print(f"Clusters detectados: {len(clusters_data)}")
    print(f"Artículos agrupados: {clustered_articles} ({stats['clustered_pct']:.1f}%)")
    print(f"Tiempo de procesamiento: {stats['processing_time']}")
    print(f"Memoria usada: {stats['memory_used']}")
    print(f"\n📄 Informe: {output_path}")


if __name__ == "__main__":
    main()
