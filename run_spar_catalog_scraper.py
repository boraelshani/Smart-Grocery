#!/usr/bin/env python3
"""
SPAR catalog scraper with Cloudflare bootstrap.

Why this exists:
- SPAR often serves a Cloudflare challenge page to automation.
- This script supports a one-time manual bootstrap in a real browser.
- It saves browser session state and reuses it for scraping.

Usage examples:
  # 1) Bootstrap session (one-time, opens browser)
  ./venv/bin/python run_spar_catalog_scraper.py --bootstrap-only

  # 2) Test scrape 2 pages without DB writes
  ./venv/bin/python run_spar_catalog_scraper.py --test --dry-run

  # 3) Full scrape + DB save
  ./venv/bin/python run_spar_catalog_scraper.py
"""

import argparse
import os
import sys
import time
from datetime import datetime

from playwright.sync_api import sync_playwright

from app import app
from models.postgres_models import db
from scrapers.spar_playwright_scraper import SparPlaywrightScraper


DEFAULT_STATE_PATH = "data/spar_storage_state.json"
DEFAULT_PROFILE_DIR = "data/spar_profile"
TARGET_URL = "https://www.spar.at/produktwelt/suche?search=%20&page=1"


def bootstrap_cloudflare_session(state_path: str, profile_dir: str, timeout_seconds: int = 300) -> bool:
    """Open a persistent browser for manual Cloudflare pass and save storage state."""
    os.makedirs(os.path.dirname(state_path), exist_ok=True)
    os.makedirs(profile_dir, exist_ok=True)

    print("\n[*] Bootstrapping SPAR browser session...")
    print("[*] A browser window will open.")
    print("[*] If Cloudflare challenge appears, complete it manually.")
    print("[*] Keep the catalog page open until products are visible.")

    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=profile_dir,
            headless=False,
            channel="chrome",
            viewport={"width": 1440, "height": 1000},
            locale="de-AT",
            timezone_id="Europe/Vienna",
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            args=[
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
                "--no-sandbox",
            ],
        )

        page = context.pages[0] if context.pages else context.new_page()
        page.goto(TARGET_URL, wait_until="domcontentloaded", timeout=60000)

        deadline = time.time() + timeout_seconds
        while time.time() < deadline:
            title = (page.title() or "").lower()
            url = (page.url or "").lower()
            html = (page.content() or "").lower()
            challenge = (
                "just a moment" in title
                or "__cf_chl" in url
                or "cdn-cgi/challenge-platform" in html
                or "enable javascript and cookies to continue" in html
            )
            if not challenge:
                # Basic check that we are on a real catalog page.
                # Keep selector broad because SPAR can change classes.
                if page.query_selector('[class*="product"]'):
                    context.storage_state(path=state_path)
                    context.close()
                    print(f"[✓] Saved storage state to {state_path}")
                    return True
            time.sleep(2)

        print("[!] Timed out waiting for a validated catalog session after challenge.")
        print("[*] State was NOT saved. Re-run and complete challenge until products are visible.")
        context.close()
        return False


def main():
    parser = argparse.ArgumentParser(description="SPAR catalog scraper with Cloudflare bootstrap")
    parser.add_argument("--state-path", default=DEFAULT_STATE_PATH, help="Playwright storage state path")
    parser.add_argument("--profile-dir", default=DEFAULT_PROFILE_DIR, help="Persistent browser profile directory")
    parser.add_argument("--bootstrap-only", action="store_true", help="Only perform Cloudflare/session bootstrap")
    parser.add_argument("--force-bootstrap", action="store_true", help="Re-bootstrap even if state file exists")
    parser.add_argument("--max-pages", type=int, default=None, help="Max pages to scrape (default: all)")
    parser.add_argument("--delay", type=float, default=1.5, help="Delay between pages")
    parser.add_argument("--dry-run", action="store_true", help="Scrape but skip DB writes")
    parser.add_argument("--test", action="store_true", help="Test mode (2 pages)")
    parser.add_argument("--visible", action="store_true", help="Run scraper browser visibly (non-headless)")
    args = parser.parse_args()

    if args.test:
        args.max_pages = 2

    need_bootstrap = args.force_bootstrap or (not os.path.exists(args.state_path))
    if need_bootstrap:
        ok = bootstrap_cloudflare_session(args.state_path, args.profile_dir)
        if not ok:
            print("[!] Bootstrap failed; exiting.")
            return 1

    if args.bootstrap_only:
        print("[✓] Bootstrap complete.")
        return 0

    print("\n" + "=" * 80)
    print("SPAR CATALOG SCRAPER")
    print("=" * 80)
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Max pages: {args.max_pages or 'All'}")
    print(f"Delay: {args.delay}s")
    print(f"Dry run: {args.dry_run}")
    print(f"Headless: {not args.visible}")
    print("=" * 80 + "\n")

    with app.app_context():
        scraper = SparPlaywrightScraper(
            headless=not args.visible,
            storage_state_path=args.state_path,
            profile_dir=args.profile_dir,
        )
        products = scraper.scrape_all_products(max_pages=args.max_pages, delay=args.delay)

        if not products:
            print("[!] No products scraped.")
            print("[*] Re-run with --force-bootstrap and complete challenge in browser.")
            return 1

        print(f"[✓] Scraped {len(products)} products")
        if args.dry_run:
            print("[*] Dry run enabled, skipping DB save.")
            return 0

        stats = scraper.save_to_database(products, db.session)
        print("\n[✓] Database write complete")
        for k, v in stats.items():
            print(f"  {k}: {v}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
