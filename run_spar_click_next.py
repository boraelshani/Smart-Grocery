#!/usr/bin/env python3
"""Run SPAR scraper with Click Next approach"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from scrapers.spar_click_next import SparClickNextScraper
from app import app
from models.postgres_models import db

def main():
    print("\n" + "="*80)
    print("SPAR CLICK NEXT SCRAPER")
    print("="*80)
    print("\nThis scraper CLICKS the 'Next' button instead of changing URLs.")
    print("Testing with 20 pages...")
    print("Watch the browser - you'll see it clicking Next!")
    print("="*80 + "\n")
    
    input("Press ENTER to start...")
    
    with app.app_context():
        scraper = SparClickNextScraper(headless=False)
        products = scraper.scrape_all_products(max_pages=20, delay=2.0)
        
        print("\n" + "="*80)
        print("TEST RESULTS")
        print("="*80)
        
        if products and len(products) > 50:
            print(f"\n✅ SUCCESS! Got {len(products)} products!")
            print("   Pagination works by clicking Next!")
            
            full = input("\nRun FULL scrape (all pages)? (yes/no): ").lower()
            if full == 'yes':
                print("\n[*] Starting full scrape...")
                scraper2 = SparClickNextScraper(headless=True)
                all_products = scraper2.scrape_all_products(max_pages=None, delay=1.5)
                if all_products:
                    stats = scraper2.save_to_database(all_products, db.session)
                    print(f"\n✅ Complete! Added {stats['products_added']} products")
            else:
                stats = scraper.save_to_database(products, db.session)
                print(f"\n✅ Saved {stats['products_added']} products from test")
        elif products:
            print(f"\n⚠️  Got {len(products)} products")
            if len(products) <= 32:
                print("   Pagination NOT working (same as page 1)")
            else:
                print("   Pagination partially working")
            stats = scraper.save_to_database(products, db.session)
        else:
            print("\n❌ No products scraped")

if __name__ == "__main__":
    main()
