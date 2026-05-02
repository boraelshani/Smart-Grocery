# Smart Grocery – Data Cleaning Pipeline
"""
4-step pipeline:
  1. name_cleaner.py     – Professional name cleaning, brand extraction
  2. categoriser.py      – Strong keyword-based categorisation
  3. price_freshness.py  – Staleness detection + URL discovery
  4. product_matcher.py  – Conservative cross-store merging

Usage:
  python scripts/pipeline/orchestrator.py              # full pipeline
  python scripts/pipeline/orchestrator.py --dry-run    # preview
  python scripts/pipeline/orchestrator.py --steps 3 4  # daily update
"""
