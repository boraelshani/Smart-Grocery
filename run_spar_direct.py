"""
Run the SPAR direct (API-interception) scraper.

Usage:
    python run_spar_direct.py                   # full scrape, headless
    python run_spar_direct.py --max-pages 5     # test with 5 pages
    python run_spar_direct.py --visible          # show browser window
    python run_spar_direct.py --dry-run          # scrape only, no DB write
"""
import argparse
import json
import subprocess
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Prevent macOS display/system sleep during scraping so Playwright isn't throttled
_caffeinate = None
if sys.platform == "darwin":
    try:
        _caffeinate = subprocess.Popen(
            ["caffeinate", "-dims", "-w", str(os.getpid())],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
    except FileNotFoundError:
        pass

# Import app BEFORE scraping so ensure_venv() in app.py fires immediately.
# If the interpreter is wrong, os.execv re-launches this whole script before
# any scraping work is done — not after spending 30 min collecting products.
from app import app
from models.postgres_models import db

from scrapers.spar_direct_scraper import SparDirectScraper


def main():
    parser = argparse.ArgumentParser(description="SPAR direct (API-interception) scraper")
    parser.add_argument("--max-pages", type=int, default=None, help="Limit pages for testing")
    parser.add_argument("--visible", action="store_true", help="Show browser window")
    parser.add_argument("--dry-run", action="store_true", help="Scrape only, no DB write")
    parser.add_argument("--out", default=None, help="Save scraped products to JSON file")
    parser.add_argument("--delay", type=float, default=0.3, help="Delay between pages (seconds)")
    args = parser.parse_args()

    scraper = SparDirectScraper(headless=not args.visible)
    products = scraper.scrape_all(max_pages=args.max_pages, delay=args.delay)

    if args.out or args.dry_run:
        out_path = args.out or "spar_products_preview.json"
        serializable = []
        for p in products:
            row = dict(p)
            if row.get("scraped_at"):
                row["scraped_at"] = row["scraped_at"].isoformat()
            if row.get("offer_end_date"):
                row["offer_end_date"] = row["offer_end_date"].isoformat()
            serializable.append(row)
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(serializable, f, ensure_ascii=False, indent=2)
        print(f"[✓] Saved {len(products)} products to {out_path}")

    if not args.dry_run and products:
        with app.app_context():
            stats = scraper.save_to_database(products, db.session)
            print(f"\n[✓] Done. {stats['products_added']} new products, "
                  f"{stats['promotions_added']} new promotions.")
    elif not products:
        print("[!] No products scraped.")


if __name__ == "__main__":
    main()
