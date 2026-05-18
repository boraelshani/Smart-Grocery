"""
═══════════════════════════════════════════════════════════════════════════
SPAR AUSTRIA API SCRAPER - NETWORK INTERCEPTION VERSION
═══════════════════════════════════════════════════════════════════════════
This scraper intercepts network requests to find SPAR's internal API
and scrapes data directly from the API instead of the HTML.

This bypasses bot detection by using the same API the website uses.
═══════════════════════════════════════════════════════════════════════════
"""

import re
import time
import json
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Optional, Tuple
from decimal import Decimal

try:
    from selenium import webdriver
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.chrome.service import Service
    from selenium.common.exceptions import TimeoutException
except ImportError:
    print("[!] Selenium not installed. Install with:")
    print("    pip install selenium")
    exit(1)


class SparApiScraper:
    """
    SPAR scraper that intercepts network requests to find and use the internal API.
    """
    
    def __init__(self, headless=False):
        """Initialize the API scraper."""
        self.headless = headless
        self.base_url = "https://www.spar.at"
        self.store_id = "spar"
        self.driver = None
        self.api_endpoint = None
        self.api_headers = {}
        
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
        """Start Chrome with network logging enabled."""
        print("[*] Starting Chrome with network logging...")
        
        chrome_options = Options()
        
        if self.headless:
            chrome_options.add_argument('--headless=new')
        
        # Enable performance logging to capture network requests
        chrome_options.set_capability('goog:loggingPrefs', {'performance': 'ALL'})
        
        # Anti-detection settings
        chrome_options.add_argument('--disable-blink-features=AutomationControlled')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--lang=de-AT')
        chrome_options.add_argument('--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
        
        # Exclude automation flags
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        
        self.driver = webdriver.Chrome(options=chrome_options)
        self.driver.set_page_load_timeout(30)
        
        # Override navigator.webdriver
        self.driver.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {
            'source': '''
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                });
                Object.defineProperty(navigator, 'plugins', {
                    get: () => [1, 2, 3, 4, 5]
                });
                Object.defineProperty(navigator, 'languages', {
                    get: () => ['de-AT', 'de', 'en-US', 'en']
                });
                window.chrome = {
                    runtime: {}
                };
            '''
        })
        
        print("[✓] Browser started with network logging")
    
    def stop_browser(self):
        """Stop browser."""
        if self.driver:
            self.driver.quit()
        print("[✓] Browser stopped")
    
    def find_api_endpoint(self):
        """
        Navigate to SPAR and intercept network requests to find the API endpoint.
        """
        print("[*] Finding SPAR's internal API endpoint...")
        
        try:
            # Navigate to search page
            self.driver.get(f"{self.base_url}/produktwelt/suche?search=&page=1")
            
            # Wait for page to load
            time.sleep(5)
            
            # Get performance logs (network requests)
            logs = self.driver.get_log('performance')
            
            # Look for API calls
            api_candidates = []
            
            for log in logs:
                try:
                    message = json.loads(log['message'])
                    method = message.get('message', {}).get('method', '')
                    
                    # Look for network responses
                    if method == 'Network.responseReceived':
                        response = message['message']['params']['response']
                        url = response.get('url', '')
                        
                        # Look for API patterns
                        if any(pattern in url.lower() for pattern in [
                            '/api/', '/graphql', '/search', '/products', 
                            '/query', '/data', '.json', '/v1/', '/v2/'
                        ]):
                            api_candidates.append({
                                'url': url,
                                'status': response.get('status'),
                                'mimeType': response.get('mimeType', '')
                            })
                            print(f"    Found API candidate: {url[:100]}")
                
                except Exception as e:
                    continue
            
            # Filter for JSON responses
            json_apis = [
                api for api in api_candidates 
                if 'json' in api.get('mimeType', '').lower() or 
                   api.get('url', '').endswith('.json')
            ]
            
            if json_apis:
                print(f"\n[✓] Found {len(json_apis)} potential API endpoints!")
                for i, api in enumerate(json_apis[:5], 1):
                    print(f"    {i}. {api['url'][:100]}")
                
                self.api_endpoint = json_apis[0]['url']
                return True
            else:
                print("[!] No API endpoint found in network logs")
                print(f"[*] Total network requests captured: {len(logs)}")
                return False
        
        except Exception as e:
            print(f"[!] Error finding API: {e}")
            return False
    
    def scrape_with_selenium(self, max_pages: int = None, delay: float = 2.0) -> List[Dict]:
        """
        Fallback: Scrape using Selenium with enhanced stealth mode.
        """
        print(f"\n{'='*80}")
        print("SPAR API SCRAPER - Using Selenium Fallback")
        print(f"{'='*80}\n")
        
        self.start_browser()
        
        # Try to find API first
        api_found = self.find_api_endpoint()
        
        if api_found:
            print(f"\n[✓] API endpoint found: {self.api_endpoint}")
            print("[*] You can now use this endpoint to scrape directly!")
            print("[*] Continuing with Selenium scraping...")
        
        all_products = []
        seen_fingerprints = set()
        
        if max_pages is None:
            max_pages = 1178
        
        page = 1
        consecutive_empty = 0
        pages_with_no_new = 0
        
        try:
            while page <= max_pages:
                print(f"\n[*] Scraping page {page}/{max_pages}")
                
                # Navigate to page
                url = f"{self.base_url}/produktwelt/suche?search=&page={page}"
                self.driver.get(url)
                
                # Wait for products
                try:
                    WebDriverWait(self.driver, 15).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, '[class*="product"]'))
                    )
                except TimeoutException:
                    print(f"[!] Timeout on page {page}")
                    consecutive_empty += 1
                    if consecutive_empty >= 5:
                        break
                    page += 1
                    continue
                
                # Scroll to load all content
                self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight / 2);")
                time.sleep(1)
                self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(2)
                
                # Extract products
                products = self._extract_products_from_page()
                
                if not products:
                    consecutive_empty += 1
                    print(f"[!] No products found (consecutive: {consecutive_empty})")
                    if consecutive_empty >= 5:
                        break
                else:
                    consecutive_empty = 0
                    
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
                    
                    print(f"[✓] New unique products: {new_count} (Total: {len(all_products)})")
                    
                    if new_count == 0:
                        pages_with_no_new += 1
                        if pages_with_no_new >= 20:
                            print(f"[*] No new products on last 20 pages. Stopping.")
                            break
                    else:
                        pages_with_no_new = 0
                
                # Progress update
                if page % 10 == 0:
                    print(f"\n{'='*80}")
                    print(f"Progress: {page}/{max_pages} pages | {len(all_products)} unique products")
                    print(f"{'='*80}\n")
                
                page += 1
                time.sleep(delay)
        
        finally:
            self.stop_browser()
        
        print(f"\n{'='*80}")
        print(f"[✓] Scraping complete!")
        print(f"Pages scraped: {page - 1}")
        print(f"Unique products: {len(all_products)}")
        print(f"{'='*80}\n")
        
        return all_products
    
    def _extract_products_from_page(self) -> List[Dict]:
        """Extract products from current page."""
        products_data = []
        
        try:
            # Find product elements
            product_elements = self.driver.find_elements(By.CSS_SELECTOR, '[class*="product-card"], [class*="product-item"]')
            
            if not product_elements:
                return []
            
            print(f"    Found {len(product_elements)} product elements")
            
            for elem in product_elements:
                try:
                    product = self._extract_product_from_element(elem)
                    if product:
                        products_data.append(product)
                        self.stats['products_scraped'] += 1
                except Exception as e:
                    self.stats['skipped'] += 1
                    continue
            
            if products_data:
                print(f"    Extracted {len(products_data)} valid products")
                print(f"    First: {products_data[0]['name'][:50]}")
                if len(products_data) > 1:
                    print(f"    Last: {products_data[-1]['name'][:50]}")
            
            return products_data
        
        except Exception as e:
            print(f"[!] Error extracting products: {e}")
            return []
    
    def _extract_product_from_element(self, element) -> Optional[Dict]:
        """Extract product data from a Selenium element."""
        try:
            # Extract name
            try:
                name_elem = element.find_element(By.CSS_SELECTOR, 'h3, h4, [class*="name"], [class*="title"]')
                name = name_elem.text.strip()
            except:
                return None
            
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
                price_elem = element.find_element(By.CSS_SELECTOR, '[class*="price"]:not([class*="old"])')
                price_text = price_elem.text.strip()
                price = self._parse_price(price_text)
            except:
                # Try finding price in all text
                all_text = element.text
                price_match = re.search(r'€\s*(\d+[,\.]\d{2})|(\d+[,\.]\d{2})\s*€', all_text)
                if price_match:
                    price_str = price_match.group(1) or price_match.group(2)
                    price = self._parse_price(price_str)
            
            if not price or price <= 0:
                return None
            
            # Extract image
            image_url = None
            try:
                img_elem = element.find_element(By.TAG_NAME, 'img')
                image_url = img_elem.get_attribute('src') or img_elem.get_attribute('data-src')
                if image_url and not image_url.startswith('http'):
                    if image_url.startswith('//'):
                        image_url = 'https:' + image_url
                    elif image_url.startswith('/'):
                        image_url = self.base_url + image_url
            except:
                pass
            
            # Extract URL
            product_url = None
            try:
                link_elem = element.find_element(By.TAG_NAME, 'a')
                product_url = link_elem.get_attribute('href')
            except:
                pass
            
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
        
        # Multi-pack pattern
        multi_match = re.search(r'(\d+)\s*x\s*(\d+(?:\.\d+)?)\s*(kg|g|l|ml|stk|stück)', text)
        if multi_match:
            qty = float(multi_match.group(1))
            size = float(multi_match.group(2))
            unit = multi_match.group(3)
            unit = 'stk' if unit == 'stück' else unit
            return unit, qty * size
        
        # Simple pattern
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
        """Generate unique fingerprint for deduplication."""
        name_norm = re.sub(r'[^\w\s]', '', name.lower()).strip()
        brand_norm = re.sub(r'[^\w\s]', '', (brand or '').lower()).strip()
        unit_norm = (unit or '').lower()
        size_norm = f"{size:.2f}" if size else ""
        
        parts = [p for p in [brand_norm, name_norm, size_norm, unit_norm] if p]
        return '_'.join(parts)
    
    def save_to_database(self, products: List[Dict], db_session) -> Dict:
        """Save products to database."""
        from models.postgres_models import Product, ProductStore, Store
        
        print(f"\n{'='*80}")
        print("DATABASE INSERTION - Starting")
        print(f"{'='*80}\n")
        
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
                
                # Validate
                if not product_data.get('name') or not product_data.get('price'):
                    stats['validation_errors'] += 1
                    continue
                
                # Generate fingerprint
                fingerprint = self._generate_fingerprint(
                    product_data['name'],
                    product_data.get('brand', ''),
                    product_data.get('unit', ''),
                    product_data.get('size_normalized')
                )
                
                # Check if product exists
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
                    
                    if stats['products_added'] % 50 == 0:
                        print(f"[+] Added {stats['products_added']} new products...")
                else:
                    if product_data.get('image_url') and not product.default_image_url:
                        product.default_image_url = product_data['image_url']
                        product.updated_at = datetime.now(timezone.utc)
                        stats['products_updated'] += 1
                
                # Product store entry
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
                
                # Commit every 100 products
                if stats['processed'] % 100 == 0:
                    db_session.commit()
                    print(f"[*] Progress: {stats['processed']}/{len(products)}")
            
            except Exception as e:
                print(f"[!] Database error: {e}")
                stats['database_errors'] += 1
                db_session.rollback()
                continue
        
        try:
            db_session.commit()
            print(f"\n[✓] Database insertion complete!")
        except Exception as e:
            print(f"[!] Final commit error: {e}")
            db_session.rollback()
        
        return stats


def main():
    """Main execution."""
    from app import app
    from models.postgres_models import db
    
    with app.app_context():
        scraper = SparApiScraper(headless=False)
        
        # Scrape products
        products = scraper.scrape_with_selenium(max_pages=None, delay=1.5)
        
        if products:
            print(f"\n[*] Scraped {len(products)} unique products. Saving to database...")
            db_stats = scraper.save_to_database(products, db.session)
            
            print(f"\n{'='*80}")
            print("FINAL STATISTICS")
            print(f"{'='*80}")
            for key, value in db_stats.items():
                print(f"{key:25s}: {value}")
            print(f"{'='*80}\n")
        else:
            print("[!] No products scraped.")


if __name__ == "__main__":
    main()
