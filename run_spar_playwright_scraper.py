#!/usr/bin/env python3
"""
═══════════════════════════════════════════════════════════════════════════
RUN SPAR PLAYWRIGHT SCRAPER
═══════════════════════════════════════════════════════════════════════════
Standalone script to run the SPAR Austria Playwright scraper.

This version uses a real browser to bypass anti-bot protection.

Prerequisites:
    pip install playwright
    playwright install chromium

Usage:
    python run_spar_playwright_scraper.py [--max-pages N] [--delay SECONDS] [--dry-run] [--visible]

Options:
    --max-pages N       Limit scraping to N pages (default: all pages)
    --delay SECONDS     Delay between requests in seconds (default: 2.0)
    --dry-run          Scrape but don't save to database
    --test             Test mode: scrape only 2 pages
    --visible          Show browser window (not headless)

Examples:
    # Test with visible browser
    python run_spar_playwright_scraper.py --test --visible --dry-run
    
    # Scrape 10 pages
    python run_spar_playwright_scraper.py --max-pages 10
    
    # Full scrape
    python run_spar_playwright_scraper.py
═══════════════════════════════════════════════════════════════════════════
"""

import sys
import argparse
from datetime import datetime

try:
    from scrapers.spar_playwright_scraper import SparPlaywrightScraper
except ImportError as e:
    print(f"[!] Import error: {e}")
    print("\nMake sure Playwright is installed:")
    print("    pip install playwright")
    print("    playwright install chromium")
    sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description='SPAR Austria Product Scraper (Playwright Version)',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    
    parser.add_argument(
        '--max-pages',
        type=int,
        default=None,
        help='Maximum number of pages to scrape (default: all pages)'
    )
    
    parser.add_argument(
        '--delay',
        type=float,
        default=2.0,
        help='Delay between requests in seconds (default: 2.0)'
    )
    
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Scrape products but do not save to database'
    )
    
    parser.add_argument(
        '--test',
        action='store_true',
        help='Test mode: scrape only 2 pages'
    )
    
    parser.add_argument(
        '--visible',
        action='store_true',
        help='Show browser window (not headless)'
    )
    
    args = parser.parse_args()
    
    # Test mode overrides
    if args.test:
        args.max_pages = 2
        print("[*] TEST MODE: Limiting to 2 pages")
    
    print(f"""
╔═══════════════════════════════════════════════════════════════════════════╗
║                SPAR AUSTRIA SCRAPER (PLAYWRIGHT)                          ║
║                      Smart Grocery Project                                ║
╚═══════════════════════════════════════════════════════════════════════════╝

Configuration:
  Max Pages:  {args.max_pages or 'All'}
  Delay:      {args.delay}s
  Dry Run:    {args.dry_run}
  Headless:   {not args.visible}
  Started:    {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

""")
    
    # Import Flask app and database
    from app import app
    from models.postgres_models import db
    
    with app.app_context():
        # Initialize scraper
        scraper = SparPlaywrightScraper(headless=not args.visible)
        
        # Scrape products
        print("[*] Starting product scraping...")
        try:
            products = scraper.scrape_all_products(
                max_pages=args.max_pages,
                delay=args.delay
            )
        except KeyboardInterrupt:
            print("\n[!] Scraping interrupted by user")
            sys.exit(130)
        except Exception as e:
            print(f"\n[!] Scraping error: {e}")
            import traceback
            traceback.print_exc()
            sys.exit(1)
        
        if not products:
            print("\n[!] No products were scraped. Possible reasons:")
            print("    - SPAR website structure has changed")
            print("    - Network connectivity issues")
            print("    - Selectors need updating")
            print("\nPlease check the error messages above for details.")
            sys.exit(1)
        
        print(f"\n[✓] Successfully scraped {len(products)} products")
        
        # Display sample products
        print("\n" + "="*80)
        print("SAMPLE PRODUCTS (first 5)")
        print("="*80)
        for i, product in enumerate(products[:5], 1):
            print(f"\n{i}. {product['name']}")
            print(f"   Brand: {product.get('brand', 'N/A')}")
            print(f"   Price: €{product['price']:.2f}")
            if product.get('original_price'):
                print(f"   Original Price: €{product['original_price']:.2f} (-{product.get('discount_percentage', 0):.0f}%)")
            if product.get('offer_end_date'):
                print(f"   Offer ends: {product['offer_end_date'].strftime('%d.%m.%Y')}")
            print(f"   Unit: {product.get('unit', 'N/A')} {product.get('size_normalized', '')}")
        
        # Save to database
        if args.dry_run:
            print("\n[*] DRY RUN MODE: Skipping database insertion")
            print(f"[*] Would have inserted {len(products)} products")
        else:
            print("\n[*] Saving products to database...")
            try:
                db_stats = scraper.save_to_database(products, db.session)
                
                # Print final statistics
                print(f"""
╔═══════════════════════════════════════════════════════════════════════════╗
║                         OPERATION COMPLETE                                ║
╚═══════════════════════════════════════════════════════════════════════════╝

SCRAPING RESULTS:
  Products scraped:        {len(products)}
  
DATABASE OPERATIONS:
  Products added:          {db_stats['products_added']}
  Products updated:        {db_stats['products_updated']}
  Product-stores added:    {db_stats['product_stores_added']}
  Product-stores updated:  {db_stats['product_stores_updated']}
  Promotions added:        {db_stats['promotions_added']}
  
ERRORS:
  Validation errors:       {db_stats['validation_errors']}
  Database errors:         {db_stats['database_errors']}

Completed:                 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
""")
                
                if db_stats['database_errors'] > 0:
                    print("[!] Some errors occurred during database insertion.")
                    print("    Check the logs above for details.")
                    sys.exit(1)
                else:
                    print("[✓] All products successfully saved to database!")
                    
            except Exception as e:
                print(f"\n[!] FATAL ERROR during database operations: {e}")
                import traceback
                traceback.print_exc()
                sys.exit(1)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n[!] Scraping interrupted by user")
        sys.exit(130)
    except Exception as e:
        print(f"\n[!] FATAL ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
