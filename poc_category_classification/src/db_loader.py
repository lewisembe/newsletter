"""
Database Loader - Carga de URLs clasificadas desde news.db
Versión para PoC de clasificación por categorías con embeddings
"""

import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import random


class DBLoader:
    """Carga URLs clasificadas desde la base de datos news.db"""

    def __init__(self, db_path: str):
        """
        Args:
            db_path: Ruta a news.db
        """
        self.db_path = Path(db_path)
        if not self.db_path.exists():
            raise FileNotFoundError(f"Database not found: {self.db_path}")

    def load_classified_urls(
        self,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        categories_filter: Optional[List[str]] = None,
        max_urls: Optional[int] = None,
        require_categoria: bool = True,
    ) -> List[Dict]:
        """
        Carga URLs con categoría asignada (ground truth LLM).

        Args:
            date_from: Fecha inicio (YYYY-MM-DD). Si None, no filtra por fecha inicio.
            date_to: Fecha fin (YYYY-MM-DD). Si None, no filtra por fecha fin.
            categories_filter: Lista de categorías a incluir. Si None, todas.
            max_urls: Límite de URLs a cargar. Si None, todas.
            require_categoria: Si True, solo URLs con categoria_tematica != NULL

        Returns:
            Lista de diccionarios con: id, url, title, categoria_tematica, categorized_at
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Construir query
        query = """
            SELECT
                id,
                url,
                title,
                source,
                categoria_tematica,
                categorized_at,
                extracted_at
            FROM urls
            WHERE 1=1
        """
        params = []

        # Filtro: solo con categoría asignada
        if require_categoria:
            query += " AND categoria_tematica IS NOT NULL"

        # Filtro: rango de fechas (por categorized_at)
        if date_from:
            query += " AND date(categorized_at) >= ?"
            params.append(date_from)

        if date_to:
            query += " AND date(categorized_at) <= ?"
            params.append(date_to)

        # Filtro: categorías específicas
        if categories_filter:
            placeholders = ",".join(["?" for _ in categories_filter])
            query += f" AND categoria_tematica IN ({placeholders})"
            params.extend(categories_filter)

        # Ordenar por fecha de categorización
        query += " ORDER BY categorized_at DESC"

        # Límite de resultados
        if max_urls:
            query += f" LIMIT {max_urls}"

        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()

        # Convertir a lista de diccionarios
        urls = []
        for row in rows:
            urls.append({
                "id": row["id"],
                "url": row["url"],
                "title": row["title"],
                "source": row["source"],
                "categoria_tematica": row["categoria_tematica"],
                "categorized_at": row["categorized_at"],
                "extracted_at": row["extracted_at"],
            })

        return urls

    def get_category_distribution(
        self,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
    ) -> Dict[str, int]:
        """
        Obtiene distribución de URLs por categoría.

        Args:
            date_from: Fecha inicio (YYYY-MM-DD)
            date_to: Fecha fin (YYYY-MM-DD)

        Returns:
            Dict {categoria: count}
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        query = """
            SELECT categoria_tematica, COUNT(*) as count
            FROM urls
            WHERE categoria_tematica IS NOT NULL
        """
        params = []

        if date_from:
            query += " AND date(categorized_at) >= ?"
            params.append(date_from)

        if date_to:
            query += " AND date(categorized_at) <= ?"
            params.append(date_to)

        query += " GROUP BY categoria_tematica ORDER BY count DESC"

        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()

        return {row[0]: row[1] for row in rows}

    def get_classification_stats(self) -> Dict:
        """
        Obtiene estadísticas generales de clasificación en la base de datos.

        Returns:
            Dict con total URLs, total clasificadas, distribución por categoría, etc.
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Total URLs
        cursor.execute("SELECT COUNT(*) FROM urls")
        total_urls = cursor.fetchone()[0]

        # URLs clasificadas
        cursor.execute("SELECT COUNT(*) FROM urls WHERE categoria_tematica IS NOT NULL")
        total_classified = cursor.fetchone()[0]

        # Distribución por categoría
        cursor.execute("""
            SELECT categoria_tematica, COUNT(*) as count
            FROM urls
            WHERE categoria_tematica IS NOT NULL
            GROUP BY categoria_tematica
            ORDER BY count DESC
        """)
        distribution = {row[0]: row[1] for row in cursor.fetchall()}

        # Rango de fechas de clasificación
        cursor.execute("""
            SELECT
                MIN(date(categorized_at)) as first_date,
                MAX(date(categorized_at)) as last_date
            FROM urls
            WHERE categoria_tematica IS NOT NULL
        """)
        row = cursor.fetchone()
        date_range = {"first": row[0], "last": row[1]} if row[0] else None

        conn.close()

        return {
            "total_urls": total_urls,
            "total_classified": total_classified,
            "classification_rate": (
                total_classified / total_urls if total_urls > 0 else 0
            ),
            "category_distribution": distribution,
            "date_range": date_range,
        }

    def split_train_test(
        self,
        urls: List[Dict],
        test_ratio: float = 0.2,
        stratify: bool = True,
        random_seed: int = 42,
    ) -> Tuple[List[Dict], List[Dict]]:
        """
        Divide URLs en train/test sets.

        Args:
            urls: Lista de URLs
            test_ratio: Proporción para test set (0.0-1.0)
            stratify: Si True, mantiene distribución de categorías
            random_seed: Semilla para reproducibilidad

        Returns:
            (train_urls, test_urls)
        """
        random.seed(random_seed)

        if not stratify:
            # Split simple aleatorio
            shuffled = urls.copy()
            random.shuffle(shuffled)
            split_idx = int(len(shuffled) * (1 - test_ratio))
            return shuffled[:split_idx], shuffled[split_idx:]

        # Split estratificado por categoría
        by_category = {}
        for url in urls:
            cat = url["categoria_tematica"]
            if cat not in by_category:
                by_category[cat] = []
            by_category[cat].append(url)

        train_urls = []
        test_urls = []

        for cat, cat_urls in by_category.items():
            shuffled = cat_urls.copy()
            random.shuffle(shuffled)
            split_idx = int(len(shuffled) * (1 - test_ratio))
            train_urls.extend(shuffled[:split_idx])
            test_urls.extend(shuffled[split_idx:])

        # Shuffle final para mezclar categorías
        random.shuffle(train_urls)
        random.shuffle(test_urls)

        return train_urls, test_urls


if __name__ == "__main__":
    # Test
    loader = DBLoader("../data/news.db")

    # Test classification stats
    stats = loader.get_classification_stats()
    print("=== Classification Stats ===")
    print(f"Total URLs: {stats['total_urls']}")
    print(f"Classified: {stats['total_classified']} ({stats['classification_rate']:.1%})")
    print(f"\nCategory Distribution:")
    for cat, count in stats['category_distribution'].items():
        print(f"  {cat}: {count}")

    if stats['date_range']:
        print(f"\nDate Range: {stats['date_range']['first']} to {stats['date_range']['last']}")

    # Test loading classified URLs
    print("\n=== Loading Recent URLs ===")
    urls = loader.load_classified_urls(max_urls=100)
    print(f"Loaded {len(urls)} URLs")

    if urls:
        print(f"\nFirst URL:")
        print(f"  Title: {urls[0]['title']}")
        print(f"  Category: {urls[0]['categoria_tematica']}")
        print(f"  Categorized: {urls[0]['categorized_at']}")

    # Test train/test split
    if urls:
        print("\n=== Train/Test Split ===")
        train, test = loader.split_train_test(urls, test_ratio=0.2, stratify=True)
        print(f"Train: {len(train)} URLs")
        print(f"Test: {len(test)} URLs")

        # Verify stratification
        train_dist = {}
        test_dist = {}
        for url in train:
            cat = url["categoria_tematica"]
            train_dist[cat] = train_dist.get(cat, 0) + 1
        for url in test:
            cat = url["categoria_tematica"]
            test_dist[cat] = test_dist.get(cat, 0) + 1

        print("\nTrain distribution:")
        for cat, count in sorted(train_dist.items()):
            print(f"  {cat}: {count}")

        print("\nTest distribution:")
        for cat, count in sorted(test_dist.items()):
            print(f"  {cat}: {count}")
