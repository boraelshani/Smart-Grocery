"""
═══════════════════════════════════════════════════════════════════════════
SPAR AUSTRIA SCRAPER - CLICK NEXT BUTTON VERSION
═══════════════════════════════════════════════════════════════════════════
This scraper clicks the "Next" button instead of changing URLs.
This is the correct approach for SPAR's pagination!
═══════════════════════════════════════════════════════════════════════════
"""

import re
import time
from datetime import datetime, timezone
from typing import List, Dict, Optional, Tuple
from decimal import Decimal

try:
    from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
except ImportError:
    print("[!] Playwright not installed")
    exit(1)


class SparClickNextScraper:
    """SPAR scraper that clicks the Next button for pagination."""
    
    def __init__(self, headless=True):
        self.headless = headless
        self.base_url = "https://www.spar.at"
        self.store_id = "spar"
        
        self.stats = {
            "products_scraped": 0,
            "pages_scraped": 0,
            "errors": 0,
            "skipped": 0
        }
    
    def scrape_all_products(self, max_pages: int = None, delay: float = 2.0) -> List[Dict]:
        """
        Scrape all products by clicking the Next button.
        
        Args:
            max_pages: Maximum pages to scrape (None = all pages)
            delay: Delay between page clicks in seconds
            
        Returns:
            List of all products
        """
        print(f"\n{'='*80}")
        print("SPAR CLICK NEXT SCRAPER - Starting")
        print(f"Strategy: Click 'Next' button for pagination")
        print(f"{'='*80}\n")
        
        all_products = []
        seen_fingerprints = set()
        
        if max_pages is None:
            max_pages = 1178
        
        with sync_playwright() as p:
            # Launch browser
            print("[*] Starting browser...")
            browser = p.chromium.launch(
                headless=self.headless,
                args=[
                    '--disable-blink-features=AutomationControlled',
                    '--disable-dev-shm-usage',
                    '--no-sandbox',
                ]
            )
            
            # Create context with realistic settings
            context = browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                locale='de-AT',
                timezone_id='Europe/Vienna',
            )
            
            page = context.new_page()
            
            # Anti-detection
            page.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
                Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});
                Object.defineProperty(navigator, 'languages', {get: () => ['de-AT', 'de', 'en']});
                window.chrome = {runtime: {}};
            """)
            
            try:
                # Navigate to first page
                print("[*] Loading SPAR products page...")
                page.goto(f"{self.base_url}/produktwelt/suche", 
                         wait_until='domcontentloaded', timeout=30000)
                time.sleep(3)
                
                # Accept cookies if present
                try:
                    cookie_button = page.query_selector('button:has-text("Akzeptieren"), button:has-text("Accept")')
                    if cookie_button:
                        cookie_button.click()
                        print("[*] Accepted cookies")
                        time.sleep(1)
                except:
                    pass
                
                # Wait for products to load
                try:
                    page.wait_for_selector('[class*="product"]', timeout=10000)
                    print("[✓] Products loaded")
                except:
                    print("[!] Could not find products")
                    browser.close()
                    return []
                
                page_num = 1
                consecutive_no_new = 0
                
                # Loop through pages by clicking Next
                while page_num <= max_pages:
                    print(f"\n[*] Page {page_num}/{max_pages}")
                    
                    # Scroll to load images
                    page.evaluate('window.scrollTo(0, document.body.scrollHeight / 2)')
                    time.sleep(0.5)
                    page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
                    time.sleep(1)
                    
                    # Extract products from current page
                    products = self._extract_products_from_page(page)
                    
                    if not products:
                        print(f"    [!] No products found")
                        break
                    
                    # Check for new products
                    new_count = 0
                    for product in products:
                        fp = self._generate_fingerprint(
                            product['name'],
                            product.get('brand', ''),
                            product.get('unit', ''),
                            product.get('size_normalized')
                        )
                        if fp not in seen_fingerprints:
                            seen_fingerprints.add(fp)
                            all_products.append(product)
                            new_count += 1
                    
                    print(f"[✓] Page {page_num} | New: {new_count} | Total: {len(all_products)}")
                    
                    if products:
                        print(f"    First: {products[0]['name'][:50]}")
                    
                    # Check if we're getting new products
                    if new_count == 0:
                        consecutive_no_new += 1
                        if consecutive_no_new >= 5:
                            print(f"\n[*] No new products on last 5 pages. Stopping.")
                            break
                    else:
                        consecutive_no_new = 0
                    
                    self.stats['pages_scraped'] = page_num
                    
                    # Progress update
                    if page_num % 25 == 0:
                        print(f"\n{'='*80}")
                        print(f"Progress: {page_num}/{max_pages} pages")
                        print(f"Unique products: {len(all_products)}")
                        print(f"Avg products/page: {len(all_products)/page_num:.1f}")
                        print(f"{'='*80}\n")
                    
                    # Try to click Next button
                    if page_num < max_pages:
                        if not self._click_next_button(page):
                            print(f"[*] No more pages (Next button not found)")
                            break
                        
                        # Wait for new page to load
                        time.sleep(delay)
                        
                        # Wait for products to update
                        try:
                            page.wait_for_load_state('networkidle', timeout=5000)
                        except:
                            pass
                    
                    page_num += 1
                
            except KeyboardInterrupt:
                print(f"\n[!] Interrupted at page {page_num}")
            
            finally:
                browser.close()
        
        print(f"\n{'='*80}")
        print(f"[✓] Scraping complete!")
        print(f"Pages scraped: {self.stats['pages_scraped']}")
        print(f"Products scraped: {self.stats['products_scraped']}")
        print(f"Unique products: {len(all_products)}")
        print(f"{'='*80}\n")
        
        return all_products
    
    def _click_next_button(self, page) -> bool:
        """
        Click the Next button to go to next page.
        
        Returns:
            True if clicked successfully, False if button not found
        """
        try:
            # Scroll to pagination area
            page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
            time.sleep(0.5)
            
            # Try different selectors for Next button
            next_selectors = [
                'a.pagination__next',
                'button.pagination__next',
                'a[aria-label*="next"]',
                'a[aria-label*="Next"]',
                'button[aria-label*="next"]',
                'a:has-text("Weiter")',
                'button:has-text("Weiter")',
                'a[class*="next"]',
                'button[class*="next"]',
                '.pagination a:last-child',
                '[class*="pagination"] a:last-child',
                'a[rel="next"]',
            ]
            
            for selector in next_selectors:
                try:
                    next_button = page.query_selector(selector)
                    if next_button:
                        # Check if button is visible and enabled
                        if next_button.is_visible():
                            # Check if disabled
                            is_disabled = next_button.get_attribute('disabled')
                            aria_disabled = next_button.get_attribute('aria-disabled')
                            class_name = next_button.get_attribute('class') or ''
                            
                            if is_disabled or aria_disabled == 'true' or 'disabled' in class_name:
                                continue
                            
                            # Click the button
                            next_button.click()
                            print(f"    [✓] Clicked Next button (selector: {selector})")
                            return True
                except Exception as e:
                    continue
            
            # If no button found, try clicking any pagination number that's higher
            try:
                # Get current page number from URL or pagination
                current_page = 1
                try:
                    active_page = page.query_selector('[class*="pagination"] [class*="active"]')
                    if active_page:
                        current_page = int(active_page.inner_text().strip())
                except:
                    pass
                
                # Try to click next page number
                next_page_num = current_page + 1
                next_page_link = page.query_selector(f'a:has-text("{next_page_num}")')
                if next_page_link and next_page_link.is_visible():
                    next_page_link.click()
                    print(f"    [✓] Clicked page number {next_page_num}")
                    return True
            except:
                pass
            
            return False
        
        except Exception as e:
            print(f"    [!] Error clicking Next: {e}")
            return False
    
    def _extract_products_from_page(self, page) -> List[Dict]:
        """Extract products from current page."""
        products_data = []
        
        try:
            # Find product elements
            product_selectors = [
                '[class*="product-card"]',
                '[class*="product-item"]',
                '[class*="product-tile"]',
                '.product-card',
                '.product-item',
            ]
            
            products = []
            for selector in product_selectors:
                products = page.query_selector_all(selector)
                if products and len(products) >= 10:
                    break
            
            if not products:
                return []
            
            # Extract data from each product
            for elem in products:
                try:
                    product = self._extract_product_from_element(elem)
                    if product:
                        products_data.append(product)
                        self.stats['products_scraped'] += 1
                except:
                    self.stats['skipped'] += 1
            
            return products_data
        
        except Exception as e:
            return []
    
    def _extract_product_from_element(self, element) -> Optional[Dict]:
        """Extract product data from element."""
        try:
            # Name
            name_elem = element.query_selector('h3, h4, [class*="name"], [class*="title"], .product-title')
            if not name_elem:
                return None
            
            name = name_elem.inner_text().strip()
            if not name:
                return None
            
            # Clean name
            name = re.sub(r'([a-z])([A-Z])', r'\1 \2', name)
            name = ' '.join(name.split())
            
            # Brand
            brand = None
            for kb in ['SPAR', 'S-BUDGET', 'DESPAR', 'SPAR PREMIUM']:
                if name.upper().startswith(kb):
                    brand = kb
                    break
            
            # Price
            price = None
            try:
                price_elem = element.query_selector('[class*="price"]:not([class*="old"]), .price')
                if price_elem:
                    price_text = price_elem.inner_text().strip()
                    price = self._parse_price(price_text)
            except:
                pass
            
            if not price:
                # Try finding in all text
                all_text = element.inner_text()
                match = re.search(r'€\s*(\d+[,\.]\d{2})', all_text)
                if match:
                    price = self._parse_price(match.group(1))
            
            if not price or price <= 0:
                return None
            
            # Image (with placeholder filtering)
            image_url = None
            img_elem = element.query_selector('img')
            if img_elem:
                for attr in ['data-src', 'data-lazy-src', 'data-original', 'srcset', 'src']:
                    url = img_elem.get_attribute(attr)
                    if url and not any(x in url.lower() for x in ['placeholder', 'icon', 'veggie', 'badge', 'label']):
                        if ' ' in url:
                            url = url.split(',')[-1].strip().split()[0]
                        if not url.startswith('http'):
                            url = 'https:' + url if url.startswith('//') else self.base_url + url
                        image_url = url
                        break
            
            # URL
            product_url = None
            link = element.query_selector('a')
            if link:
                product_url = link.get_attribute('href')
                if product_url and not product_url.startswith('http'):
                    product_url = self.base_url + product_url
            
            # Unit info
            unit, size = self._extract_unit_info(name)
            
            return {
                'name': name,
                'brand': brand,
                'price': price,
                'image_url': image_url,
                'product_url': product_url,
                'unit': unit,
                'size_normalized': size,
                'scraped_at': datetime.now(timezone.utc)
            }
        
        except:
            return None
    
    def _extract_unit_info(self, text: str) -> Tuple[Optional[str], Optional[float]]:
        """Extract unit and size."""
        if not text:
            return None, None
        text = text.lower().replace(',', '.')
        
        # Multi-pack
        match = re.search(r'(\d+)\s*x\s*(\d+(?:\.\d+)?)\s*(kg|g|l|ml|stk)', text)
        if match:
            qty = float(match.group(1))
            size = float(match.group(2))
            unit = match.group(3)
            return unit, qty * size
        
        # Simple
        match = re.search(r'(\d+(?:\.\d+)?)\s*(kg|g|l|ml|stk)', text)
        if match:
            return match.group(2), float(match.group(1))
        
        return None, None
    
    def _parse_price(self, text: str) -> Optional[float]:
        """Parse price."""
        if not text:
            return None
        cleaned = text.replace('€', '').replace(',', '.').strip()
        try:
            return float(cleaned)
        except:
            return None
    
    def _generate_fingerprint(self, name: str, brand: str, unit: str, size: float) -> str:
        """Generate fingerprint."""
        name_norm = re.sub(r'[^\w\s]', '', name.lower()).strip()
        brand_norm = re.sub(r'[^\w\s]', '', (brand or '').lower()).strip()
        unit_norm = (unit or '').lower()
        size_norm = f"{size:.2f}" if size else ""
        parts = [p for p in [brand_norm, name_norm, size_norm, unit_norm] if p]
        return '_'.join(parts)
    
    def save_to_database(self, products: List[Dict], db_session) -> Dict:
        """Save to database."""
        from models.postgres_models import Product, ProductStore, Store
        
        print(f"\n[*] Saving {len(products)} products to database...")
        
        store = db_session.query(Store).filter_by(store_id='spar').first()
        if not store:
            store = Store(store_id='spar', name='SPAR', website='https://www.spar.at',
                         country='AT', active=True)
            db_session.add(store)
            db_session.commit()
        
        stats = {'processed': 0, 'products_added': 0, 'products_updated': 0,
                'product_stores_added': 0, 'product_stores_updated': 0}
        
        for pd in products:
            try:
                stats['processed'] += 1
                if not pd.get('name') or not pd.get('price'):
                    continue
                
                fp = self._generate_fingerprint(pd['name'], pd.get('brand', ''),
                                               pd.get('unit', ''), pd.get('size_normalized'))
                
                product = db_session.query(Product).filter_by(fingerprint=fp).first()
                if not product:
                    product = Product(fingerprint=fp, name=pd['name'], name_de=pd['name'],
                                    brand=pd.get('brand'), unit_normalized=pd.get('unit'),
                                    size_normalized=pd.get('size_normalized'),
                                    default_image_url=pd.get('image_url'),
                                    created_at=datetime.now(timezone.utc),
                                    updated_at=datetime.now(timezone.utc))
                    db_session.add(product)
                    db_session.flush()
                    stats['products_added'] += 1
                
                ps = db_session.query(ProductStore).filter_by(
                    product_id=product.id, store_id='spar').first()
                if not ps:
                    ps = ProductStore(product_id=product.id, store_id='spar',
                                    base_price=Decimal(str(pd['price'])), is_available=True,
                                    product_url=pd.get('product_url'),
                                    last_seen=datetime.now(timezone.utc),
                                    created_at=datetime.now(timezone.utc))
                    db_session.add(ps)
                    stats['product_stores_added'] += 1
                else:
                    ps.base_price = Decimal(str(pd['price']))
                    ps.is_available = True
                    ps.last_seen = datetime.now(timezone.utc)
                    stats['product_stores_updated'] += 1
                
                if stats['processed'] % 100 == 0:
                    db_session.commit()
                    print(f"    [{stats['processed']}/{len(products)}]")
            except:
                db_session.rollback()
                continue
        
        db_session.commit()
        print(f"[✓] Database save complete!")
        return stats


def main():
    """Main execution."""
    from app import app
    from models.postgres_models import db
    
    with app.app_context():
        scraper = SparClickNextScraper(headless=False)  # Visible so you can watch
        
        print("\nTesting with 20 pages...")
        print("Watch the browser - it will CLICK the Next button!\n")
        
        products = scraper.scrape_all_products(max_pages=20, delay=2.0)
        
        if products:
            print(f"\n✓ Got {len(products)} unique products!")
            
            if len(products) > 50:
                print("\n✅ SUCCESS! Pagination works by clicking Next!")
            
            stats = scraper.save_to_database(products, db.session)
            
            print(f"\n{'='*80}")
            print("STATISTICS")
            print(f"{'='*80}")
            for k, v in stats.items():
                print(f"{k:30s}: {v}")
            print(f"{'='*80}\n")


if __name__ == "__main__":
    main()
