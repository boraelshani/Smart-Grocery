#!/usr/bin/env python3
"""
═══════════════════════════════════════════════════════════════════════════
SPAR FULL SCRAPER - OPTIMIZED FOR ALL 37,692 PRODUCTS
═══════════════════════════════════════════════════════════════════════════
This script will scrape all 1,178 pages from SPAR Austria efficiently.

Features:
- Fast scraping (1 second delay between pages)
- Incremental saves every 100 pages (no data loss)
- Progress tracking
- Automatic resume on interruption
- Proper image extraction (no placeholder icons)
- Deduplication via fingerprinting

Estimated time: 30-45 minutes for all pages
═══════════════════════════════════════════════════════════════════════════
"""

import sys
import os
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from scrapers.spar_playwright_scraper import SparPlaywrightScraper
from app import app
from models.postgres_models import db


def main():
    """Main execution."""
    print("""
╔═══════════════════════════════════════════════════════════════════════════╗
║           SPAR AUSTRIA - FULL PRODUCT SCRAPER (OPTIMIZED)                 ║
║                      Smart Grocery Project                                ║
╚═══════════════════════════════════════════════════════════════════════════╝

Target: All 1,178 pages (~37,692 products)

Configuration:
✓ Headless mode: Yes (faster)
✓ Delay: 1.0 seconds (optimized for speed)
✓ Incremental saves: Every 100 pages
✓ Image filtering: Skip placeholder icons
✓ Deduplication: Fingerprint-based
✓ Safe: No data loss, no duplicates

Estimated time: 30-45 minutes

Press Ctrl+C to stop at any time (progress will be saved)
""")
    
    input("Press ENTER to start scraping...")
    
    start_time = datetime.now()
    
    try:
        with app.app_context():
            scraper = SparPlaywrightScraper(headless=True)
            
            print(f"\n[*] Starting at {start_time.strftime('%H:%M:%S')}")
            print("[*] Scraping all 1,178 pages...")
            print()
            
            # Scrape all products with optimized settings
            products = scraper.scrape_all_products(
                max_pages=None,  # All pages
                delay=1.0,       # Fast but safe
                save_every=100   # Save every 100 pages
            )
            
            end_time = datetime.now()
            duration = end_time - start_time
            
            if products:
                print(f"\n{'='*80}")
                print("SCRAPING COMPLETE!")
                print(f"{'='*80}")
                print(f"Total products: {len(products)}")
                print(f"Duration: {duration}")
                print(f"Avg speed: {len(products) / duration.total_seconds() * 60:.1f} products/minute")
                print(f"{'='*80}\n")
                
                # Final save to database
                print("[*] Performing final database save...")
                db_stats = scraper.save_to_database(products, db.session)
                
                print(f"\n{'='*80}")
                print("DATABASE STATISTICS")
                print(f"{'='*80}")
                for key, value in db_stats.items():
                    print(f"{key:30s}: {value}")
                print(f"{'='*80}\n")
                
                print("[✓] All done! Check your database for SPAR products.")
                
                # Summary
                print(f"\n{'='*80}")
                print("SUMMARY")
                print(f"{'='*80}")
                print(f"Started:           {start_time.strftime('%H:%M:%S')}")
                print(f"Finished:          {end_time.strftime('%H:%M:%S')}")
                print(f"Duration:          {duration}")
                print(f"Products scraped:  {len(products)}")
                print(f"Products added:    {db_stats['products_added']}")
                print(f"Products updated:  {db_stats['products_updated']}")
                print(f"Promotions added:  {db_stats['promotions_added']}")
                print(f"Errors:            {db_stats['database_errors']}")
                print(f"{'='*80}\n")
            else:
                print("[!] No products scraped. Check the logs above for errors.")
    
    except KeyboardInterrupt:
        print("\n\n[!] Interrupted by user.")
        print("[*] Progress has been saved to database.")
        sys.exit(0)
    except Exception as e:
        print(f"\n[!] Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
