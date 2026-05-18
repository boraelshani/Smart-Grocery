"""
═══════════════════════════════════════════════════════════════════════════
SPAR AUSTRIA SCRAPER - SESSION-BASED VERSION
═══════════════════════════════════════════════════════════════════════════
This version establishes a proper session before scraping to avoid redirects.

Strategy:
1. Visit homepage first
2. Navigate to search page naturally
3. Interact with page (scroll, wait)
4. Then start pagination
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


class SparSessionScraper:
    """SPAR scraper with proper session establishment."""
    
    def __init__(self, headless=True):
        self.headless = headless
        self.base_url = "https://www.spar.at"
        self.store_id = "spar"
        self.playwright = None
        self.browser = None
        self.context = None
        self.page = None
        self.session_established = False
        
        self.stats = {
            "products_scraped": 0,
            "products_added": 0,
            "errors": 0,
            "skipped": 0
        }
    
    def start_browser(self):
        """Start browser with enhanced anti-detection."""
        print("[*] Starting browser...")
        self.playwright = sync_playwright().start()
        
        self.browser = self.playwright.chromium.launch(
            headless=self.headless,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--disable-dev-shm-usage',
                '--no-sandbox',
                '--disable-web-security',
            ]
        )
        
        self.context = self.browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            locale='de-AT',
            timezone_id='Europe/Vienna',
            java_script_enabled=True,
        )
        
        self.page = self.context.new_page()
        
        # Enhanced anti-detection
        self.page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
            Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});
            Object.defineProperty(navigator, 'languages', {get: () => ['de-AT', 'de', 'en']});
            window.chrome = {runtime: {}};
            
            // Override permissions
            const originalQuery = window.navigator.permissions.query;
            window.navigator.permissions.query = (parameters) => (
                parameters.name === 'notifications' ?
                    Promise.resolve({state: Notification.permission}) :
                    originalQuery(parameters)
            );
        """)
        
        print("[✓] Browser started")
    
    def stop_browser(self):
        """Stop browser."""
        if self.page:
            self.page.close()
        if self.context:
            self.context.close()
        if self.browser:
            self.browser.close()
        if self.playwright:
            self.playwright.stop()
        print("[✓] Browser stopped")
    
    def establish_session(self):
        """Establish a proper session with SPAR before scraping."""
        if self.session_established:
            return True
        
        print("[*] Establishing session with SPAR...")
        
        try:
            # Step 1: Visit homepage
            print("    [1/4] Visiting homepage...")
            self.page.goto(self.base_url, wait_until='domcontentloaded', timeout=30000)
            time.sleep(2)
            
            # Step 2: Accept cookies if present
            print("    [2/4] Handling cookies...")
            try:
                cookie_selectors = [
                    'button:has-text("Akzeptieren")',
                    'button:has-text("Accept")',
                    '[class*="cookie"] button',
                    '[id*="cookie"] button'
                ]
                for selector in cookie_selectors:
                    try:
                        button = self.page.query_selector(selector)
                        if button:
                            button.click()
                            print("        ✓ Accepted cookies")
                            time.sleep(1)
                            break
                    except:
                        continue
            except:
                pass
            
            # Step 3: Navigate to search page naturally
            print("    [3/4] Navigating to products...")
            self.page.goto(f"{self.base_url}/produktwelt/suche", 
                          wait_until='domcontentloaded', timeout=30000)
            time.sleep(2)
            
            # Step 4: Interact with page (scroll, wait)
            print("    [4/4] Interacting with page...")
            self.page.evaluate('window.scrollTo(0, 500)')
            time.sleep(0.5)
            self.page.evaluate('window.scrollTo(0, 1000)')
            time.sleep(0.5)
            self.page.evaluate('window.scrollTo(0, 0)')
            time.sleep(1)
            
            # Wait for products to load
            try:
                self.page.wait_for_selector('[class*="product"]', timeout=10000)
                print("[✓] Session established successfully")
                self.session_established = True
                return True
            except:
                print("[!] Could not find products after session setup")
                return False
        
        except Exception as e:
            print(f"[!] Error establishing session: {e}")
            return False
    
    def scrape_all_products(self, max_pages: int = None, delay: float = 2.0) -> List[Dict]:
        """Scrape all products with proper session."""
        print(f"\n{'='*80}")
        print("SPAR SESSION SCRAPER - Starting")
        print(f"{'='*80}\n")
        
        self.start_browser()
        
        # Establish session first
        if not self.establish_session():
            print("[!] Failed to establish session. Stopping.")
            self.stop_browser()
            return []
        
        all_products = []
        seen_fingerprints = set()
        
        if max_pages is None:
            max_pages = 1178
        
        page_num = 1
        consecutive_no_new = 0
        
        try:
            while page_num <= max_pages:
                print(f"\n[*] Page {page_num}/{max_pages}")
                
                # For page 1, we're already there
                if page_num == 1:
                    print("    Already on page 1")
                else:
                    # Navigate to specific page
                    # Try different URL formats
                    urls_to_try = [
                        f"{self.base_url}/produktwelt/suche?page={page_num}",
                        f"{self.base_url}/produktwelt/suche?search=&page={page_num}",
                        f"{self.base_url}/produktwelt/suche?page={page_num}&search=",
                    ]
                    
                    success = False
                    for url in urls_to_try:
                        try:
                            self.page.goto(url, wait_until='domcontentloaded', timeout=20000)
                            time.sleep(1)
                            
                            # Check if we're actually on the right page
                            current_url = self.page.url
                            if f"page={page_num}" in current_url:
                                print(f"    ✓ Navigated to page {page_num}")
                                success = True
                                break
                            else:
                                print(f"    ✗ Redirected from page {page_num}")
                        except:
                            continue
                    
                    if not success:
                        print(f"    [!] Could not navigate to page {page_num}")
                        # Try clicking pagination instead
                        if not self._try_click_to_page(page_num):
                            break
                
                # Wait and scroll
                time.sleep(1)
                self.page.evaluate('window.scrollTo(0, document.body.scrollHeight / 2)')
                time.sleep(0.5)
                self.page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
                time.sleep(1)
                
                # Extract products
                products = self._extract_products_from_current_page()
                
                if not products:
                    print(f"    [!] No products found")
                    consecutive_no_new += 1
                    if consecutive_no_new >= 5:
                        break
                    page_num += 1
                    continue
                
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
                
                if new_count == 0:
                    consecutive_no_new += 1
                    if consecutive_no_new >= 10:
                        print(f"\n[*] No new products on last 10 pages. Stopping.")
                        break
                else:
                    consecutive_no_new = 0
                
                page_num += 1
                
                if page_num % 25 == 0:
                    print(f"\n{'='*80}")
                    print(f"Progress: {page_num}/{max_pages} | Products: {len(all_products)}")
                    print(f"{'='*80}\n")
                
                time.sleep(delay)
        
        except KeyboardInterrupt:
            print(f"\n[!] Interrupted at page {page_num}")
        
        finally:
            self.stop_browser()
        
        print(f"\n{'='*80}")
        print(f"[✓] Complete! Pages: {page_num} | Products: {len(all_products)}")
        print(f"{'='*80}\n")
        
        return all_products
    
    def _try_click_to_page(self, target_page: int) -> bool:
        """Try to click to a specific page number."""
        try:
            self.page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
            time.sleep(0.5)
            
            # Look for page number button
            page_button = self.page.query_selector(f'a:has-text("{target_page}")')
            if page_button:
                page_button.click()
                time.sleep(2)
                return True
            
            return False
        except:
            return False
    
    def _extract_products_from_current_page(self) -> List[Dict]:
        """Extract products from current page."""
        products_data = []
        
        try:
            selectors = ['[class*="product-card"]', '[class*="product-item"]']
            products = []
            
            for selector in selectors:
                products = self.page.query_selector_all(selector)
                if products and len(products) >= 10:
                    break
            
            if not products:
                return []
            
            for elem in products:
                try:
                    product = self._extract_product_from_element(elem)
                    if product:
                        products_data.append(product)
                        self.stats['products_scraped'] += 1
                except:
                    self.stats['skipped'] += 1
            
            return products_data
        except:
            return []
    
    def _extract_product_from_element(self, element) -> Optional[Dict]:
        """Extract product data."""
        try:
            # Name
            name_elem = element.query_selector('h3, h4, [class*="name"]')
            if not name_elem:
                return None
            name = name_elem.inner_text().strip()
            if not name:
                return None
            
            name = re.sub(r'([a-z])([A-Z])', r'\1 \2', name)
            name = ' '.join(name.split())
            
            # Brand
            brand = None
            for kb in ['SPAR', 'S-BUDGET', 'DESPAR']:
                if name.upper().startswith(kb):
                    brand = kb
                    break
            
            # Price
            price = None
            try:
                price_elem = element.query_selector('[class*="price"]:not([class*="old"])')
                if price_elem:
                    price = self._parse_price(price_elem.inner_text())
            except:
                pass
            
            if not price:
                all_text = element.inner_text()
                match = re.search(r'€\s*(\d+[,\.]\d{2})', all_text)
                if match:
                    price = self._parse_price(match.group(1))
            
            if not price or price <= 0:
                return None
            
            # Image
            image_url = None
            img_elem = element.query_selector('img')
            if img_elem:
                for attr in ['data-src', 'data-lazy-src', 'srcset', 'src']:
                    url = img_elem.get_attribute(attr)
                    if url and not any(x in url.lower() for x in ['placeholder', 'icon', 'veggie', 'badge']):
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
        
        print(f"\n[*] Saving {len(products)} products...")
        
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
            except Exception as e:
                db_session.rollback()
                continue
        
        db_session.commit()
        print(f"[✓] Saved!")
        return stats


def main():
    """Main execution."""
    from app import app
    from models.postgres_models import db
    
    with app.app_context():
        scraper = SparSessionScraper(headless=False)
        products = scraper.scrape_all_products(max_pages=20, delay=2.0)
        
        if products:
            stats = scraper.save_to_database(products, db.session)
            print(f"\n{'='*80}")
            for k, v in stats.items():
                print(f"{k:25s}: {v}")
            print(f"{'='*80}\n")


if __name__ == "__main__":
    main()
