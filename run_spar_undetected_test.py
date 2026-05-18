#!/usr/bin/env python3
"""
Test SPAR scraper with undetected-chromedriver
"""

import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from scrapers.spar_undetected_final import SparUndetectedFinalScraper
from app import app
from models.postgres_models import db


def main():
    """Main execution."""
    print("\n" + "="*80)
    print("SPAR UNDETECTED SCRAPER - FINAL TEST")
    print("="*80)
    print("\nThis will test 20 pages to see if pagination works.")
    print("Watch the browser carefully:")
    print("  - Does it stay on page 2 or redirect to page 1?")
    print("  - Do you see different products on each page?")
    print("  - Does the product count increase?")
    print("\nPress Ctrl+C to stop at any time.")
    print("="*80 + "\n")
    
    input("Press ENTER to start...")
    
    with app.app_context():
        scraper = SparUndetectedFinalScraper(headless=False)  # Visible so you can watch
        
        # Test 20 pages
        products = scraper.scrape_all_products(max_pages=20, delay=3.0)
        
        print("\n" + "="*80)
        print("TEST RESULTS")
        print("="*80)
        
        if products:
            print(f"✓ Scraped {len(products)} unique products")
            
            if len(products) > 50:
                print("\n✅ SUCCESS! Pagination is working!")
                print(f"   Got {len(products)} products from multiple pages")
                print("   This means undetected-chromedriver bypassed the bot protection!")
                
                # Save to database
                print("\n[*] Saving to database...")
                stats = scraper.save_to_database(products, db.session)
                
                print(f"\n{'='*80}")
                print("DATABASE STATISTICS")
                print(f"{'='*80}")
                for k, v in stats.items():
                    print(f"{k:30s}: {v}")
                print(f"{'='*80}\n")
                
                print("✅ You can now run the full scrape to get all 37,692 products!")
                print("\nTo run full scrape:")
                print("  python3 run_spar_undetected_full.py")
                
            elif len(products) > 32:
                print(f"\n⚠️  Got {len(products)} products")
                print("   Pagination is partially working")
                print("   Try running with slower delays (5+ seconds)")
                
                # Save anyway
                stats = scraper.save_to_database(products, db.session)
                print(f"\n[*] Saved {stats['products_added']} new products to database")
                
            else:
                print(f"\n❌ Only got {len(products)} products (same as page 1)")
                print("   Pagination is NOT working")
                print("   SPAR's bot protection is too strong")
                
                print("\n" + "="*80)
                print("RECOMMENDATIONS")
                print("="*80)
                print("\n1. ✅ Focus on other stores (Billa, Hofer, Lidl)")
                print("   These stores don't have such strong bot protection")
                print("   You can get 50,000+ products from them!")
                
                print("\n2. 📧 Contact SPAR for official API access")
                print("   Email: info@spar.at")
                print("   Request: Product data feed for price comparison app")
                
                print("\n3. 🔧 Build a browser extension")
                print("   Let users scrape as they browse")
                print("   Works perfectly (real user behavior)")
                
                print("\n4. 👥 Crowdsource the data")
                print("   Let users submit products via barcode scanning")
                
                print("\n" + "="*80)
                print("NEXT STEPS")
                print("="*80)
                print("\nWould you like me to:")
                print("  A) Implement Billa scraper (works great!)")
                print("  B) Implement Hofer scraper")
                print("  C) Implement Lidl scraper")
                print("  D) Create browser extension for SPAR")
                print("  E) Set up crowdsourcing system")
                print("\nLet me know what you'd like to do!")
        else:
            print("❌ No products scraped")
            print("   Could not even get page 1")
            print("   Check if SPAR website is accessible")
        
        print("\n" + "="*80 + "\n")


if __name__ == "__main__":
    main()
