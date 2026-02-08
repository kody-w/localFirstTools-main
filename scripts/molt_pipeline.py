#!/usr/bin/env python3
"""
molt_pipeline.py -- Single-app multi-generation molt pipeline with scoring.

Molts one app through N generations (default 4), re-scoring between each
to track quality improvement. Designed to be called in parallel by
task-delegator subagents.

Usage:
    python3 scripts/molt_pipeline.py <app-file>              # Molt through 4 gens
    python3 scripts/molt_pipeline.py <app-file> --dry-run    # Preview only
    python3 scripts/molt_pipeline.py <app-file> --verbose    # Show details
    python3 scripts/molt_pipeline.py <app-file> --gens N     # Override gen count

Output: apps/archive/<stem>/pipeline-report.json
"""

import json
import sys
from datetime import datetime
from pathlib import Path

from copilot_utils import APPS_DIR, load_manifest, save_manifest
from molt import get_generation_focus, molt_app, resolve_app
from rank_games import score_single_app


def run_pipeline(
    identifier,
    num_gens=4,
    dry_run=False,
    verbose=False,
    _manifest=None,
    _apps_dir=None,
):
    """Run a multi-generation molt pipeline on a single app.

    Returns a report dict with baseline, timeline, and summary.
    """
    manifest = _manifest if _manifest is not None else load_manifest()
    apps_dir = _apps_dir or APPS_DIR

    # Resolve the app
    try:
        path, cat_key, app_entry = resolve_app(
            identifier, _manifest=manifest, _apps_dir=apps_dir
        )
    except FileNotFoundError as e:
        return {"status": "failed", "reason": str(e)}

    filename = path.name
    stem = path.stem
    current_gen = app_entry.get("generation", 0)

    if verbose:
        print(f"\n{'='*60}")
        print(f"PIPELINE: {filename}")
        print(f"  Category: {cat_key}")
        print(f"  Current generation: {current_gen}")
        print(f"  Target generations: {num_gens}")
        print(f"{'='*60}")

    # Score baseline
    baseline = score_single_app(path)
    if verbose:
        print(f"\n  BASELINE: score={baseline['score']} grade={baseline['grade']}")
        for dim, data in baseline["dimensions"].items():
            print(f"    {dim}: {data['score']}/{data['max']}")

    timeline = []

    for i in range(num_gens):
        gen_num = current_gen + i + 1
        focus = get_generation_focus(gen_num)

        if verbose:
            print(f"\n  --- Generation {gen_num} ({focus}) ---")

        # Score before this molt
        score_before = score_single_app(path)

        # Run the molt
        result = molt_app(
            identifier,
            dry_run=dry_run,
            verbose=verbose,
            max_gen=current_gen + num_gens,
            _manifest=manifest,
            _apps_dir=apps_dir,
        )

        status = result.get("status", "failed")

        if status == "success":
            score_after = score_single_app(path)
            entry = {
                "generation": gen_num,
                "focus": focus,
                "status": "success",
                "score_before": score_before["score"],
                "score_after": score_after["score"],
                "delta": score_after["score"] - score_before["score"],
                "size_before": result.get("previousSize", 0),
                "size_after": result.get("newSize", 0),
                "dimensions_after": score_after["dimensions"],
            }
            if verbose:
                print(f"  SCORE: {entry['score_before']} -> {entry['score_after']} ({entry['delta']:+d})")
        elif status == "dry_run":
            entry = {
                "generation": gen_num,
                "focus": focus,
                "status": "dry_run",
                "score_before": score_before["score"],
                "score_after": score_before["score"],
                "delta": 0,
            }
            if verbose:
                print(f"  DRY RUN: would molt generation {gen_num}")
        else:
            # failed or rejected
            entry = {
                "generation": gen_num,
                "focus": focus,
                "status": status,
                "reason": result.get("reason", "unknown"),
                "score_before": score_before["score"],
                "score_after": score_before["score"],
                "delta": 0,
            }
            if verbose:
                print(f"  {status.upper()}: {result.get('reason', 'unknown')}")

        timeline.append(entry)

    # Final score
    final = score_single_app(path)
    total_delta = final["score"] - baseline["score"]
    generations_succeeded = sum(1 for e in timeline if e["status"] == "success")

    report = {
        "file": filename,
        "category": cat_key,
        "stem": stem,
        "baseline_score": baseline["score"],
        "baseline_grade": baseline["grade"],
        "final_score": final["score"],
        "final_grade": final["grade"],
        "total_delta": total_delta,
        "generations_attempted": num_gens,
        "generations_succeeded": generations_succeeded,
        "baseline_dimensions": baseline["dimensions"],
        "final_dimensions": final["dimensions"],
        "timeline": timeline,
        "timestamp": datetime.now().isoformat(),
    }

    # Write report to archive
    if not dry_run:
        archive_dir = apps_dir / "archive" / stem
        archive_dir.mkdir(parents=True, exist_ok=True)
        report_path = archive_dir / "pipeline-report.json"
        report_path.write_text(json.dumps(report, indent=2))
        if verbose:
            print(f"\n  Report written: {report_path}")

    # Save manifest (accumulated generation updates from all molts)
    # Only save when we loaded it ourselves (not when caller passed _manifest)
    if not dry_run and _manifest is None:
        save_manifest(manifest)
        if verbose:
            print(f"  Manifest saved.")

    if verbose:
        print(f"\n{'='*60}")
        print(f"PIPELINE COMPLETE: {filename}")
        print(f"  Score: {baseline['score']} -> {final['score']} ({total_delta:+d})")
        print(f"  Grade: {baseline['grade']} -> {final['grade']}")
        print(f"  Generations succeeded: {generations_succeeded}/{num_gens}")
        print(f"{'='*60}\n")

    report["status"] = "completed"
    return report


def select_candidates(manifest=None, apps_dir=None, score_min=40, score_max=65,
                      max_size=100_000, count=10):
    """Find gen-0 apps in the given score range for molting.

    Returns list of {file, category, score, grade, size_bytes} sorted by score.
    """
    manifest = manifest if manifest is not None else load_manifest()
    apps_dir = apps_dir or APPS_DIR

    candidates = []
    for cat_key, cat_data in manifest["categories"].items():
        folder = cat_data["folder"]
        for app_entry in cat_data["apps"]:
            # Skip already-molted apps
            if app_entry.get("generation", 0) > 0:
                continue

            filepath = apps_dir / folder / app_entry["file"]
            if not filepath.exists():
                continue

            size = filepath.stat().st_size
            if size > max_size:
                continue

            try:
                result = score_single_app(filepath)
            except Exception:
                continue

            if score_min <= result["score"] <= score_max:
                candidates.append({
                    "file": app_entry["file"],
                    "category": cat_key,
                    "score": result["score"],
                    "grade": result["grade"],
                    "size_bytes": size,
                })

    # Sort by score ascending (lowest = most potential)
    candidates.sort(key=lambda c: c["score"])

    # Diversify categories: pick from as many categories as possible
    if len(candidates) > count:
        selected = []
        seen_cats = set()
        # First pass: one per category
        for c in candidates:
            if c["category"] not in seen_cats and len(selected) < count:
                selected.append(c)
                seen_cats.add(c["category"])
        # Second pass: fill remaining slots
        for c in candidates:
            if c not in selected and len(selected) < count:
                selected.append(c)
        candidates = selected

    return candidates[:count]


def main():
    args = sys.argv[1:]
    dry_run = "--dry-run" in args
    verbose = "--verbose" in args or "-v" in args

    # Parse --gens N
    num_gens = 4
    if "--gens" in args:
        idx = args.index("--gens")
        if idx + 1 < len(args):
            num_gens = int(args[idx + 1])

    # Strip flags
    positional = [a for a in args if not a.startswith("--") and not a.startswith("-")]
    # Also remove the value after --gens
    if "--gens" in args:
        idx = args.index("--gens")
        if idx + 1 < len(args):
            val = args[idx + 1]
            if val in positional:
                positional.remove(val)

    if not positional:
        print("Usage: molt_pipeline.py <app-file> [--dry-run] [--verbose] [--gens N]")
        return 1

    app_file = positional[0]

    report = run_pipeline(
        app_file,
        num_gens=num_gens,
        dry_run=dry_run,
        verbose=verbose,
    )

    if report.get("status") == "completed":
        print(f"\n{report['file']}: {report['baseline_score']} -> {report['final_score']} "
              f"({report['total_delta']:+d}) [{report['baseline_grade']}->{report['final_grade']}] "
              f"({report['generations_succeeded']}/{report['generations_attempted']} gens)")
        return 0
    else:
        print(f"\nFAILED: {report.get('reason', 'unknown')}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
