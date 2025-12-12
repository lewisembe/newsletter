"""
Database Loader - Carga de titulares desde news.db
"""

import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional


class DBLoader:
    """Carga titulares desde la base de datos news.db"""

    def __init__(self, db_path: str):
        """
        Args:
            db_path: Ruta a news.db
        """
        self.db_path = Path(db_path)
        if not self.db_path.exists():
            raise FileNotFoundError(f"Database not found: {self.db_path}")

    def load_articles(
        self,
        date: Optional[str] = None,
        category: Optional[str] = None,
        content_type: Optional[str] = "contenido",
    ) -> List[Dict]:
        """
        Carga artículos de la base de datos.

        Args:
            date: Fecha en formato YYYY-MM-DD. Si None, usa fecha actual.
            category: Filtrar por categoria_tematica. Si None, todas las categorías.
            content_type: Filtrar por tipo de contenido. Default: 'contenido'

        Returns:
            Lista de diccionarios con: id, url, title, source, extracted_at, categoria_tematica
        """
        if date is None:
            date = datetime.now().strftime("%Y-%m-%d")

        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row  # Para acceder a columnas por nombre
        cursor = conn.cursor()

        # Construir query
        query = """
            SELECT
                id,
                url,
                title,
                source,
                extracted_at,
                categoria_tematica
            FROM urls
            WHERE date(extracted_at) = ?
        """
        params = [date]

        if content_type:
            query += " AND content_type = ?"
            params.append(content_type)

        if category:
            query += " AND categoria_tematica = ?"
            params.append(category)

        # Ordenar por fecha de extracción (cronológico)
        query += " ORDER BY extracted_at ASC"

        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()

        # Convertir a lista de diccionarios
        articles = []
        for row in rows:
            articles.append({
                "id": row["id"],
                "url": row["url"],
                "title": row["title"],
                "source": row["source"],
                "extracted_at": row["extracted_at"],
                "categoria_tematica": row["categoria_tematica"],
            })

        return articles

    def get_date_stats(self, date: str) -> Dict:
        """
        Obtiene estadísticas de artículos para una fecha.

        Args:
            date: Fecha en formato YYYY-MM-DD

        Returns:
            Dict con total, por categoría, por fuente
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Total de artículos
        cursor.execute(
            "SELECT COUNT(*) FROM urls WHERE date(extracted_at) = ?", [date]
        )
        total = cursor.fetchone()[0]

        # Por categoría
        cursor.execute(
            """
            SELECT categoria_tematica, COUNT(*) as count
            FROM urls
            WHERE date(extracted_at) = ?
            GROUP BY categoria_tematica
            ORDER BY count DESC
            """,
            [date],
        )
        categories = {row[0]: row[1] for row in cursor.fetchall()}

        # Por fuente
        cursor.execute(
            """
            SELECT source, COUNT(*) as count
            FROM urls
            WHERE date(extracted_at) = ?
            GROUP BY source
            ORDER BY count DESC
            LIMIT 10
            """,
            [date],
        )
        sources = {row[0]: row[1] for row in cursor.fetchall()}

        conn.close()

        return {
            "total": total,
            "categories": categories,
            "top_sources": sources,
        }


if __name__ == "__main__":
    # Test
    loader = DBLoader("../data/news.db")

    # Test date stats
    today = datetime.now().strftime("%Y-%m-%d")
    stats = loader.get_date_stats(today)
    print(f"Stats for {today}:")
    print(f"  Total: {stats['total']}")
    print(f"  Categories: {stats['categories']}")

    # Test article loading
    articles = loader.load_articles(date=today, category="economia")
    print(f"\nLoaded {len(articles)} articles from 'economia' category")
    if articles:
        print(f"First article: {articles[0]['title']}")
