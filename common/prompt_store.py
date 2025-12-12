"""
PromptStore utility: fetch prompts/templates/categories from DB with file fallback.

Usage:
    store = PromptStore(db=PostgreSQLURLDatabase(DATABASE_URL))
    prompt = store.get_prompt(stage="01", operation="filter_news_urls")
    template = store.get_newsletter_template("default")
    categories = store.get_categories()
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

from common.postgres_db import PostgreSQLURLDatabase

logger = logging.getLogger(__name__)


class PromptStore:
    def __init__(
        self,
        db: Optional[PostgreSQLURLDatabase] = None,
        templates_dir: Path | None = None,
        categories_file: Path | None = None,
    ):
        self.db = db
        self.templates_dir = templates_dir or Path("templates/prompts")
        self.categories_file = categories_file or Path("config/categories.yml")

    # ---------- Prompts ----------
    def get_prompt(self, stage: str, operation: str) -> Optional[Dict[str, Any]]:
        """
        Fetch prompt by stage/operation from DB, fallback to None.
        """
        if self.db:
            try:
                query = """
                    SELECT lp.*
                    FROM prompt_usages pu
                    JOIN llm_prompts lp ON lp.id = pu.prompt_id
                    WHERE pu.stage = %s AND pu.operation = %s AND pu.enabled = TRUE
                    LIMIT 1
                """
                res = self.db.execute_query(query, (stage, operation), fetch_one=True)
                if res:
                    return dict(res)
            except Exception as e:
                logger.warning(f"DB prompt fetch failed for {stage}/{operation}: {e}")
        return None

    # ---------- Newsletter templates ----------
    def get_newsletter_template(self, name: str) -> Optional[Dict[str, Any]]:
        """
        Fetch newsletter template from DB, fallback to JSON file in templates/prompts.
        """
        if self.db:
            try:
                query = """
                    SELECT *
                    FROM newsletter_templates
                    WHERE name = %s AND status = 'approved'
                    ORDER BY version DESC
                    LIMIT 1
                """
                res = self.db.execute_query(query, (name,), fetch_one=True)
                if res:
                    return dict(res)
            except Exception as e:
                logger.warning(f"DB template fetch failed for {name}: {e}")

        # Fallback to file
        file_path = self.templates_dir / f"{name}.json"
        if file_path.exists():
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                return {
                    "name": data.get("name", name),
                    "description": data.get("description", ""),
                    "system_prompt": data.get("system_prompt", ""),
                    "user_prompt_template": data.get("user_prompt_template", ""),
                    "placeholders": ["date", "newsletter_name", "context"],
                    "default_model": data.get("model", None),
                    "temperature": data.get("temperature", None),
                    "max_tokens": data.get("max_tokens", None),
                }
            except Exception as e:
                logger.error(f"Error reading template file {file_path}: {e}")
        return None

    # ---------- Categories / ontologies ----------
    def get_categories(self) -> Dict[str, Any]:
        """
        Fetch categories from DB prompt_categories, fallback to config/categories.yml.

        Returns dict with keys found (e.g., categories, content_types, classification_rules).
        """
        result: Dict[str, Any] = {}
        if self.db:
            try:
                query = """
                    SELECT name, items
                    FROM prompt_categories
                    WHERE status = 'approved'
                """
                rows = self.db.execute_query(query) or []
                for row in rows:
                    name = row.get("name")
                    items = row.get("items")
                    result[name] = items
                if result:
                    return result
            except Exception as e:
                logger.warning(f"DB categories fetch failed: {e}")

        # Fallback to YAML file
        if self.categories_file.exists():
            try:
                with open(self.categories_file, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f) or {}
                return data
            except Exception as e:
                logger.error(f"Error reading categories file {self.categories_file}: {e}")
        return result
