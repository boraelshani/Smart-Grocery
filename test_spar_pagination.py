#!/usr/bin/env python3
"""
Test SPAR pagination to see what's actually happening
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from scrapers.spar_playwright_scraper import SparPlaywrightScraper


def test_pagination():
    """Test if pagination is actually working."""
    print("""
╔═══════════════════════════════════════════════════════════════════════════╗
║                    SPAR PAGINATION TEST                                   ║
╚═══════════════════════════════════════════════════════════════════════════╝

Testing first 5 pages to see if we get different products...
""")
    
    scraper = SparPlaywrightScraper(headless=False)  # Visible so you can see
    scraper.start_browser()
    
    try:
        all_product_names = []
        
        for page in range(1, 6):
            url = f"https://www.spar.at/produktwelt/suche?search=&page={page}"
            print(f"\n{'='*80}")
            print(f"PAGE {page}: {url}")
            print(f"{'='*80}")
            
            products = scraper._scrape_search_page(url, page)
            
            if products:
                print(f"Found {len(products)} products")
                print(f"\nFirst 3 products on page {page}:")
                for i, p in enumerate(products[:3], 1):
                    print(f"  {i}. {p['name'][:60]}")
                
                # Track all names
                page_names = [p['name'] for p in products]
                all_product_names.append({
                    'page': page,
                    'names': page_names,
                    'first': page_names[0] if page_names else None
                })
            else:
                print(f"❌ No products found on page {page}")
        
        # Analysis
        print(f"\n{'='*80}")
        print("ANALYSIS")
        print(f"{'='*80}\n")
        
        # Check if first product is the same on all pages
        first_products = [p['first'] for p in all_product_names if p['first']]
        
        if len(set(first_products)) == 1:
            print("❌ PROBLEM DETECTED!")
            print(f"   All pages show the same first product: {first_products[0][:50]}")
            print("   This means pagination is NOT working.")
            print("\n   Possible causes:")
            print("   1. SPAR detects automation and serves cached results")
            print("   2. URL parameters are not being respected")
            print("   3. Need to click pagination buttons instead of URL navigation")
        else:
            print("✅ PAGINATION WORKS!")
            print("   Different products on different pages:")
            for p in all_product_names:
                print(f"   Page {p['page']}: {p['first'][:50]}")
        
        # Check for duplicates across pages
        all_names = []
        for p in all_product_names:
            all_names.extend(p['names'])
        
        unique_names = set(all_names)
        total_names = len(all_names)
        unique_count = len(unique_names)
        duplicate_count = total_names - unique_count
        
        print(f"\n{'='*80}")
        print("DUPLICATE CHECK")
        print(f"{'='*80}")
        print(f"Total products seen:     {total_names}")
        print(f"Unique products:         {unique_count}")
        print(f"Duplicates:              {duplicate_count}")
        
        if duplicate_count > total_names * 0.5:
            print("\n❌ HIGH DUPLICATION RATE!")
            print("   More than 50% duplicates - pagination likely not working")
        elif duplicate_count > 0:
            print("\n⚠️  Some duplicates (normal)")
        else:
            print("\n✅ No duplicates - pagination working perfectly!")
        
    finally:
        input("\nPress ENTER to close browser...")
        scraper.stop_browser()


if __name__ == "__main__":
    test_pagination()
