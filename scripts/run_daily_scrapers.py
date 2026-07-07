"""
Daily scraper runner — intended to be called by GitHub Actions (or any cron).
Runs all configured store scrapers in sequence and deactivates expired promotions.

Usage:
    python scripts/run_daily_scrapers.py              # all stores
    python scripts/run_daily_scrapers.py --store spar # single store
"""

import sys
import argparse
from datetime import datetime, timezone

# ── Expired promotions cleanup ────────────────────────────────────────────────

def deactivate_expired_promotions(db_session):
    """Mark any promotion whose end_date has passed as inactive."""
    from models.postgres_models import Promotion, Offer

    today = datetime.now(timezone.utc).date()
    expired = (
        db_session.query(Promotion)
        .filter(
            Promotion.is_active == True,
            Promotion.end_date != None,
            Promotion.end_date < today,
        )
        .all()
    )

    count = 0
    for promo in expired:
        promo.is_active = False
        if promo.offer:
            promo.offer.is_active = False
        count += 1

    db_session.commit()
    print(f"[✓] Deactivated {count} expired promotions (end_date < {today})")
    return count


# ── Store runner registry ────────────────────────────────────────────────────

def run_spar(db_session, max_pages=None):
    print("\n" + "="*70)
    print("RUNNING: SPAR scraper")
    print("="*70)
    from scrapers.spar_direct_scraper import SparDirectScraper
    scraper = SparDirectScraper(headless=True)
    products = scraper.scrape_all(max_pages=max_pages, delay=0.8)
    if products:
        return scraper.save_to_database(products, db_session)
    print("[!] SPAR: no products scraped")
    return {}


def run_billa(db_session, max_pages=None):
    print("\n" + "="*70)
    print("RUNNING: BILLA scraper")
    print("="*70)
    try:
        from scripts.billa_scrape_to_postgres import main as billa_main
        billa_main()
    except ImportError:
        from scrapers.real_billa_scraper import BillaScraper
        scraper = BillaScraper()
        products = scraper.scrape_all_products(max_pages=max_pages)
        if products:
            return scraper.save_to_database(products, db_session)
    return {}


STORE_RUNNERS = {
    "spar": run_spar,
    "billa": run_billa,
}


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Run daily grocery scrapers")
    parser.add_argument(
        "--store", choices=list(STORE_RUNNERS.keys()) + ["all"], default="all",
        help="Which store to scrape (default: all)"
    )
    parser.add_argument("--max-pages", type=int, default=None)
    args = parser.parse_args()

    from app import app
    from models.postgres_models import db

    start = datetime.now(timezone.utc)
    print(f"\n[{start.strftime('%Y-%m-%d %H:%M:%S UTC')}] Daily scraper starting…")

    with app.app_context():
        stores = list(STORE_RUNNERS.keys()) if args.store == "all" else [args.store]

        for store in stores:
            try:
                STORE_RUNNERS[store](db.session, max_pages=args.max_pages)
            except Exception as e:
                print(f"[!] ERROR running {store} scraper: {e}")
                import traceback
                traceback.print_exc()

        # Clean up expired promotions across all stores
        print("\n[*] Cleaning up expired promotions…")
        deactivate_expired_promotions(db.session)

    elapsed = (datetime.now(timezone.utc) - start).total_seconds()
    print(f"\n[✓] Daily scraper finished in {elapsed:.0f}s")


if __name__ == "__main__":
    main()
