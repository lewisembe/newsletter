#!/usr/bin/env python3
"""
Initialize independent POC database for keyword-based search testing.

Creates a separate database (poc_keyword_search/data/poc_news.db) that:
- Has the same schema as the main database
- Includes the search_keyword column
- Doesn't affect the production database
"""

import sqlite3
import sys
from pathlib import Path
from datetime import datetime

def init_poc_database():
    """Initialize POC database with full schema including search_keyword."""

    # Create data directory for POC
    poc_dir = Path(__file__).parent
    data_dir = poc_dir / "data"
    data_dir.mkdir(exist_ok=True)

    db_path = data_dir / "poc_news.db"

    print(f"Initializing POC database at: {db_path}")

    try:
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()

        # Create urls table with search_keyword and google_news_url columns
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS urls (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                url TEXT NOT NULL UNIQUE,
                title TEXT,

                -- Stage 01: Classification
                content_type TEXT NOT NULL,
                content_subtype TEXT,
                classification_method TEXT,
                rule_name TEXT,

                source TEXT NOT NULL,
                extracted_at TIMESTAMP NOT NULL,
                last_extracted_at TIMESTAMP NOT NULL,

                -- POC: Keyword tracking (v1)
                search_keyword TEXT,

                -- POC: Google News URL tracking (v2)
                google_news_url TEXT,

                -- Stage 02: Thematic categorization
                categoria_tematica TEXT,
                categorized_at TIMESTAMP,

                -- Stage 01.5: Semantic clustering
                cluster_id TEXT,
                cluster_assigned_at TIMESTAMP,

                -- Stage 03: Ranking
                relevance_level INTEGER,
                scored_at TIMESTAMP,
                scored_by_method TEXT,

                -- Stage 04: Content extraction
                full_content TEXT,
                content_extracted_at TIMESTAMP,
                content_extraction_method TEXT,
                extraction_status TEXT,
                word_count INTEGER,
                archive_url TEXT,
                ai_summary TEXT,

                -- Metadata
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Create indices
        indices = [
            "CREATE INDEX IF NOT EXISTS idx_url ON urls(url)",
            "CREATE INDEX IF NOT EXISTS idx_extracted_at ON urls(extracted_at)",
            "CREATE INDEX IF NOT EXISTS idx_source ON urls(source)",
            "CREATE INDEX IF NOT EXISTS idx_content_type ON urls(content_type)",
            "CREATE INDEX IF NOT EXISTS idx_categoria_tematica ON urls(categoria_tematica)",
            "CREATE INDEX IF NOT EXISTS idx_cluster_id ON urls(cluster_id)",
            "CREATE INDEX IF NOT EXISTS idx_relevance_level ON urls(relevance_level)",
            "CREATE INDEX IF NOT EXISTS idx_scored_at ON urls(scored_at)",
            "CREATE INDEX IF NOT EXISTS idx_search_keyword ON urls(search_keyword)"
        ]

        for idx_sql in indices:
            cursor.execute(idx_sql)

        # Create keywords table (normalized keyword entities)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS keywords (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                keyword TEXT NOT NULL UNIQUE,
                category TEXT,
                is_active BOOLEAN DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_used_at TIMESTAMP,
                CONSTRAINT check_keyword_not_empty CHECK (length(trim(keyword)) > 0)
            )
        """)

        # Create indices for keywords
        cursor.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS idx_keywords_keyword ON keywords(keyword)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_keywords_active ON keywords(is_active)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_keywords_category ON keywords(category)
        """)

        # Create url_keywords table (N:N relationship for URLs and keywords - normalized)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS url_keywords (
                url_id INTEGER NOT NULL,
                keyword_id INTEGER NOT NULL,
                found_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (url_id, keyword_id),
                FOREIGN KEY (url_id) REFERENCES urls(id) ON DELETE CASCADE,
                FOREIGN KEY (keyword_id) REFERENCES keywords(id) ON DELETE CASCADE
            )
        """)

        # Create indices for url_keywords
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_url_keywords_url_id ON url_keywords(url_id)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_url_keywords_keyword_id ON url_keywords(keyword_id)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_url_keywords_found_at ON url_keywords(found_at)
        """)

        # Create clusters table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS clusters (
                id TEXT PRIMARY KEY,
                run_date TEXT NOT NULL,
                centroid_url_id INTEGER,
                article_count INTEGER NOT NULL,
                avg_similarity REAL,
                similarity_mean REAL,
                similarity_m2 REAL,
                similarity_samples INTEGER,
                cluster_name TEXT,
                last_assigned_at TIMESTAMP,
                created_at TIMESTAMP,
                updated_at TIMESTAMP,
                FOREIGN KEY (centroid_url_id) REFERENCES urls(id)
            )
        """)

        # Create ranking_runs table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS ranking_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                newsletter_name TEXT NOT NULL,
                date_filter TEXT NOT NULL,
                categories TEXT,
                ranking_method TEXT NOT NULL,
                articles_count INTEGER NOT NULL,
                total_candidates INTEGER NOT NULL,
                run_timestamp TIMESTAMP NOT NULL,
                duration_seconds REAL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Create ranked_urls table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS ranked_urls (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ranking_run_id INTEGER NOT NULL,
                url_id INTEGER NOT NULL,
                rank INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (ranking_run_id) REFERENCES ranking_runs(id),
                FOREIGN KEY (url_id) REFERENCES urls(id)
            )
        """)

        # Create newsletters table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS newsletters (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                newsletter_name TEXT NOT NULL,
                date TEXT NOT NULL,
                categories TEXT,
                articles_count INTEGER NOT NULL,
                template TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(newsletter_name, date)
            )
        """)

        # Create debug_reports table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS debug_reports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                newsletter_name TEXT NOT NULL,
                date TEXT NOT NULL,
                report_data TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(newsletter_name, date)
            )
        """)

        # Create url_embeddings table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS url_embeddings (
                url_id INTEGER PRIMARY KEY,
                embedding BLOB NOT NULL,
                dimension INTEGER NOT NULL,
                created_at TIMESTAMP,
                FOREIGN KEY(url_id) REFERENCES urls(id) ON DELETE CASCADE
            )
        """)

        conn.commit()

        # Verify
        cursor.execute("PRAGMA table_info(urls)")
        columns = [col[1] for col in cursor.fetchall()]

        print("\n✓ POC Database initialized successfully!")
        print(f"  Location: {db_path}")
        print(f"  Tables created: urls, keywords, url_keywords, clusters, ranking_runs, ranked_urls, newsletters, debug_reports, url_embeddings")
        print(f"  Total columns in urls table: {len(columns)}")
        print(f"  search_keyword column: {'✓' if 'search_keyword' in columns else '✗'}")
        print(f"  Normalized schema: keywords table + url_keywords with keyword_id ✓")

        return True

    except Exception as e:
        print(f"\n✗ Database initialization failed: {e}")
        return False
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    success = init_poc_database()
    sys.exit(0 if success else 1)
