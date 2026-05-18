#!/usr/bin/env python3
"""
Runner script for SPAR API Scraper
This will attempt to find SPAR's internal API and scrape all products
"""

import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from scrapers.spar_api_scraper import SparApiScraper
from app import app
from models.postgres_models import db


def main():
    """Main execution."""
    print("""
╔═══════════════════════════════════════════════════════════════════════════╗
║                SPAR AUSTRIA API SCRAPER                                   ║
║                  Smart Grocery Project                                    ║
╚═══════════════════════════════════════════════════════════════════════════╝

This scraper will:
1. Try to find SPAR's internal API endpoint
2. Scrape all 1,178 pages (~37,692 products)
3. Save unique products to database
4. Avoid duplicates using fingerprinting

Configuration:
- Headless: False (you'll see the browser)
- Max Pages: All (1,178)
- Delay: 1.5 seconds between pages
- Safe: No data loss, no duplicates

Press Ctrl+C to stop at any time.
""")
    
    try:
        with app.app_context():
            scraper = SparApiScraper(headless=False)
            
            print("[*] Starting scraper...")
            print("[*] This will take approximately 30-60 minutes for all pages")
            print()
            
            # Scrape products
            products = scraper.scrape_with_selenium(max_pages=None, delay=1.5)
            
            if products:
                print(f"\n[✓] Scraped {len(products)} unique products!")
                print(f"[*] Saving to database...")
                
                db_stats = scraper.save_to_database(products, db.session)
                
                print(f"\n{'='*80}")
                print("FINAL STATISTICS")
                print(f"{'='*80}")
                for key, value in db_stats.items():
                    print(f"{key:25s}: {value}")
                print(f"{'='*80}\n")
                
                print("[✓] All done! Products saved to database.")
            else:
                print("[!] No products scraped. Check the logs above for errors.")
    
    except KeyboardInterrupt:
        print("\n\n[!] Interrupted by user. Exiting...")
        sys.exit(0)
    except Exception as e:
        print(f"\n[!] Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
