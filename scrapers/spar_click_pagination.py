"""
═══════════════════════════════════════════════════════════════════════════
SPAR AUSTRIA SCRAPER - CLICK PAGINATION VERSION
═══════════════════════════════════════════════════════════════════════════
This version clicks the "Next" button instead of changing URLs.
This should bypass the bot protection that serves cached results.
═══════════════════════════════════════════════════════════════════════════
"""

import re
import time
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Optional, Tuple
from decimal import Decimal

try:
    from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
except ImportError:
    print("[!] Playwright not installed. Install with:")
    print("    pip install playwright")
    print("    playwright install chromium")
    exit(1)


class SparClickPaginationScraper:
    """
    SPAR scraper that clicks pagination buttons instead of URL navigation.
    """
    
    def __init__(self, headless=True):
        """Initialize the scraper."""
        self.headless = headless
        self.base_url = "https://www.spar.at"
        self.store_id = "spar"
        self.playwright = None
        self.browser = None
        self.context = None
        self.page = None
        
        # Statistics
        self.stats = {
            "products_scraped": 0,
            "products_added": 0,
            "products_updated": 0,
            "promotions_added": 0,
            "errors": 0,
            "skipped": 0
        }
    
    def start_browser(self):
        """Start Playwright browser with enhanced settings."""
        print("[*] Starting browser...")
        self.playwright = sync_playwright().start()
        
        # Launch browser with realistic settings
        self.browser = self.playwright.chromium.launch(
            headless=self.headless,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--disable-dev-shm-usage',
                '--no-sandbox',
            ]
        )
        
        # Create context with realistic settings
        self.context = self.browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            locale='de-AT',
            timezone_id='Europe/Vienna',
        )
        
        # Create page
        self.page = self.context.new_page()
        
        # Anti-detection
        self.page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
            Object.defineProperty(navigator, 'plugins', {
                get: () => [1, 2, 3, 4, 5]
            });
            Object.defineProperty(navigator, 'languages', {
                get: () => ['de-AT', 'de', 'en-US', 'en']
            });
            window.chrome = { runtime: {} };
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
    
    def scrape_all_products_with_clicks(self, max_pages: int = None, delay: float = 2.0) -> List[Dict]:
        """
        Scrape products by clicking pagination buttons.
        
        Args:
            max_pages: Maximum pages to scrape
            delay: Delay between pages
            
        Returns:
            List of all products
        """
        print(f"\n{'='*80}")
        print("SPAR CLICK PAGINATION SCRAPER - Starting")
        print(f"Strategy: Click 'Next' button instead of URL navigation")
        print(f"{'='*80}\n")
        
        self.start_browser()
        
        all_products = []
        seen_fingerprints = set()
        
        if max_pages is None:
            max_pages = 1178
        
        page_num = 1
        consecutive_no_new = 0
        
        try:
            # Navigate to first page
            print("[*] Loading first page...")
            self.page.goto(f"{self.base_url}/produktwelt/suche?search=", 
                          wait_until='domcontentloaded', timeout=30000)
            
            # Wait for products
            try:
                self.page.wait_for_selector('[class*="product"]', timeout=15000)
            except PlaywrightTimeout:
                print("[!] Timeout waiting for products")
                return []
            
            time.sleep(2)
            
            while page_num <= max_pages:
                print(f"\n[*] Scraping page {page_num}/{max_pages}")
                
                # Scroll to load images
                self.page.evaluate('window.scrollTo(0, document.body.scrollHeight / 2)')
                time.sleep(0.5)
                self.page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
                time.sleep(1)
                
                # Extract products from current page
                products = self._extract_products_from_current_page()
                
                if not products:
                    print(f"[!] No products found on page {page_num}")
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
                
                # Show first product to verify it's different
                if products:
                    print(f"    First product: {products[0]['name'][:50]}")
                
                # Check if we're getting new products
                if new_count == 0:
                    consecutive_no_new += 1
                    if consecutive_no_new >= 10:
                        print(f"\n[*] No new products on last 10 pages. Stopping.")
                        break
                else:
                    consecutive_no_new = 0
                
                # Try to click next button
                if page_num < max_pages:
                    if not self._click_next_page():
                        print(f"[*] Could not find 'Next' button. Reached end.")
                        break
                    
                    # Wait for new page to load
                    time.sleep(delay)
                    
                    # Wait for products to update
                    try:
                        self.page.wait_for_load_state('networkidle', timeout=5000)
                    except:
                        pass
                
                page_num += 1
                
                # Progress update
                if page_num % 25 == 0:
                    print(f"\n{'='*80}")
                    print(f"Progress: {page_num}/{max_pages} pages")
                    print(f"Unique products: {len(all_products)}")
                    print(f"{'='*80}\n")
        
        except KeyboardInterrupt:
            print(f"\n[!] Interrupted at page {page_num}")
        
        finally:
            self.stop_browser()
        
        print(f"\n{'='*80}")
        print(f"[✓] Scraping complete!")
        print(f"Pages scraped: {page_num}")
        print(f"Unique products: {len(all_products)}")
        print(f"{'='*80}\n")
        
        return all_products
    
    def _click_next_page(self) -> bool:
        """
        Click the next page button.
        
        Returns:
            True if clicked successfully, False otherwise
        """
        try:
            # Try different selectors for next button
            next_selectors = [
                'a[aria-label*="next"]',
                'a[aria-label*="Next"]',
                'button[aria-label*="next"]',
                'a:has-text("Weiter")',
                'button:has-text("Weiter")',
                'a[class*="next"]',
                'button[class*="next"]',
                '.pagination a:last-child',
                '[class*="pagination"] a:last-child'
            ]
            
            for selector in next_selectors:
                try:
                    next_button = self.page.query_selector(selector)
                    if next_button:
                        # Check if button is enabled
                        is_disabled = next_button.get_attribute('disabled')
                        aria_disabled = next_button.get_attribute('aria-disabled')
                        
                        if is_disabled or aria_disabled == 'true':
                            continue
                        
                        # Click the button
                        next_button.click()
                        print(f"    [✓] Clicked next button: {selector}")
                        return True
                except:
                    continue
            
            # If no button found, try scrolling to pagination and clicking
            try:
                self.page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
                time.sleep(0.5)
                
                # Try clicking any pagination link that's not the current page
                pagination_links = self.page.query_selector_all('[class*="pagination"] a')
                for link in pagination_links:
                    text = link.inner_text().strip()
                    if text and text.isdigit():
                        # Click the next number
                        link.click()
                        print(f"    [✓] Clicked pagination number: {text}")
                        return True
            except:
                pass
            
            return False
        
        except Exception as e:
            print(f"    [!] Error clicking next: {e}")
            return False
    
    def _extract_products_from_current_page(self) -> List[Dict]:
        """Extract products from the current page."""
        products_data = []
        
        try:
            # Find product elements
            product_selectors = [
                '[class*="product-card"]',
                '[class*="product-item"]',
                '[class*="product-tile"]',
            ]
            
            products = []
            for selector in product_selectors:
                products = self.page.query_selector_all(selector)
                if products and len(products) >= 10:
                    break
            
            if not products:
                return []
            
            # Extract data
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
            print(f"[!] Error extracting products: {e}")
            return []
    
    def _extract_product_from_element(self, element) -> Optional[Dict]:
        """Extract product data from element."""
        try:
            # Extract name
            name_elem = (
                element.query_selector('h3, h4') or
                element.query_selector('[class*="name"]') or
                element.query_selector('[class*="title"]')
            )
            if not name_elem:
                return None
            
            name = name_elem.inner_text().strip()
            if not name:
                return None
            
            # Clean name
            name = re.sub(r'([a-z])([A-Z])', r'\1 \2', name)
            name = re.sub(r'([A-Z]+)([A-Z][a-z])', r'\1 \2', name)
            name = ' '.join(name.split())
            
            # Extract brand
            brand = None
            known_brands = ['SPAR', 'S-BUDGET', 'DESPAR', 'SPAR PREMIUM', 'SPAR NATUR PUR']
            for kb in known_brands:
                if name.upper().startswith(kb.upper()):
                    brand = kb
                    break
            
            # Extract price
            price = None
            try:
                price_elem = element.query_selector('[class*="price"]:not([class*="old"])')
                if price_elem:
                    price_text = price_elem.inner_text().strip()
                    price = self._parse_price(price_text)
            except:
                pass
            
            if not price or price <= 0:
                # Try finding in all text
                all_text = element.inner_text()
                price_match = re.search(r'€\s*(\d+[,\.]\d{2})|(\d+[,\.]\d{2})\s*€', all_text)
                if price_match:
                    price_str = price_match.group(1) or price_match.group(2)
                    price = self._parse_price(price_str)
            
            if not price or price <= 0:
                return None
            
            # Extract image (with placeholder filtering)
            img_elem = element.query_selector('img')
            image_url = None
            if img_elem:
                potential_urls = [
                    img_elem.get_attribute('data-src'),
                    img_elem.get_attribute('data-lazy-src'),
                    img_elem.get_attribute('data-original'),
                    img_elem.get_attribute('srcset'),
                    img_elem.get_attribute('src')
                ]
                
                for url in potential_urls:
                    if url:
                        if ' ' in url:
                            parts = url.split(',')
                            url = parts[-1].strip().split()[0]
                        
                        if any(skip in url.lower() for skip in [
                            'placeholder', 'icon', 'logo', 'veggie', 'vegan',
                            'bio-icon', 'label', 'badge', 'data:image'
                        ]):
                            continue
                        
                        if not url.startswith('http'):
                            if url.startswith('//'):
                                url = 'https:' + url
                            elif url.startswith('/'):
                                url = self.base_url + url
                        
                        if url.startswith('http'):
                            image_url = url
                            break
            
            # Extract URL
            link_elem = element.query_selector('a')
            product_url = None
            if link_elem:
                product_url = link_elem.get_attribute('href')
                if product_url and not product_url.startswith('http'):
                    if product_url.startswith('/'):
                        product_url = self.base_url + product_url
            
            # Extract unit info
            unit, size_normalized = self._extract_unit_info(name)
            
            return {
                'name': name,
                'brand': brand,
                'price': price,
                'image_url': image_url,
                'product_url': product_url,
                'unit': unit,
                'size_normalized': size_normalized,
                'scraped_at': datetime.now(timezone.utc)
            }
        
        except Exception as e:
            return None
    
    def _extract_unit_info(self, text: str) -> Tuple[Optional[str], Optional[float]]:
        """Extract unit and size from text."""
        if not text:
            return None, None
        
        text = text.lower().replace(',', '.')
        
        multi_match = re.search(r'(\d+)\s*x\s*(\d+(?:\.\d+)?)\s*(kg|g|l|ml|stk|stück)', text)
        if multi_match:
            qty = float(multi_match.group(1))
            size = float(multi_match.group(2))
            unit = multi_match.group(3)
            unit = 'stk' if unit == 'stück' else unit
            return unit, qty * size
        
        simple_match = re.search(r'(\d+(?:\.\d+)?)\s*(kg|g|l|ml|stk|stück)', text)
        if simple_match:
            size = float(simple_match.group(1))
            unit = simple_match.group(2)
            unit = 'stk' if unit == 'stück' else unit
            return unit, size
        
        return None, None
    
    def _parse_price(self, price_text: str) -> Optional[float]:
        """Parse price string to float."""
        if not price_text:
            return None
        
        cleaned = price_text.replace('€', '').replace('EUR', '').strip()
        cleaned = cleaned.replace(',', '.')
        
        try:
            return float(cleaned)
        except (ValueError, TypeError):
            return None
    
    def _generate_fingerprint(self, name: str, brand: str, unit: str, size: float) -> str:
        """Generate unique fingerprint."""
        name_norm = re.sub(r'[^\w\s]', '', name.lower()).strip()
        brand_norm = re.sub(r'[^\w\s]', '', (brand or '').lower()).strip()
        unit_norm = (unit or '').lower()
        size_norm = f"{size:.2f}" if size else ""
        
        parts = [p for p in [brand_norm, name_norm, size_norm, unit_norm] if p]
        return '_'.join(parts)
    
    def save_to_database(self, products: List[Dict], db_session) -> Dict:
        """Save products to database."""
        from models.postgres_models import Product, ProductStore, Store
        
        print(f"\n[*] Saving {len(products)} products to database...")
        
        # Ensure SPAR store exists
        store = db_session.query(Store).filter_by(store_id='spar').first()
        if not store:
            store = Store(
                store_id='spar',
                name='SPAR',
                website='https://www.spar.at',
                logo_url='https://www.spar.at/favicon.ico',
                country='AT',
                active=True
            )
            db_session.add(store)
            db_session.commit()
        
        stats = {
            'processed': 0,
            'products_added': 0,
            'products_updated': 0,
            'product_stores_added': 0,
            'product_stores_updated': 0,
            'validation_errors': 0,
            'database_errors': 0
        }
        
        for product_data in products:
            try:
                stats['processed'] += 1
                
                if not product_data.get('name') or not product_data.get('price'):
                    stats['validation_errors'] += 1
                    continue
                
                fingerprint = self._generate_fingerprint(
                    product_data['name'],
                    product_data.get('brand', ''),
                    product_data.get('unit', ''),
                    product_data.get('size_normalized')
                )
                
                product = db_session.query(Product).filter_by(fingerprint=fingerprint).first()
                
                if not product:
                    product = Product(
                        fingerprint=fingerprint,
                        name=product_data['name'],
                        name_de=product_data['name'],
                        brand=product_data.get('brand'),
                        unit_normalized=product_data.get('unit'),
                        size_normalized=product_data.get('size_normalized'),
                        default_image_url=product_data.get('image_url'),
                        created_at=datetime.now(timezone.utc),
                        updated_at=datetime.now(timezone.utc)
                    )
                    db_session.add(product)
                    db_session.flush()
                    stats['products_added'] += 1
                else:
                    if product_data.get('image_url') and not product.default_image_url:
                        product.default_image_url = product_data['image_url']
                        product.updated_at = datetime.now(timezone.utc)
                        stats['products_updated'] += 1
                
                product_store = db_session.query(ProductStore).filter_by(
                    product_id=product.id,
                    store_id='spar'
                ).first()
                
                if not product_store:
                    product_store = ProductStore(
                        product_id=product.id,
                        store_id='spar',
                        base_price=Decimal(str(product_data['price'])),
                        is_available=True,
                        product_url=product_data.get('product_url'),
                        last_seen=datetime.now(timezone.utc),
                        created_at=datetime.now(timezone.utc)
                    )
                    db_session.add(product_store)
                    stats['product_stores_added'] += 1
                else:
                    product_store.base_price = Decimal(str(product_data['price']))
                    product_store.is_available = True
                    product_store.last_seen = datetime.now(timezone.utc)
                    stats['product_stores_updated'] += 1
                
                if stats['processed'] % 100 == 0:
                    db_session.commit()
                    print(f"[*] Saved {stats['processed']}/{len(products)}")
            
            except Exception as e:
                print(f"[!] Error: {e}")
                stats['database_errors'] += 1
                db_session.rollback()
                continue
        
        try:
            db_session.commit()
            print(f"[✓] Database save complete!")
        except Exception as e:
            print(f"[!] Final commit error: {e}")
            db_session.rollback()
        
        return stats


def main():
    """Main execution."""
    from app import app
    from models.postgres_models import db
    
    with app.app_context():
        scraper = SparClickPaginationScraper(headless=False)
        
        # Scrape products
        products = scraper.scrape_all_products_with_clicks(max_pages=50, delay=2.0)
        
        if products:
            db_stats = scraper.save_to_database(products, db.session)
            
            print(f"\n{'='*80}")
            print("STATISTICS")
            print(f"{'='*80}")
            for key, value in db_stats.items():
                print(f"{key:25s}: {value}")
            print(f"{'='*80}\n")
        else:
            print("[!] No products scraped.")


if __name__ == "__main__":
    main()
