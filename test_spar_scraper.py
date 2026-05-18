#!/usr/bin/env python3
"""
═══════════════════════════════════════════════════════════════════════════
TEST SPAR SCRAPER
═══════════════════════════════════════════════════════════════════════════
Quick test script to verify the SPAR scraper is working correctly.

This script:
1. Tests HTTP connection to SPAR
2. Scrapes 1 page
3. Validates extracted data
4. Shows sample products
5. Does NOT save to database

Usage:
    python test_spar_scraper.py
═══════════════════════════════════════════════════════════════════════════
"""

import sys
from scrapers.spar_scraper import SparScraper


def test_connection():
    """Test if we can connect to SPAR website."""
    print("\n" + "="*80)
    print("TEST 1: Connection Test")
    print("="*80)
    
    scraper = SparScraper()
    try:
        response = scraper.session.get(scraper.base_url, timeout=10)
        if response.status_code == 200:
            print("[✓] Successfully connected to SPAR website")
            return True
        else:
            print(f"[✗] Connection failed with status code: {response.status_code}")
            return False
    except Exception as e:
        print(f"[✗] Connection error: {e}")
        return False


def test_scraping():
    """Test scraping a single page."""
    print("\n" + "="*80)
    print("TEST 2: Scraping Test (1 page)")
    print("="*80)
    
    scraper = SparScraper()
    try:
        products = scraper.scrape_page(page=1)
        
        if not products:
            print("[✗] No products found. Possible reasons:")
            print("    - Website structure has changed")
            print("    - Page is empty")
            print("    - Selectors need updating")
            return False, []
        
        print(f"[✓] Successfully scraped {len(products)} products")
        return True, products
        
    except Exception as e:
        print(f"[✗] Scraping error: {e}")
        import traceback
        traceback.print_exc()
        return False, []


def test_data_validation(products):
    """Test data validation."""
    print("\n" + "="*80)
    print("TEST 3: Data Validation")
    print("="*80)
    
    scraper = SparScraper()
    valid_count = 0
    invalid_count = 0
    errors = []
    
    for product in products:
        is_valid, error_msg = scraper.validate_product_data(product)
        if is_valid:
            valid_count += 1
        else:
            invalid_count += 1
            errors.append((product.get('name', 'Unknown'), error_msg))
    
    print(f"Valid products:   {valid_count}/{len(products)}")
    print(f"Invalid products: {invalid_count}/{len(products)}")
    
    if errors:
        print("\nValidation Errors:")
        for name, error in errors[:5]:  # Show first 5 errors
            print(f"  - {name}: {error}")
    
    if valid_count > 0:
        print("[✓] Data validation passed")
        return True
    else:
        print("[✗] All products failed validation")
        return False


def show_sample_products(products, count=5):
    """Display sample products."""
    print("\n" + "="*80)
    print(f"SAMPLE PRODUCTS (showing {min(count, len(products))} of {len(products)})")
    print("="*80)
    
    for i, product in enumerate(products[:count], 1):
        print(f"\n{i}. {product['name']}")
        print(f"   {'─' * 70}")
        print(f"   Brand:           {product.get('brand', 'N/A')}")
        print(f"   Price:           €{product['price']:.2f}")
        
        if product.get('original_price'):
            discount = product.get('discount_percentage', 0)
            print(f"   Original Price:  €{product['original_price']:.2f}")
            print(f"   Discount:        {discount:.0f}% OFF")
            print(f"   🔥 ON SALE!")
        
        if product.get('offer_end_date'):
            print(f"   Offer ends:      {product['offer_end_date'].strftime('%d.%m.%Y')}")
        
        if product.get('unit') and product.get('size_normalized'):
            print(f"   Size:            {product['size_normalized']}{product['unit']}")
        
        if product.get('image_url'):
            print(f"   Image:           {product['image_url'][:60]}...")
        
        if product.get('product_url'):
            print(f"   URL:             {product['product_url'][:60]}...")


def test_fingerprinting(products):
    """Test product fingerprinting for deduplication."""
    print("\n" + "="*80)
    print("TEST 4: Fingerprinting Test")
    print("="*80)
    
    scraper = SparScraper()
    fingerprints = set()
    duplicates = 0
    
    for product in products:
        fp = scraper._generate_fingerprint(
            product['name'],
            product.get('brand', ''),
            product.get('unit', ''),
            product.get('size_normalized')
        )
        
        if fp in fingerprints:
            duplicates += 1
        else:
            fingerprints.add(fp)
    
    print(f"Unique fingerprints: {len(fingerprints)}")
    print(f"Duplicates found:    {duplicates}")
    
    if duplicates == 0:
        print("[✓] No duplicates found - fingerprinting working correctly")
    else:
        print(f"[!] Found {duplicates} duplicates - this is normal if products appear multiple times")
    
    # Show sample fingerprints
    print("\nSample Fingerprints:")
    for i, fp in enumerate(list(fingerprints)[:3], 1):
        print(f"  {i}. {fp}")
    
    return True


def main():
    """Run all tests."""
    print("""
╔═══════════════════════════════════════════════════════════════════════════╗
║                    SPAR SCRAPER TEST SUITE                                ║
║                                                                           ║
║  This script tests the SPAR scraper without saving to database.          ║
╚═══════════════════════════════════════════════════════════════════════════╝
""")
    
    results = {
        'connection': False,
        'scraping': False,
        'validation': False,
        'fingerprinting': False
    }
    
    # Test 1: Connection
    results['connection'] = test_connection()
    if not results['connection']:
        print("\n[!] Connection test failed. Cannot proceed with other tests.")
        sys.exit(1)
    
    # Test 2: Scraping
    results['scraping'], products = test_scraping()
    if not results['scraping'] or not products:
        print("\n[!] Scraping test failed. Cannot proceed with other tests.")
        sys.exit(1)
    
    # Test 3: Validation
    results['validation'] = test_data_validation(products)
    
    # Test 4: Fingerprinting
    results['fingerprinting'] = test_fingerprinting(products)
    
    # Show sample products
    show_sample_products(products, count=5)
    
    # Summary
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    
    all_passed = all(results.values())
    
    for test_name, passed in results.items():
        status = "[✓]" if passed else "[✗]"
        print(f"{status} {test_name.replace('_', ' ').title()}")
    
    print("="*80)
    
    if all_passed:
        print("""
╔═══════════════════════════════════════════════════════════════════════════╗
║                         ALL TESTS PASSED! ✓                               ║
╚═══════════════════════════════════════════════════════════════════════════╝

The SPAR scraper is working correctly. You can now run:

  python run_spar_scraper.py --test        # Test with 2 pages
  python run_spar_scraper.py --max-pages 5 # Scrape 5 pages
  python run_spar_scraper.py               # Full scrape

""")
        sys.exit(0)
    else:
        print("""
╔═══════════════════════════════════════════════════════════════════════════╗
║                         SOME TESTS FAILED ✗                               ║
╚═══════════════════════════════════════════════════════════════════════════╝

Please review the errors above and fix them before running the full scraper.

Common issues:
  - Website structure changed (update selectors)
  - Network connectivity problems
  - Data format changes

""")
        sys.exit(1)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n[!] Tests interrupted by user")
        sys.exit(130)
    except Exception as e:
        print(f"\n[!] FATAL ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
