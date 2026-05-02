#!/usr/bin/env python3
"""
Pipeline Orchestrator – 4 Steps
═══════════════════════════════

1. Name Cleaning       → Professional names, brand extraction, unit normalization
2. Categorisation      → Strong keyword-based category assignment
3. Price Freshness     → Staleness detection + URL discovery
4. Product Matching    → Conservative cross-store merging (100% certain only)

Usage:
  python scripts/pipeline/orchestrator.py              # all 4 steps
  python scripts/pipeline/orchestrator.py --dry-run    # preview
  python scripts/pipeline/orchestrator.py --steps 1 2  # specific steps
  python scripts/pipeline/orchestrator.py --steps 4    # matching only
"""

import os
import sys
import time
import json
from pathlib import Path

_project_root = Path(__file__).parent.parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from dotenv import load_dotenv
load_dotenv(_project_root / ".env", override=True)

STEPS = {
    1: {
        "name": "Name Cleaning",
        "module": "name_cleaner",
        "function": "apply_clean_names",
        "description": "Professional names, brand extraction, unit normalization",
    },
    2: {
        "name": "Categorisation",
        "module": "categoriser",
        "function": "apply_categorisation",
        "description": "Strong keyword-based category assignment with full paths",
    },
    3: {
        "name": "Price Freshness",
        "module": "price_freshness",
        "function": "mark_stale_prices",
        "description": "Staleness detection + URL discovery for BILLA/HOFER",
    },
    4: {
        "name": "Product Matching",
        "module": "product_matcher",
        "function": "merge_products",
        "description": "Conservative cross-store merging (100% certain only)",
    },
}

_STEP_ARGS = {
    1: {"db", "dry_run", "limit"},
    2: {"db", "dry_run", "limit", "confidence_threshold"},
    3: {"db", "dry_run", "max_stale_days"},
    4: {"db", "dry_run"},
}


def get_db():
    import certifi
    from pymongo import MongoClient
    client = MongoClient(
        os.environ["MONGO_URI"],
        tlsCAFile=certifi.where(),
        serverSelectionTimeoutMS=30000,
    )
    return client[os.environ.get("DATABASE_NAME", "smart_grocery")]


def run_pipeline(dry_run=False, steps=None, db=None, **kwargs):
    if db is None:
        db = get_db()

    if steps is None:
        steps = sorted(STEPS.keys())

    for s in steps:
        if s not in STEPS:
            raise ValueError(f"Unknown step: {s}. Valid: {list(STEPS.keys())}")

    print("=" * 70)
    print("Smart Grocery – Data Cleaning Pipeline")
    print("=" * 70)
    print(f"Mode: {'DRY RUN (no changes)' if dry_run else 'LIVE (writing to DB)'}")
    print(f"Steps: {steps}")
    print()

    overall_start = time.time()
    results = {}

    for step_num in steps:
        step = STEPS[step_num]
        print(f"\n{'─' * 70}")
        print(f"Step {step_num}: {step['name']}")
        print(f"Description: {step['description']}")
        print(f"{'─' * 70}")

        step_start = time.time()

        module = __import__(f"scripts.pipeline.{step['module']}", fromlist=[step['function']])
        func = getattr(module, step['function'])

        step_args = _STEP_ARGS.get(step_num, set())
        step_kwargs = {k: v for k, v in kwargs.items() if k in step_args}

        try:
            result = func(db=db, dry_run=dry_run, **step_kwargs)
            results[step_num] = {
                "status": "success",
                "result": result,
                "duration_seconds": round(time.time() - step_start, 1),
            }
            print(f"\n  Step {step_num} completed in {results[step_num]['duration_seconds']}s")
        except Exception as e:
            results[step_num] = {
                "status": "error",
                "error": str(e),
                "duration_seconds": round(time.time() - step_start, 1),
            }
            print(f"\n  ERROR in step {step_num}: {e}")

    total_duration = round(time.time() - overall_start, 1)
    print(f"\n{'=' * 70}")
    print(f"Pipeline {'DRY RUN' if dry_run else 'COMPLETE'} in {total_duration}s")
    print(f"{'=' * 70}")

    for step_num, result in results.items():
        status = "PASS" if result["status"] == "success" else "FAIL"
        print(f"  [{status}] Step {step_num} ({STEPS[step_num]['name']}): {result['duration_seconds']}s")

    return {
        "dry_run": dry_run,
        "steps_run": steps,
        "total_duration_seconds": total_duration,
        "results": results,
    }


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Data cleaning pipeline")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--steps", type=int, nargs="+", help="Specific steps (default: all)")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--confidence-threshold", type=float, default=0.3)
    parser.add_argument("--max-stale-days", type=int, default=3)
    args = parser.parse_args()

    kwargs = {}
    if args.limit > 0:
        kwargs["limit"] = args.limit
    kwargs["confidence_threshold"] = args.confidence_threshold
    kwargs["max_stale_days"] = args.max_stale_days

    result = run_pipeline(dry_run=args.dry_run, steps=args.steps, **kwargs)
    print(f"\n{json.dumps(result, indent=2, default=str)}")
