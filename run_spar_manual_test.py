#!/usr/bin/env python3
"""
SPAR Manual Interaction Test
This opens a browser and lets YOU interact with it first, then scrapes.
"""

import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from playwright.sync_api import sync_playwright
from app import app
from models.postgres_models import db, Product, ProductStore, Store
from datetime import datetime, timezone
from decimal import Decimal
import re


def extract_products(page):
    """Extract products from current page."""
    products = []
    
    try:
        product_elements = page.query_selector_all('[class*="product-card"], [class*="product-item"]')
        
        for elem in product_elements:
            try:
                # Name
                name_elem = elem.query_selector('h3, h4, [class*="name"]')
                if not name_elem:
                    continue
                name = name_elem.inner_text().strip()
                if not name:
                    continue
                
                # Clean name
                name = re.sub(r'([a-z])([A-Z])', r'\1 \2', name)
                name = ' '.join(name.split())
                
                # Price
                price = None
                try:
                    price_elem = elem.query_selector('[class*="price"]:not([class*="old"])')
                    if price_elem:
                        price_text = price_elem.inner_text().strip()
                        price_text = price_text.replace('€', '').replace(',', '.').strip()
                        price = float(price_text)
                except:
                    pass
                
                if not price or price <= 0:
                    continue
                
                # Brand
                brand = None
                for kb in ['SPAR', 'S-BUDGET', 'DESPAR']:
                    if name.upper().startswith(kb):
                        brand = kb
                        break
                
                # Image
                image_url = None
                img_elem = elem.query_selector('img')
                if img_elem:
                    for attr in ['data-src', 'data-lazy-src', 'srcset', 'src']:
                        url = img_elem.get_attribute(attr)
                        if url and not any(x in url.lower() for x in ['placeholder', 'icon', 'veggie', 'badge']):
                            if ' ' in url:
                                url = url.split(',')[-1].strip().split()[0]
                            if not url.startswith('http'):
                                url = 'https:' + url if url.startswith('//') else 'https://www.spar.at' + url
                            image_url = url
                            break
                
                products.append({
                    'name': name,
                    'brand': brand,
                    'price': price,
                    'image_url': image_url
                })
            except:
                continue
        
        return products
    except:
        return []


def generate_fingerprint(name, brand):
    """Generate fingerprint."""
    name_norm = re.sub(r'[^\w\s]', '', name.lower()).strip()
    brand_norm = re.sub(r'[^\w\s]', '', (brand or '').lower()).strip()
    parts = [p for p in [brand_norm, name_norm] if p]
    return '_'.join(parts)


def main():
    """Main execution."""
    print("\n" + "="*80)
    print("SPAR MANUAL INTERACTION TEST")
    print("="*80)
    print("\nThis test will:")
    print("1. Open SPAR website in a browser")
    print("2. Let YOU interact with it (scroll, click, etc.)")
    print("3. Then scrape the products")
    print("\nThis proves whether the issue is:")
    print("  - Code bug (if manual interaction works)")
    print("  - Bot protection (if even manual doesn't work)")
    print("\n" + "="*80 + "\n")
    
    input("Press ENTER to start...")
    
    playwright = sync_playwright().start()
    browser = playwright.chromium.launch(headless=False)
    context = browser.new_context(
        viewport={'width': 1920, 'height': 1080},
        user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
    )
    page = context.new_page()
    
    all_products = []
    seen_fingerprints = set()
    
    try:
        # Go to SPAR
        print("\n[*] Opening SPAR website...")
        page.goto("https://www.spar.at/produktwelt/suche", wait_until='domcontentloaded')
        time.sleep(3)
        
        print("\n" + "="*80)
        print("MANUAL INTERACTION TIME")
        print("="*80)
        print("\nThe browser is now open. Please:")
        print("1. Scroll down the page")
        print("2. Look at the products")
        print("3. Click on page 2 at the bottom")
        print("4. See if different products appear")
        print("\nThen come back here and press ENTER")
        print("="*80 + "\n")
        
        input("Press ENTER when you've tested pagination manually...")
        
        # Now let's test programmatically
        print("\n[*] Now testing programmatically...")
        
        # Go back to page 1
        print("\n[*] Going to page 1...")
        page.goto("https://www.spar.at/produktwelt/suche", wait_until='domcontentloaded')
        time.sleep(2)
        
        # Extract page 1 products
        print("[*] Extracting page 1 products...")
        page1_products = extract_products(page)
        print(f"    Found {len(page1_products)} products on page 1")
        if page1_products:
            print(f"    First: {page1_products[0]['name'][:50]}")
        
        for p in page1_products:
            fp = generate_fingerprint(p['name'], p.get('brand'))
            if fp not in seen_fingerprints:
                seen_fingerprints.add(fp)
                all_products.append(p)
        
        # Try to go to page 2
        print("\n[*] Trying to navigate to page 2...")
        page.goto("https://www.spar.at/produktwelt/suche?page=2", wait_until='domcontentloaded')
        time.sleep(2)
        
        # Check URL
        current_url = page.url
        print(f"    Current URL: {current_url}")
        
        if "page=2" in current_url:
            print("    ✅ Stayed on page 2!")
        else:
            print("    ❌ Redirected back to page 1")
        
        # Extract page 2 products
        print("[*] Extracting page 2 products...")
        page2_products = extract_products(page)
        print(f"    Found {len(page2_products)} products on page 2")
        if page2_products:
            print(f"    First: {page2_products[0]['name'][:50]}")
        
        new_count = 0
        for p in page2_products:
            fp = generate_fingerprint(p['name'], p.get('brand'))
            if fp not in seen_fingerprints:
                seen_fingerprints.add(fp)
                all_products.append(p)
                new_count += 1
        
        print(f"    New products: {new_count}")
        
        # Results
        print("\n" + "="*80)
        print("TEST RESULTS")
        print("="*80)
        print(f"\nTotal unique products: {len(all_products)}")
        print(f"Page 1 products: {len(page1_products)}")
        print(f"Page 2 products: {len(page2_products)}")
        print(f"New on page 2: {new_count}")
        
        if new_count > 0:
            print("\n✅ SUCCESS! Pagination works!")
            print("   Different products on page 2")
            print("   The code is correct, SPAR allows pagination")
        else:
            print("\n❌ PAGINATION BLOCKED")
            print("   Same products on page 2")
            print("   SPAR's bot protection is redirecting")
        
        # Compare with manual test
        print("\n" + "="*80)
        print("COMPARISON")
        print("="*80)
        print("\nDid YOU see different products when you clicked page 2 manually?")
        manual_worked = input("Enter 'yes' or 'no': ").lower().strip()
        
        if manual_worked == 'yes' and new_count == 0:
            print("\n🔍 DIAGNOSIS:")
            print("   Manual: Works ✅")
            print("   Automated: Blocked ❌")
            print("   Conclusion: SPAR detects automation")
            print("\n   This is NOT a code bug.")
            print("   This is SPAR's intentional bot protection.")
        elif manual_worked == 'no':
            print("\n🔍 DIAGNOSIS:")
            print("   Manual: Blocked ❌")
            print("   Automated: Blocked ❌")
            print("   Conclusion: SPAR blocks ALL pagination")
            print("\n   Even manual users can't paginate!")
            print("   This might be a SPAR website issue.")
        else:
            print("\n🔍 DIAGNOSIS:")
            print("   Both manual and automated work!")
            print("   Pagination is functional.")
        
        # Save products
        if len(all_products) > 0:
            print(f"\n[*] Saving {len(all_products)} products to database...")
            
            with app.app_context():
                store = db.session.query(Store).filter_by(store_id='spar').first()
                if not store:
                    store = Store(store_id='spar', name='SPAR', 
                                website='https://www.spar.at', country='AT', active=True)
                    db.session.add(store)
                    db.session.commit()
                
                added = 0
                for pd in all_products:
                    try:
                        fp = generate_fingerprint(pd['name'], pd.get('brand'))
                        
                        product = db.session.query(Product).filter_by(fingerprint=fp).first()
                        if not product:
                            product = Product(
                                fingerprint=fp,
                                name=pd['name'],
                                name_de=pd['name'],
                                brand=pd.get('brand'),
                                default_image_url=pd.get('image_url'),
                                created_at=datetime.now(timezone.utc),
                                updated_at=datetime.now(timezone.utc)
                            )
                            db.session.add(product)
                            db.session.flush()
                        
                        ps = db.session.query(ProductStore).filter_by(
                            product_id=product.id, store_id='spar').first()
                        if not ps:
                            ps = ProductStore(
                                product_id=product.id,
                                store_id='spar',
                                base_price=Decimal(str(pd['price'])),
                                is_available=True,
                                last_seen=datetime.now(timezone.utc),
                                created_at=datetime.now(timezone.utc)
                            )
                            db.session.add(ps)
                            added += 1
                        else:
                            ps.base_price = Decimal(str(pd['price']))
                            ps.is_available = True
                            ps.last_seen = datetime.now(timezone.utc)
                    except:
                        continue
                
                db.session.commit()
                print(f"[✓] Saved {added} new products")
        
        print("\n" + "="*80)
        print("RECOMMENDATIONS")
        print("="*80)
        
        if new_count == 0:
            print("\nSince pagination doesn't work, you should:")
            print("\n1. ✅ Focus on Billa, Hofer, Lidl (they work!)")
            print("   Get 50,000+ products from stores without bot protection")
            print("\n2. 📧 Contact SPAR for official API")
            print("   Email: info@spar.at")
            print("\n3. 🔧 Build browser extension")
            print("   Let users scrape as they browse")
            print("\n4. ✅ Keep the ~150 SPAR products you have")
            print("   Update them regularly")
        else:
            print("\n✅ Pagination works! You can scrape all products!")
        
        print("\n" + "="*80 + "\n")
        
    finally:
        input("\nPress ENTER to close browser...")
        browser.close()
        playwright.stop()


if __name__ == "__main__":
    main()
