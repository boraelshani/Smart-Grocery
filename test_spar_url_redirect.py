#!/usr/bin/env python3
"""
Test SPAR URL behavior to see if it redirects
"""

import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from playwright.sync_api import sync_playwright


def test_url_redirect():
    """Test if SPAR redirects page URLs."""
    print("""
╔═══════════════════════════════════════════════════════════════════════════╗
║                    SPAR URL REDIRECT TEST                                 ║
╚═══════════════════════════════════════════════════════════════════════════╝

Testing different URL formats to see which one works...
""")
    
    playwright = sync_playwright().start()
    browser = playwright.chromium.launch(headless=False)
    context = browser.new_context(
        viewport={'width': 1920, 'height': 1080},
        user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
    )
    page = context.new_page()
    
    # Test different URL formats
    url_formats = [
        ("Format 1", "https://www.spar.at/produktwelt/suche?search=&page=2"),
        ("Format 2", "https://www.spar.at/produktwelt/suche?page=2&search="),
        ("Format 3", "https://www.spar.at/produktwelt/suche?page=2"),
        ("Format 4", "https://www.spar.at/produktwelt/suche?search=*&page=2"),
    ]
    
    try:
        for name, url in url_formats:
            print(f"\n{'='*80}")
            print(f"Testing {name}")
            print(f"URL: {url}")
            print(f"{'='*80}")
            
            # Navigate to URL
            page.goto(url, wait_until='domcontentloaded', timeout=30000)
            time.sleep(3)
            
            # Check final URL after any redirects
            final_url = page.url
            print(f"Final URL: {final_url}")
            
            # Check if redirected
            if "page=2" in final_url:
                print("✅ STAYED ON PAGE 2")
            elif "page=1" in final_url or final_url == "https://www.spar.at/produktwelt/suche":
                print("❌ REDIRECTED TO PAGE 1")
            else:
                print(f"⚠️  UNKNOWN: {final_url}")
            
            # Try to find products
            try:
                page.wait_for_selector('[class*="product"]', timeout=5000)
                products = page.query_selector_all('[class*="product-card"]')
                print(f"Products found: {len(products)}")
                
                if products:
                    first_product = products[0].query_selector('h3, h4, [class*="name"]')
                    if first_product:
                        name = first_product.inner_text().strip()[:50]
                        print(f"First product: {name}")
            except:
                print("No products found")
            
            time.sleep(2)
        
        # Now test clicking pagination
        print(f"\n{'='*80}")
        print("Testing CLICK PAGINATION")
        print(f"{'='*80}")
        
        # Go to page 1
        page.goto("https://www.spar.at/produktwelt/suche", wait_until='domcontentloaded')
        time.sleep(3)
        
        # Get first product on page 1
        try:
            products = page.query_selector_all('[class*="product-card"]')
            if products:
                first_elem = products[0].query_selector('h3, h4, [class*="name"]')
                page1_first = first_elem.inner_text().strip()[:50] if first_elem else "Unknown"
                print(f"Page 1 first product: {page1_first}")
        except:
            page1_first = "Unknown"
        
        # Try to find and click next button
        print("\nLooking for pagination buttons...")
        
        # Scroll to bottom to see pagination
        page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
        time.sleep(1)
        
        # Try to find pagination
        pagination_selectors = [
            'a[aria-label*="2"]',
            'button[aria-label*="2"]',
            '.pagination a:has-text("2")',
            '[class*="pagination"] a:has-text("2")',
            'a:has-text("2")',
        ]
        
        clicked = False
        for selector in pagination_selectors:
            try:
                button = page.query_selector(selector)
                if button:
                    print(f"Found pagination with selector: {selector}")
                    button.click()
                    clicked = True
                    break
            except:
                continue
        
        if clicked:
            print("✅ Clicked page 2 button")
            time.sleep(3)
            
            # Check URL after click
            final_url = page.url
            print(f"URL after click: {final_url}")
            
            # Get first product on page 2
            try:
                products = page.query_selector_all('[class*="product-card"]')
                if products:
                    first_elem = products[0].query_selector('h3, h4, [class*="name"]')
                    page2_first = first_elem.inner_text().strip()[:50] if first_elem else "Unknown"
                    print(f"Page 2 first product: {page2_first}")
                    
                    if page1_first != page2_first:
                        print("\n✅ SUCCESS! Different products after clicking!")
                    else:
                        print("\n❌ SAME PRODUCTS after clicking")
            except:
                print("Could not get products after click")
        else:
            print("❌ Could not find pagination button")
        
        print(f"\n{'='*80}")
        print("RECOMMENDATION")
        print(f"{'='*80}")
        
        # Determine best approach
        working_formats = []
        for name, url in url_formats:
            page.goto(url, wait_until='domcontentloaded')
            time.sleep(2)
            if "page=2" in page.url:
                working_formats.append(name)
        
        if working_formats:
            print(f"✅ URL navigation works with: {', '.join(working_formats)}")
            print("   Use URL-based scraping")
        elif clicked:
            print("✅ Click-based pagination works")
            print("   Use click-based scraping")
        else:
            print("❌ Neither URL nor click pagination works")
            print("   SPAR has strong bot protection")
            print("   Recommendations:")
            print("   1. Try slower delays (5+ seconds)")
            print("   2. Try undetected-chromedriver")
            print("   3. Focus on other stores")
            print("   4. Contact SPAR for API access")
        
    finally:
        input("\nPress ENTER to close browser...")
        browser.close()
        playwright.stop()


if __name__ == "__main__":
    test_url_redirect()
