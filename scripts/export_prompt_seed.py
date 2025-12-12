#!/usr/bin/env python3
"""
Export seed data for prompt management tables from existing files.

This script is non-destructive and only prints JSON to stdout. It focuses on:
1) Newsletter templates from templates/prompts/*.json
2) Categories from config/categories.yml

Usage:
  python scripts/export_prompt_seed.py > /tmp/prompt_seed.json
"""

import json
import glob
from pathlib import Path

import yaml

BASE_DIR = Path(__file__).resolve().parent.parent
TEMPLATES_DIR = BASE_DIR / "templates" / "prompts"
CATEGORIES_FILE = BASE_DIR / "config" / "categories.yml"


def load_newsletter_templates():
    templates = []
    for path_str in glob.glob(str(TEMPLATES_DIR / "*.json")):
        path = Path(path_str)
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        templates.append(
            {
                "name": data.get("name", path.stem),
                "description": data.get("description", ""),
                "system_prompt": data.get("system_prompt", ""),
                "user_prompt_template": data.get("user_prompt_template", ""),
                "placeholders": ["date", "newsletter_name", "context"],
                "default_model": "gpt-4o-mini",
                "temperature": data.get("temperature", 0.3),
                "max_tokens": data.get("max_tokens", None),
                "notes": f"Imported from {path.name}",
            }
        )
    return templates


def load_categories():
    if not CATEGORIES_FILE.exists():
        return []
    with open(CATEGORIES_FILE, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    categories = []
    for key in ["categories", "content_types"]:
        if key in data:
            categories.append(
                {
                    "name": f"{key}",
                    "items": data[key],
                    "notes": f"Imported from categories.yml ({key})",
                }
            )
    # Level1 rules if present
    if "classification_rules" in data and isinstance(data["classification_rules"], dict):
        categories.append(
            {
                "name": "classification_rules",
                "items": data["classification_rules"],
                "notes": "Imported rules from categories.yml",
            }
        )
    return categories


def main():
    seed = {
        "newsletter_templates": load_newsletter_templates(),
        "prompt_categories": load_categories(),
    }
    print(json.dumps(seed, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
