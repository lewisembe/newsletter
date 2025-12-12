#!/usr/bin/env python3
"""
Analyze Context Report - Quick verification tool for newsletter generation

Usage:
    python scripts/analyze_context_report.py data/newsletters/context_report_*.json
    python scripts/analyze_context_report.py --latest
"""

import json
import sys
from pathlib import Path
from typing import Dict, Any
import argparse


def load_report(filepath: str) -> Dict[str, Any]:
    """Load context report from JSON file."""
    with open(filepath, 'r', encoding='utf-8') as f:
        return json.load(f)


def print_summary(report: Dict[str, Any]) -> None:
    """Print summary of context report."""
    print("="*80)
    print("📊 CONTEXT REPORT SUMMARY")
    print("="*80)

    # Metadata
    meta = report['metadata']
    print(f"\n📝 Newsletter: {meta['newsletter_name']}")
    print(f"📅 Run Date: {meta['run_date']}")
    print(f"🕐 Generated: {meta['generated_at']}")

    # Configuration
    config = report['configuration']
    print(f"\n⚙️  CONFIGURATION")
    print(f"   • Max articles: {config['max_articles']}")
    print(f"   • Top with content: {config['top_with_content']}")
    print(f"   • Template: {config['template']}")
    print(f"   • Model: {config['model_writer']}")
    print(f"   • Format: {config['output_format']}")

    # Categories
    expected_cats = config.get('expected_categories', [])
    ranked_cats = config.get('ranked_file_categories', [])
    print(f"\n📂 CATEGORIES")
    print(f"   • Expected: {expected_cats}")
    print(f"   • Ranked file: {ranked_cats}")

    if expected_cats and ranked_cats:
        if sorted([c.lower() for c in expected_cats]) == sorted([c.lower() for c in ranked_cats]):
            print(f"   ✅ Categories match!")
        else:
            print(f"   ❌ MISMATCH! Categories don't match")

    # Extraction stats
    stats = report['content_extraction']['extraction_stats']
    print(f"\n📊 EXTRACTION STATS")
    print(f"   • Requested: {stats['total_requested']}")
    print(f"   • Success: {stats['total_success']}")
    print(f"   • Failed: {stats['total_failed']}")
    print(f"   • Success rate: {stats['success_rate']}%")

    if stats['success_rate'] >= 80:
        print(f"   ✅ Excellent extraction rate!")
    elif stats['success_rate'] >= 60:
        print(f"   ⚠️  Moderate extraction rate - room for improvement")
    else:
        print(f"   ❌ LOW extraction rate - needs attention!")

    # Failed extractions details
    failed = report['content_extraction']['urls_failed_extraction']
    if failed:
        print(f"\n❌ FAILED EXTRACTIONS ({len(failed)})")
        for item in failed[:5]:  # Show first 5
            print(f"   • [{item.get('rank', 'N/A')}] {item['title'][:60]}...")
            if item.get('error'):
                print(f"     Error: {item['error']}")

    # Extraction methods breakdown
    articles = report['articles']
    methods = {}
    for article in articles:
        method = article.get('extraction_method')
        if method:
            methods[method] = methods.get(method, 0) + 1

    if methods:
        print(f"\n🔧 EXTRACTION METHODS")
        for method, count in sorted(methods.items(), key=lambda x: x[1], reverse=True):
            print(f"   • {method}: {count}")

    # Category distribution
    categories = {}
    for article in articles:
        cat = article.get('category', 'Unknown')
        categories[cat] = categories.get(cat, 0) + 1

    print(f"\n📁 CATEGORY DISTRIBUTION")
    for cat, count in sorted(categories.items(), key=lambda x: x[1], reverse=True):
        print(f"   • {cat}: {count}")

    # Newsletter preview
    preview = report['newsletter_preview']
    print(f"\n📰 NEWSLETTER PREVIEW")
    print(f"   • Word count: {preview['word_count']}")
    print(f"   • Character count: {preview['char_count']}")

    if preview['word_count'] >= 500:
        print(f"   ✅ Good length newsletter")
    else:
        print(f"   ⚠️  Newsletter seems short")

    print("\n" + "="*80)


def print_verification_checklist(report: Dict[str, Any]) -> None:
    """Print verification checklist."""
    print("\n🔍 VERIFICATION CHECKLIST")
    print("-"*80)

    checks = []

    # 1. Category match
    config = report['configuration']
    expected = config.get('expected_categories', [])
    ranked = config.get('ranked_file_categories', [])
    if expected and ranked:
        match = sorted([c.lower() for c in expected]) == sorted([c.lower() for c in ranked])
        checks.append(("Category match", match))
    else:
        checks.append(("Category match", True))  # No specific requirements

    # 2. Extraction rate
    stats = report['content_extraction']['extraction_stats']
    checks.append(("Extraction rate >= 70%", stats['success_rate'] >= 70))

    # 3. Configuration consistency
    checks.append(("Config: total_requested == top_with_content",
                   stats['total_requested'] == config['top_with_content']))

    # 4. Newsletter size
    preview = report['newsletter_preview']
    checks.append(("Newsletter word count > 500", preview['word_count'] > 500))

    # 5. Content availability
    articles_with_content = [a for a in report['articles'] if a.get('has_full_content')]
    all_have_content = all(
        a.get('full_content') and len(a.get('full_content', '')) > 0
        for a in articles_with_content
    )
    checks.append(("Articles with has_full_content have content", all_have_content))

    # 6. All articles have categories
    all_have_categories = all(
        a.get('category') and a.get('category') != 'Unknown'
        for a in report['articles']
    )
    checks.append(("All articles have valid categories", all_have_categories))

    # Print results
    for check_name, passed in checks:
        status = "✅" if passed else "❌"
        print(f"{status} {check_name}")

    # Summary
    passed_count = sum(1 for _, passed in checks if passed)
    total_count = len(checks)
    print("-"*80)
    print(f"Result: {passed_count}/{total_count} checks passed")

    if passed_count == total_count:
        print("✅ All checks passed! Newsletter generation looks good.")
    else:
        print("⚠️  Some checks failed - review the issues above.")


def print_failed_details(report: Dict[str, Any]) -> None:
    """Print detailed information about failed extractions."""
    failed = report['content_extraction']['urls_failed_extraction']

    if not failed:
        print("\n✅ No failed extractions!")
        return

    print(f"\n❌ FAILED EXTRACTIONS - DETAILED ({len(failed)})")
    print("-"*80)

    for i, item in enumerate(failed, 1):
        print(f"\n{i}. [{item.get('rank', 'N/A')}] {item['title']}")
        print(f"   URL: {item['url']}")
        print(f"   Status: {item.get('status', 'unknown')}")
        if item.get('error'):
            print(f"   Error: {item['error']}")


def main():
    parser = argparse.ArgumentParser(
        description='Analyze context report from newsletter generation'
    )
    parser.add_argument(
        'report_file',
        nargs='?',
        help='Path to context report JSON file'
    )
    parser.add_argument(
        '--latest',
        action='store_true',
        help='Analyze the latest context report in data/newsletters/'
    )
    parser.add_argument(
        '--checklist',
        action='store_true',
        help='Show verification checklist'
    )
    parser.add_argument(
        '--failed',
        action='store_true',
        help='Show detailed failed extractions'
    )

    args = parser.parse_args()

    # Determine which file to analyze
    if args.latest:
        # Find latest context report
        reports_dir = Path("data/newsletters")
        if not reports_dir.exists():
            print("Error: data/newsletters/ directory not found")
            return 1

        reports = sorted(reports_dir.glob("context_report_*.json"), reverse=True)
        if not reports:
            print("Error: No context reports found in data/newsletters/")
            return 1

        report_file = reports[0]
        print(f"📄 Analyzing latest report: {report_file.name}\n")

    elif args.report_file:
        report_file = Path(args.report_file)
        if not report_file.exists():
            print(f"Error: File not found: {report_file}")
            return 1

    else:
        parser.print_help()
        return 1

    # Load and analyze report
    try:
        report = load_report(report_file)
    except Exception as e:
        print(f"Error loading report: {e}")
        return 1

    # Print analysis
    print_summary(report)

    if args.checklist:
        print_verification_checklist(report)

    if args.failed:
        print_failed_details(report)

    return 0


if __name__ == '__main__':
    sys.exit(main())
