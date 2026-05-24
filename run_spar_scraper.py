#!/usr/bin/env python3
"""
═══════════════════════════════════════════════════════════════════════════
RUN SPAR SCRAPER
═══════════════════════════════════════════════════════════════════════════
Standalone script to run the SPAR Austria scraper.

Usage:
    python run_spar_scraper.py [--max-pages N] [--delay SECONDS] [--dry-run]

Options:
    --max-pages N       Limit scraping to N pages (default: all pages)
    --delay SECONDS     Delay between requests in seconds (default: 1.5)
    --dry-run          Scrape but don't save to database
    --test             Test mode: scrape only 2 pages

Examples:
    # Scrape all products
    python run_spar_scraper.py
    
    # Scrape first 10 pages only
    python run_spar_scraper.py --max-pages 10
    
    # Test scraping without saving
    python run_spar_scraper.py --test --dry-run
═══════════════════════════════════════════════════════════════════════════
"""

import sys
import argparse
from datetime import datetime
from scrapers.spar_session_scraper import SparSessionScraper as SparScraper


def main():
    parser = argparse.ArgumentParser(
        description='SPAR Austria Product Scraper',
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
        default=1.5,
        help='Delay between requests in seconds (default: 1.5)'
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
    
    args = parser.parse_args()
    
    # Test mode overrides
    if args.test:
        args.max_pages = 2
        print("[*] TEST MODE: Limiting to 2 pages")
    
    print(f"""
=== SPAR AUSTRIA SCRAPER - Smart Grocery ===

Configuration:
  Max Pages:  {args.max_pages or 'All'}
  Delay:      {args.delay}s
  Dry Run:    {args.dry_run}
  Started:    {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

""")
    
    # Import Flask app and database
    from app import app
    from models.postgres_models import db
    
    with app.app_context():
        # Initialize scraper
        scraper = SparScraper(headless=False)
        
        # Scrape products
        print("[*] Starting product scraping...")
        products = scraper.scrape_all_products(
            max_pages=args.max_pages,
            delay=args.delay
        )
        
        if not products:
            print("\n[!] No products were scraped. Possible reasons:")
            print("    - SPAR website structure has changed")
            print("    - Network connectivity issues")
            print("    - Website blocking automated requests")
            print("\nPlease check the error messages above for details.")
            sys.exit(1)
        
        print(f"\n[[OK]] Successfully scraped {len(products)} products")
        
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
=== OPERATION COMPLETE ===

SCRAPING RESULTS:
  Products scraped:        {len(products)}
  
DATABASE OPERATIONS:
  Linked to BILLA:         {db_stats.get('linked_to_billa', 0)}
  New SPAR-only products:  {db_stats.get('products_added', 0)}
  Products updated:        {db_stats.get('products_updated', 0)}
  Product-stores added:    {db_stats.get('product_stores_added', 0)}
  Product-stores updated:  {db_stats.get('product_stores_updated', 0)}

Completed:                 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
""")
                
                if db_stats.get('database_errors', 0) > 0:
                    print("[!] Some errors occurred during database insertion.")
                    print("    Check the logs above for details.")
                    sys.exit(1)
                else:
                    print("[[OK]] All products successfully saved to database!")
                    
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
