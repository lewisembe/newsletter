"""
Configuration settings for the Newsletter Bot
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / '.env')

# OpenAI Configuration
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
CLASSIFICATION_MODEL = os.getenv('CLASSIFICATION_MODEL', 'gpt-3.5-turbo')
NEWSLETTER_MODEL = os.getenv('NEWSLETTER_MODEL', 'gpt-4-turbo-preview')

# Google Sheets Configuration
GOOGLE_SHEETS_ID = os.getenv('GOOGLE_SHEETS_ID')
CREDENTIALS_PATH = BASE_DIR / 'config' / 'credentials.json'

# Sheet Names
SHEET_SOURCES = 'Fuentes'
SHEET_TOPICS = 'Temas'
SHEET_PROCESSED_NEWS = 'Noticias_Procesadas'
SHEET_NEWSLETTERS = 'Newsletters_Generadas'

# Content Processing
MAX_TOKENS_PER_ARTICLE = int(os.getenv('MAX_TOKENS_PER_ARTICLE', 1000))
MAX_ARTICLES_PER_DAY = int(os.getenv('MAX_ARTICLES_PER_DAY', 100))

# Newsletter Generation Configuration
NEWSLETTER_USE_CULTURAL_REFERENCES = os.getenv('NEWSLETTER_USE_CULTURAL_REFERENCES', 'true').lower() == 'true'
NEWSLETTER_MIN_WORD_COUNT = int(os.getenv('NEWSLETTER_MIN_WORD_COUNT', 800))
NEWSLETTER_INCLUDE_EXECUTIVE_SUMMARY = os.getenv('NEWSLETTER_INCLUDE_EXECUTIVE_SUMMARY', 'true').lower() == 'true'

# Execution Configuration
TIMEZONE = os.getenv('TIMEZONE', 'America/New_York')
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')

# Archive Services
ARCHIVE_SERVICES = os.getenv('ARCHIVE_SERVICES', 'archive.today,web.archive.org,12ft.io').split(',')

# Logging Configuration
LOG_DIR = BASE_DIR / 'logs'
LOG_DIR.mkdir(exist_ok=True)
LOG_FILE = LOG_DIR / 'newsletter_bot.log'

# Validation
def validate_config():
    """Validate that all required configuration is present"""
    errors = []

    if not OPENAI_API_KEY:
        errors.append("OPENAI_API_KEY is not set in .env file")

    if not GOOGLE_SHEETS_ID:
        errors.append("GOOGLE_SHEETS_ID is not set in .env file")

    if not CREDENTIALS_PATH.exists():
        errors.append(f"Google credentials file not found at {CREDENTIALS_PATH}")

    if errors:
        raise ValueError("Configuration errors:\n" + "\n".join(f"- {e}" for e in errors))

    return True

if __name__ == '__main__':
    try:
        validate_config()
        print("✓ Configuration is valid")
        print(f"✓ Google Sheets ID: {GOOGLE_SHEETS_ID}")
        print(f"✓ Credentials path: {CREDENTIALS_PATH}")
        print(f"✓ OpenAI API Key: {'*' * 20}{OPENAI_API_KEY[-10:]}")
    except ValueError as e:
        print(f"✗ {e}")
