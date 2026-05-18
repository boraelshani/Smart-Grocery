#!/usr/bin/env python3
"""
Quick test to verify SPAR image extraction is working correctly
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from scrapers.spar_playwright_scraper import SparPlaywrightScraper


def test_image_extraction():
    """Test that we're getting real product images, not placeholders."""
    print("""
╔═══════════════════════════════════════════════════════════════════════════╗
║                    SPAR IMAGE EXTRACTION TEST                             ║
╚═══════════════════════════════════════════════════════════════════════════╝

Testing first 3 pages to verify image extraction...
""")
    
    scraper = SparPlaywrightScraper(headless=False)
    scraper.start_browser()
    
    try:
        # Test first 3 pages
        all_products = []
        for page in range(1, 4):
            url = f"https://www.spar.at/produktwelt/suche?search=&page={page}"
            print(f"\n[*] Testing page {page}...")
            products = scraper._scrape_search_page(url, page)
            all_products.extend(products)
            print(f"[✓] Found {len(products)} products")
        
        # Analyze images
        print(f"\n{'='*80}")
        print("IMAGE ANALYSIS")
        print(f"{'='*80}\n")
        
        total = len(all_products)
        with_images = sum(1 for p in all_products if p.get('image_url'))
        placeholders = sum(1 for p in all_products if p.get('image_url') and any(
            x in p['image_url'].lower() for x in ['veggie', 'icon', 'placeholder', 'badge', 'label']
        ))
        real_images = with_images - placeholders
        
        print(f"Total products:      {total}")
        print(f"With images:         {with_images} ({with_images/total*100:.1f}%)")
        print(f"Real images:         {real_images} ({real_images/total*100:.1f}%)")
        print(f"Placeholder images:  {placeholders} ({placeholders/total*100:.1f}%)")
        
        # Show sample images
        print(f"\n{'='*80}")
        print("SAMPLE IMAGES (first 5 products)")
        print(f"{'='*80}\n")
        
        for i, product in enumerate(all_products[:5], 1):
            print(f"{i}. {product['name'][:50]}")
            if product.get('image_url'):
                url = product['image_url']
                is_placeholder = any(x in url.lower() for x in ['veggie', 'icon', 'placeholder', 'badge', 'label'])
                status = "❌ PLACEHOLDER" if is_placeholder else "✅ REAL IMAGE"
                print(f"   {status}")
                print(f"   {url[:100]}")
            else:
                print(f"   ⚠️  NO IMAGE")
            print()
        
        # Verdict
        print(f"{'='*80}")
        if placeholders == 0:
            print("✅ SUCCESS! No placeholder images detected.")
            print("✅ Image extraction is working correctly!")
        elif placeholders < with_images * 0.1:  # Less than 10%
            print("⚠️  MOSTLY GOOD: Some placeholders detected but mostly real images.")
        else:
            print("❌ ISSUE: Too many placeholder images detected.")
            print("   Need to improve image filtering.")
        print(f"{'='*80}\n")
        
    finally:
        scraper.stop_browser()


if __name__ == "__main__":
    test_image_extraction()
