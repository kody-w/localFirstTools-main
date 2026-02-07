#!/usr/bin/env python3
"""Data Slosh Quality Scanner - Mode 1: Scan and Report.

Scans all HTML files under apps/, scores them using 19 quality rules,
and generates a markdown report.

Usage:
    python3 scripts/data_slosh_scan.py
    python3 scripts/data_slosh_scan.py --verbose
"""

import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
APPS_DIR = ROOT / "apps"
REPORT_PATH = ROOT / "data-slosh-report.md"

# Category folder mapping
CATEGORIES = {
    "3d-immersive": "3d_immersive",
    "audio-music": "audio_music",
    "creative-tools": "creative_tools",
    "experimental-ai": "experimental_ai",
    "games-puzzles": "games_puzzles",
    "generative-art": "generative_art",
    "particle-physics": "particle_physics",
    "visual-art": "visual_art",
}


def check_rules(content: str) -> dict:
    """Check all 19 quality rules against HTML content.

    Returns dict with:
        score: int (0-100)
        errors: list of failed error rules
        warnings: list of failed warning rules
        info: list of failed info rules
        all_failed: list of all failed rule names
        passed: list of all passed rule names
    """
    errors = []
    warnings = []
    info_issues = []

    # === ERRORS (15 points each) ===

    # 1. missing-doctype
    if not re.search(r'<!DOCTYPE\s+html>', content, re.IGNORECASE):
        errors.append("missing-doctype")

    # 2. missing-charset
    has_charset = bool(
        re.search(r'<meta\s+[^>]*charset\s*=', content, re.IGNORECASE)
        or re.search(r'http-equiv\s*=\s*["\']Content-Type["\'][^>]*charset', content, re.IGNORECASE)
    )
    if not has_charset:
        errors.append("missing-charset")

    # 3. missing-viewport
    if not re.search(r'<meta\s+[^>]*name\s*=\s*["\']viewport["\']', content, re.IGNORECASE):
        errors.append("missing-viewport")

    # 4. external-scripts
    if re.search(r'<script\s+[^>]*src\s*=\s*["\']https?://', content, re.IGNORECASE):
        errors.append("external-scripts")

    # 5. external-styles
    if re.search(r'<link\s+[^>]*href\s*=\s*["\']https?://', content, re.IGNORECASE):
        errors.append("external-styles")

    # 6. cdn-dependencies (any src= or href= to external URLs, broader check)
    # Only flag if there are external URLs beyond what rules 4+5 catch
    has_ext_src = bool(re.search(r'\bsrc\s*=\s*["\']https?://', content, re.IGNORECASE))
    has_ext_href = bool(re.search(r'\bhref\s*=\s*["\']https?://', content, re.IGNORECASE))
    if has_ext_src or has_ext_href:
        if "external-scripts" not in errors and "external-styles" not in errors:
            errors.append("cdn-dependencies")
        elif has_ext_src and "external-scripts" not in errors:
            errors.append("cdn-dependencies")
        elif has_ext_href and "external-styles" not in errors:
            errors.append("cdn-dependencies")
        # If both external-scripts and external-styles already flagged, cdn-deps is redundant
        # but we still flag it if there are OTHER external refs (e.g., img src)
        else:
            # Check for external refs beyond script src and link href
            other_ext = re.findall(r'\b(?:src|href)\s*=\s*["\']https?://[^"\']+', content, re.IGNORECASE)
            script_ext = re.findall(r'<script\s+[^>]*src\s*=\s*["\']https?://[^"\']+', content, re.IGNORECASE)
            link_ext = re.findall(r'<link\s+[^>]*href\s*=\s*["\']https?://[^"\']+', content, re.IGNORECASE)
            if len(other_ext) > len(script_ext) + len(link_ext):
                errors.append("cdn-dependencies")

    # === WARNINGS (5 points each) ===

    # 7. missing-title
    title_match = re.search(r'<title>(.*?)</title>', content, re.IGNORECASE | re.DOTALL)
    if not title_match or not title_match.group(1).strip():
        warnings.append("missing-title")

    # 8. missing-html-lang
    if not re.search(r'<html\s+[^>]*lang\s*=', content, re.IGNORECASE):
        # Also check <html lang=
        if not re.search(r'<html\s+lang\s*=', content, re.IGNORECASE):
            warnings.append("missing-html-lang")

    # 9. missing-description
    if not re.search(r'<meta\s+[^>]*name\s*=\s*["\']description["\']', content, re.IGNORECASE):
        warnings.append("missing-description")

    # 10. no-localstorage
    if not re.search(r'localStorage\.(getItem|setItem|removeItem|clear)', content):
        warnings.append("no-localstorage")

    # 11. no-json-export (only if uses localStorage)
    if "no-localstorage" not in warnings:
        has_json_export = bool(
            re.search(r'JSON\.stringify', content)
            and re.search(r'(download|export|Blob|saveAs|createObjectURL)', content, re.IGNORECASE)
        )
        if not has_json_export:
            warnings.append("no-json-export")

    # 12. no-error-handling
    has_error_handling = bool(
        re.search(r'try\s*\{', content)
        or re.search(r'window\.onerror', content)
        or re.search(r"addEventListener\s*\(\s*['\"]error['\"]", content)
        or re.search(r'\.catch\s*\(', content)
    )
    if not has_error_handling:
        warnings.append("no-error-handling")

    # 13. console-log-pollution
    if re.search(r'console\.(log|debug|info)\s*\(', content):
        warnings.append("console-log-pollution")

    # 14. hardcoded-api-keys
    if re.search(r'(api[_-]?key|api[_-]?token|secret[_-]?key|access[_-]?token|private[_-]?key)\s*[:=]\s*["\'][A-Za-z0-9_\-]{16,}["\']', content, re.IGNORECASE):
        warnings.append("hardcoded-api-keys")

    # === INFO (2 points each) ===

    # 15. no-media-queries
    if not re.search(r'@media\s', content):
        info_issues.append("no-media-queries")

    # 16. no-aria-labels
    if not re.search(r'(aria-label|role\s*=)', content, re.IGNORECASE):
        info_issues.append("no-aria-labels")

    # 17. no-noscript
    if not re.search(r'<noscript', content, re.IGNORECASE):
        info_issues.append("no-noscript")

    # 18. inline-onclick
    if re.search(r'\bon(click|mouseover|mouseout|mousedown|mouseup|change|submit|load|focus|blur)\s*=', content, re.IGNORECASE):
        info_issues.append("inline-onclick")

    # 19. missing-input-labels
    has_inputs = bool(re.search(r'<(input|select|textarea)\b', content, re.IGNORECASE))
    if has_inputs:
        has_labels = bool(re.search(r'<label\b', content, re.IGNORECASE))
        if not has_labels:
            info_issues.append("missing-input-labels")

    # Calculate score
    score = 100
    score -= len(errors) * 15
    score -= len(warnings) * 5
    score -= len(info_issues) * 2
    score = max(score, 0)

    all_failed = errors + warnings + info_issues
    all_rules = [
        "missing-doctype", "missing-charset", "missing-viewport",
        "external-scripts", "external-styles", "cdn-dependencies",
        "missing-title", "missing-html-lang", "missing-description",
        "no-localstorage", "no-json-export", "no-error-handling",
        "console-log-pollution", "hardcoded-api-keys",
        "no-media-queries", "no-aria-labels", "no-noscript",
        "inline-onclick", "missing-input-labels",
    ]
    passed = [r for r in all_rules if r not in all_failed]

    return {
        "score": score,
        "errors": errors,
        "warnings": warnings,
        "info": info_issues,
        "error_count": len(errors),
        "warning_count": len(warnings),
        "info_count": len(info_issues),
        "all_failed": all_failed,
        "passed": passed,
    }


def scan_all_apps(verbose=False):
    """Scan all HTML files under apps/ and return results."""
    results = []
    # Collect all HTML files, excluding archive and backup files
    html_files = []
    for cat_folder in sorted(CATEGORIES.keys()):
        cat_dir = APPS_DIR / cat_folder
        if not cat_dir.exists():
            continue
        for f in sorted(cat_dir.glob("*.html")):
            if f.name.endswith(".bak.html"):
                continue
            html_files.append((f, cat_folder))

    total = len(html_files)
    print(f"Data Slosh Scanner: Found {total} HTML files to scan.\n")

    rule_fail_counts = {}

    for i, (filepath, category) in enumerate(html_files, 1):
        try:
            content = filepath.read_text(errors="replace")
            result = check_rules(content)
            rel_path = f"apps/{category}/{filepath.name}"
            result["file"] = filepath.name
            result["path"] = rel_path
            result["category"] = category
            result["size_kb"] = round(len(content) / 1024, 1)
            result["lines"] = content.count("\n") + 1

            # Extract title
            title_match = re.search(r'<title>(.*?)</title>', content, re.IGNORECASE | re.DOTALL)
            result["title"] = title_match.group(1).strip() if title_match else filepath.stem.replace("-", " ").title()

            results.append(result)

            # Track rule failure frequency
            for rule in result["all_failed"]:
                rule_fail_counts[rule] = rule_fail_counts.get(rule, 0) + 1

            if verbose or i % 50 == 0 or i == total:
                print(
                    f"[{i}/{total}] {rel_path} -- score: {result['score']} "
                    f"-- errors: {result['error_count']}, warnings: {result['warning_count']}, info: {result['info_count']}"
                )
        except Exception as e:
            print(f"[{i}/{total}] ERROR reading {filepath}: {e}")

    return results, rule_fail_counts, total


def generate_report(results, rule_fail_counts, total_files):
    """Generate the markdown report."""
    scores = [r["score"] for r in results]
    avg_score = sum(scores) / len(scores) if scores else 0
    median_score = sorted(scores)[len(scores) // 2] if scores else 0

    # Score distribution buckets
    dist_0_50 = sum(1 for s in scores if s <= 50)
    dist_51_70 = sum(1 for s in scores if 51 <= s <= 70)
    dist_71_89 = sum(1 for s in scores if 71 <= s <= 89)
    dist_90_100 = sum(1 for s in scores if s >= 90)

    # Category averages
    cat_scores = {}
    for r in results:
        cat = r["category"]
        if cat not in cat_scores:
            cat_scores[cat] = []
        cat_scores[cat].append(r["score"])

    # Sort results by score ascending (worst first)
    sorted_results = sorted(results, key=lambda r: r["score"])

    lines = []
    lines.append("# Data Slosh Quality Report")
    lines.append("")
    lines.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"Scanner: Data Slosh 19-rule regex scorer (local-only, no AI)")
    lines.append("")
    lines.append("## Summary Statistics")
    lines.append("")
    lines.append(f"| Metric | Value |")
    lines.append(f"|--------|-------|")
    lines.append(f"| Total files scanned | {total_files} |")
    lines.append(f"| Files scored | {len(results)} |")
    lines.append(f"| Average score | {avg_score:.1f} |")
    lines.append(f"| Median score | {median_score} |")
    lines.append(f"| Highest score | {max(scores) if scores else 0} |")
    lines.append(f"| Lowest score | {min(scores) if scores else 0} |")
    lines.append("")
    lines.append("## Score Distribution")
    lines.append("")
    lines.append(f"| Range | Count | Percentage |")
    lines.append(f"|-------|-------|------------|")
    lines.append(f"| 90-100 (Excellent) | {dist_90_100} | {dist_90_100/len(results)*100:.1f}% |")
    lines.append(f"| 71-89 (Good) | {dist_71_89} | {dist_71_89/len(results)*100:.1f}% |")
    lines.append(f"| 51-70 (Fair) | {dist_51_70} | {dist_51_70/len(results)*100:.1f}% |")
    lines.append(f"| 0-50 (Poor) | {dist_0_50} | {dist_0_50/len(results)*100:.1f}% |")
    lines.append("")

    lines.append("## Category Averages")
    lines.append("")
    lines.append(f"| Category | Apps | Avg Score | Min | Max |")
    lines.append(f"|----------|------|-----------|-----|-----|")
    for cat in sorted(cat_scores.keys()):
        s = cat_scores[cat]
        lines.append(f"| {cat} | {len(s)} | {sum(s)/len(s):.1f} | {min(s)} | {max(s)} |")
    lines.append("")

    lines.append("## Top Issues (Most Common Failures)")
    lines.append("")
    lines.append(f"| # | Rule | Severity | Failures | % of Apps |")
    lines.append(f"|---|------|----------|----------|-----------|")
    sorted_rules = sorted(rule_fail_counts.items(), key=lambda x: x[1], reverse=True)
    for i, (rule, count) in enumerate(sorted_rules, 1):
        severity = "ERROR" if rule in [
            "missing-doctype", "missing-charset", "missing-viewport",
            "external-scripts", "external-styles", "cdn-dependencies"
        ] else "WARN" if rule in [
            "missing-title", "missing-html-lang", "missing-description",
            "no-localstorage", "no-json-export", "no-error-handling",
            "console-log-pollution", "hardcoded-api-keys"
        ] else "INFO"
        lines.append(f"| {i} | {rule} | {severity} | {count} | {count/len(results)*100:.1f}% |")
    lines.append("")

    lines.append("## All Files Ranked by Score (Worst First)")
    lines.append("")
    lines.append(f"| # | File | Category | Score | Errors | Warnings | Info | Failed Rules |")
    lines.append(f"|---|------|----------|-------|--------|----------|------|--------------|")
    for i, r in enumerate(sorted_results, 1):
        failed = ", ".join(r["all_failed"][:6])
        if len(r["all_failed"]) > 6:
            failed += f", +{len(r['all_failed'])-6} more"
        lines.append(
            f"| {i} | {r['path']} | {r['category']} | {r['score']} "
            f"| {r['error_count']} | {r['warning_count']} | {r['info_count']} "
            f"| {failed} |"
        )
    lines.append("")

    # Top 20 best files
    lines.append("## Top 20 Highest Scoring Apps")
    lines.append("")
    lines.append(f"| Rank | File | Category | Score | Failed Rules |")
    lines.append(f"|------|------|----------|-------|--------------|")
    top20 = sorted(results, key=lambda r: r["score"], reverse=True)[:20]
    for i, r in enumerate(top20, 1):
        failed = ", ".join(r["all_failed"]) if r["all_failed"] else "(none)"
        lines.append(f"| {i} | {r['path']} | {r['category']} | {r['score']} | {failed} |")
    lines.append("")

    # Bottom 20 worst files
    lines.append("## Bottom 20 Lowest Scoring Apps")
    lines.append("")
    lines.append(f"| Rank | File | Category | Score | Failed Rules |")
    lines.append(f"|------|------|----------|-------|--------------|")
    for i, r in enumerate(sorted_results[:20], 1):
        failed = ", ".join(r["all_failed"])
        lines.append(f"| {i} | {r['path']} | {r['category']} | {r['score']} | {failed} |")
    lines.append("")

    lines.append("---")
    lines.append(f"*Report generated by Data Slosh Scanner v1.0 on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*")

    return "\n".join(lines)


def main():
    verbose = "--verbose" in sys.argv or "-v" in sys.argv

    print("=" * 60)
    print("DATA SLOSH QUALITY SCANNER - Mode 1: Scan and Report")
    print("=" * 60)
    print(f"Scope: All HTML files under apps/")
    print(f"Method: Local-only regex scoring (19 quality rules)")
    print(f"AI Classification: No")
    print()

    results, rule_fail_counts, total_files = scan_all_apps(verbose=verbose)

    report = generate_report(results, rule_fail_counts, total_files)
    REPORT_PATH.write_text(report)

    # Print summary
    scores = [r["score"] for r in results]
    avg_score = sum(scores) / len(scores) if scores else 0

    print()
    print("=" * 60)
    print("SCAN COMPLETE")
    print("=" * 60)
    print(f"Files scanned: {len(results)}")
    print(f"Average score: {avg_score:.1f}")
    print(f"Score range: {min(scores) if scores else 0} - {max(scores) if scores else 0}")
    print(f"Files scoring 90+: {sum(1 for s in scores if s >= 90)}")
    print(f"Files scoring <50: {sum(1 for s in scores if s < 50)}")
    print(f"Report saved to: {REPORT_PATH}")
    print()

    # Print top 10 issues
    sorted_rules = sorted(rule_fail_counts.items(), key=lambda x: x[1], reverse=True)[:10]
    print("Top 10 most common issues:")
    for i, (rule, count) in enumerate(sorted_rules, 1):
        print(f"  {i:2d}. {rule}: {count} ({count/len(results)*100:.1f}%)")


if __name__ == "__main__":
    main()
