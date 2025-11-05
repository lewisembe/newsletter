"""
Google Sheets integration module
Handles all CRUD operations for the Newsletter Bot Google Sheet
"""
import gspread
from google.oauth2.service_account import Credentials
import logging
from datetime import datetime
from typing import List, Dict, Optional, Any

from config import settings

# Setup logging
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(settings.LOG_FILE),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class GoogleSheetsClient:
    """Client for interacting with Google Sheets"""

    def __init__(self):
        """Initialize Google Sheets client"""
        try:
            # Define the scope
            scopes = [
                'https://www.googleapis.com/auth/spreadsheets',
                'https://www.googleapis.com/auth/drive'
            ]

            # Authenticate
            creds = Credentials.from_service_account_file(
                str(settings.CREDENTIALS_PATH),
                scopes=scopes
            )
            self.client = gspread.authorize(creds)

            # Open the spreadsheet
            self.spreadsheet = self.client.open_by_key(settings.GOOGLE_SHEETS_ID)
            logger.info(f"Connected to Google Sheet: {self.spreadsheet.title}")

        except Exception as e:
            logger.error(f"Failed to initialize Google Sheets client: {e}")
            raise

    def ensure_sheets_exist(self):
        """Ensure all required sheets exist, create them if they don't"""
        required_sheets = {
            settings.SHEET_SOURCES: ['nombre', 'url', 'tipo', 'activo'],
            settings.SHEET_TOPICS: ['id', 'nombre', 'keywords', 'descripcion'],
            settings.SHEET_PROCESSED_NEWS: [
                'fecha_publicacion', 'titulo', 'fuente', 'tema', 'contenido_completo',
                'contenido_truncado', 'url_original', 'url_sin_paywall', 'fecha_fetch', 'hash_contenido'
            ],
            settings.SHEET_NEWSLETTERS: [
                'fecha_generacion', 'contenido', 'num_articulos', 'temas_cubiertos'
            ]
        }

        existing_sheets = [sheet.title for sheet in self.spreadsheet.worksheets()]

        for sheet_name, headers in required_sheets.items():
            if sheet_name not in existing_sheets:
                logger.info(f"Creating sheet: {sheet_name}")
                worksheet = self.spreadsheet.add_worksheet(
                    title=sheet_name,
                    rows=1000,
                    cols=len(headers)
                )
                # Add headers
                worksheet.append_row(headers)
                logger.info(f"Created sheet '{sheet_name}' with headers: {headers}")
            else:
                logger.info(f"Sheet '{sheet_name}' already exists")

    # ===== SOURCES SHEET OPERATIONS =====

    def get_active_sources(self) -> List[Dict[str, str]]:
        """Get all active news sources"""
        try:
            worksheet = self.spreadsheet.worksheet(settings.SHEET_SOURCES)
            records = worksheet.get_all_records()

            # Filter only active sources
            active_sources = [
                record for record in records
                if str(record.get('activo', '')).lower() in ['si', 'yes', 'true', '1', 'sí']
            ]

            logger.info(f"Retrieved {len(active_sources)} active sources")
            return active_sources

        except Exception as e:
            logger.error(f"Error getting active sources: {e}")
            return []

    def add_source(self, nombre: str, url: str, tipo: str, activo: str = 'si'):
        """Add a new source to the sources sheet"""
        try:
            worksheet = self.spreadsheet.worksheet(settings.SHEET_SOURCES)
            worksheet.append_row([nombre, url, tipo, activo])
            logger.info(f"Added source: {nombre}")
        except Exception as e:
            logger.error(f"Error adding source: {e}")
            raise

    # ===== TOPICS SHEET OPERATIONS =====

    def get_all_topics(self) -> List[Dict[str, str]]:
        """Get all predefined topics/categories"""
        try:
            worksheet = self.spreadsheet.worksheet(settings.SHEET_TOPICS)
            records = worksheet.get_all_records()
            logger.info(f"Retrieved {len(records)} topics")
            return records
        except Exception as e:
            logger.error(f"Error getting topics: {e}")
            return []

    def get_topic_names(self) -> List[str]:
        """Get just the topic names for classification"""
        topics = self.get_all_topics()
        return [topic['nombre'] for topic in topics if 'nombre' in topic]

    def add_topic(self, topic_id: str, nombre: str, keywords: str = '', descripcion: str = ''):
        """Add a new topic to the topics sheet"""
        try:
            worksheet = self.spreadsheet.worksheet(settings.SHEET_TOPICS)
            worksheet.append_row([topic_id, nombre, keywords, descripcion])
            logger.info(f"Added topic: {nombre}")
        except Exception as e:
            logger.error(f"Error adding topic: {e}")
            raise

    # ===== PROCESSED NEWS SHEET OPERATIONS =====

    def get_all_processed_news(self) -> List[Dict[str, Any]]:
        """Get all processed news articles"""
        try:
            worksheet = self.spreadsheet.worksheet(settings.SHEET_PROCESSED_NEWS)
            records = worksheet.get_all_records()
            logger.info(f"Retrieved {len(records)} processed articles")
            return records
        except Exception as e:
            logger.error(f"Error getting processed news: {e}")
            return []

    def get_processed_urls(self) -> set:
        """Get all URLs that have been processed (for deduplication)"""
        articles = self.get_all_processed_news()
        urls = {article.get('url_original', '') for article in articles}
        urls.discard('')  # Remove empty strings
        return urls

    def add_processed_article(
        self,
        fecha_publicacion: str,
        titulo: str,
        fuente: str,
        tema: str,
        contenido_completo: str,
        contenido_truncado: str,
        url_original: str,
        url_sin_paywall: str,
        hash_contenido: str
    ):
        """Add a processed article to the sheet"""
        try:
            worksheet = self.spreadsheet.worksheet(settings.SHEET_PROCESSED_NEWS)
            fecha_fetch = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            worksheet.append_row([
                fecha_publicacion,
                titulo,
                fuente,
                tema,
                contenido_completo,  # Full content
                contenido_truncado,  # Truncated content for classification
                url_original,
                url_sin_paywall,
                fecha_fetch,
                hash_contenido
            ])

            logger.info(f"Added processed article: {titulo[:50]}...")

        except Exception as e:
            logger.error(f"Error adding processed article: {e}")
            raise

    def add_processed_articles_batch(self, articles: List[Dict[str, Any]]):
        """Add multiple processed articles at once (more efficient)"""
        try:
            worksheet = self.spreadsheet.worksheet(settings.SHEET_PROCESSED_NEWS)
            fecha_fetch = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            rows = []
            for article in articles:
                rows.append([
                    article.get('fecha_publicacion', ''),
                    article.get('titulo', ''),
                    article.get('fuente', ''),
                    article.get('tema', ''),
                    article.get('contenido_completo', ''),  # Full content
                    article.get('contenido_truncado', ''),  # Truncated content
                    article.get('url_original', ''),
                    article.get('url_sin_paywall', ''),
                    fecha_fetch,
                    article.get('hash_contenido', '')
                ])

            if rows:
                worksheet.append_rows(rows)
                logger.info(f"Added {len(rows)} articles in batch")

        except Exception as e:
            logger.error(f"Error adding articles in batch: {e}")
            raise

    # ===== NEWSLETTERS SHEET OPERATIONS =====

    def add_newsletter(
        self,
        contenido: str,
        num_articulos: int,
        temas_cubiertos: str
    ):
        """Add a generated newsletter to the sheet"""
        try:
            worksheet = self.spreadsheet.worksheet(settings.SHEET_NEWSLETTERS)
            fecha_generacion = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            worksheet.append_row([
                fecha_generacion,
                contenido,
                num_articulos,
                temas_cubiertos
            ])

            logger.info(f"Added newsletter with {num_articulos} articles")

        except Exception as e:
            logger.error(f"Error adding newsletter: {e}")
            raise

    def get_latest_newsletter(self) -> Optional[Dict[str, Any]]:
        """Get the most recently generated newsletter"""
        try:
            worksheet = self.spreadsheet.worksheet(settings.SHEET_NEWSLETTERS)
            records = worksheet.get_all_records()

            if records:
                return records[-1]  # Return last record
            return None

        except Exception as e:
            logger.error(f"Error getting latest newsletter: {e}")
            return None

    # ===== RESET OPERATIONS =====

    def reset_processed_news(self) -> bool:
        """
        Reset the processed news sheet (clear all articles but keep headers)

        Returns:
            True if successful, False otherwise
        """
        try:
            logger.info("Resetting processed news sheet...")
            worksheet = self.spreadsheet.worksheet(settings.SHEET_PROCESSED_NEWS)

            # Clear all content
            worksheet.clear()

            # Restore headers
            headers = [
                'fecha_publicacion', 'titulo', 'fuente', 'tema', 'contenido_completo',
                'contenido_truncado', 'url_original', 'url_sin_paywall', 'fecha_fetch', 'hash_contenido'
            ]
            worksheet.append_row(headers)

            logger.info("✓ Processed news sheet reset successfully")
            return True

        except Exception as e:
            logger.error(f"Error resetting processed news: {e}")
            return False

    def reset_newsletters(self) -> bool:
        """
        Reset the newsletters sheet (clear all newsletters but keep headers)

        Returns:
            True if successful, False otherwise
        """
        try:
            logger.info("Resetting newsletters sheet...")
            worksheet = self.spreadsheet.worksheet(settings.SHEET_NEWSLETTERS)

            # Clear all content
            worksheet.clear()

            # Restore headers
            headers = ['fecha_generacion', 'contenido', 'num_articulos', 'temas_cubiertos']
            worksheet.append_row(headers)

            logger.info("✓ Newsletters sheet reset successfully")
            return True

        except Exception as e:
            logger.error(f"Error resetting newsletters: {e}")
            return False

    def reset_all_data(self, confirm: bool = False) -> Dict[str, bool]:
        """
        Reset both processed news and newsletters sheets

        Args:
            confirm: Must be True to execute (safety check)

        Returns:
            Dictionary with success status for each sheet reset
        """
        if not confirm:
            raise ValueError("Must explicitly confirm reset by passing confirm=True")

        logger.warning("⚠️  RESETTING ALL DATA (keeping sources and topics)")

        results = {
            'processed_news': False,
            'newsletters': False
        }

        results['processed_news'] = self.reset_processed_news()
        results['newsletters'] = self.reset_newsletters()

        if all(results.values()):
            logger.info("✅ All data reset successfully")
        else:
            logger.warning("⚠️  Some resets failed")

        return results


# Convenience function for quick access
def get_client() -> GoogleSheetsClient:
    """Get a GoogleSheetsClient instance"""
    return GoogleSheetsClient()


if __name__ == '__main__':
    # Test the Google Sheets connection
    try:
        client = GoogleSheetsClient()
        print("✓ Successfully connected to Google Sheets")
        print(f"✓ Spreadsheet: {client.spreadsheet.title}")

        # Ensure all sheets exist
        client.ensure_sheets_exist()
        print("✓ All required sheets are present")

    except Exception as e:
        print(f"✗ Error: {e}")
