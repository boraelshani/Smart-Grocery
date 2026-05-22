"""Run SPAR scraper wrapper

Defaults to the click-next Playwright scraper (robust for SPAR pagination).
Usage:
    python run_spar.py --max-pages 5 --dry-run --out preview_spar.json

Dry-run will save the scraped products to a JSON file and will NOT modify the database.
"""
import argparse
import json
import os
import sys

# Prefer the click-next scraper
from scrapers.spar_click_next import SparClickNextScraper


def main():
    parser = argparse.ArgumentParser(description="Run SPAR scraper (wrapper)")
    parser.add_argument("--max-pages", type=int, default=None, help="Maximum pages to scrape")
    parser.add_argument("--delay", type=float, default=2.0, help="Delay between page navigations")
    parser.add_argument("--headless", action="store_true", help="Run browser headless")
    parser.add_argument("--dry-run", action="store_true", help="Do not write to DB; save output to JSON")
    parser.add_argument("--out", default="data/preview_spar.json", help="Output file for dry-run JSON")
    args = parser.parse_args()

    scraper = SparClickNextScraper(headless=args.headless)
    try:
        products = scraper.scrape_all_products(max_pages=args.max_pages, delay=args.delay)
    except Exception as e:
        print(f"[!] Scraper error: {e}")
        sys.exit(2)

    print(f"Scraped {len(products)} products")

    if args.dry_run:
        os.makedirs(os.path.dirname(args.out), exist_ok=True)
        with open(args.out, "w", encoding="utf-8") as fh:
            json.dump(products, fh, ensure_ascii=False, indent=2)
        print(f"Saved dry-run output to {args.out}")
    else:
        # Ideally this would insert into DB with history tracking.
        # For safety, we avoid making DB changes in this wrapper; use the existing scraper.save_to_database()
        try:
            from app import app
            from models.postgres_models import db
            with app.app_context():
                print("Saving to database (this will modify DB)...")
                stats = scraper.save_to_database(products, db.session)
                print("Database save stats:")
                for k, v in stats.items():
                    print(f"  {k}: {v}")
        except Exception as e:
            print(f"[!] Error saving to DB: {e}")
            sys.exit(3)


if __name__ == "__main__":
    main()
