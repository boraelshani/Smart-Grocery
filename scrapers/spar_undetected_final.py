"""
═══════════════════════════════════════════════════════════════════════════
SPAR AUSTRIA SCRAPER - UNDETECTED CHROMEDRIVER VERSION
═══════════════════════════════════════════════════════════════════════════
This uses undetected-chromedriver which is specifically designed to bypass
bot detection. This is the BEST chance of working with SPAR.
═══════════════════════════════════════════════════════════════════════════
"""

import re
import time
from datetime import datetime, timezone
from typing import List, Dict, Optional, Tuple
from decimal import Decimal

try:
    import undetected_chromedriver as uc
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.common.exceptions import TimeoutException
except ImportError:
    print("[!] Required packages not installed. Run:")
    print("    pip install undetected-chromedriver selenium")
    exit(1)


class SparUndetectedFinalScraper:
    """SPAR scraper using undetected-chromedriver to bypass bot detection."""
    
    def __init__(self, headless=False):
        self.headless = headless
        self.base_url = "https://www.spar.at"
        self.store_id = "spar"
        self.driver = None
        
        self.stats = {
            "products_scraped": 0,
            "products_added": 0,
            "errors": 0,
            "skipped": 0
        }
    
    def start_browser(self):
        """Start undetected Chrome browser."""
        print("[*] Starting undetected Chrome browser...")
        print("    This may take a moment on first run...")
        
        options = uc.ChromeOptions()
        
        if self.headless:
            options.add_argument('--headless=new')
        
        # Minimal options to avoid detection
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--lang=de-AT')
        options.add_argument('--window-size=1920,1080')
        
        # Use undetected chromedriver
        try:
            self.driver = uc.Chrome(options=options, version_main=None, use_subprocess=True)
            self.driver.set_page_load_timeout(30)
            print("[✓] Browser started")
            return True
        except Exception as e:
            print(f"[!] Error starting browser: {e}")
            return False
    
    def stop_browser(self):
        """Stop browser."""
        if self.driver:
            try:
                self.driver.quit()
            except:
                pass
        print("[✓] Browser stopped")
    
    def establish_session(self):
        """Establish session with SPAR."""
        print("[*] Establishing session...")
        
        try:
            # Visit homepage
            print("    [1/3] Visiting homepage...")
            self.driver.get(self.base_url)
            time.sleep(3)
            
            # Accept cookies
            print("    [2/3] Handling cookies...")
            try:
                cookie_buttons = self.driver.find_elements(By.XPATH, 
                    "//button[contains(text(), 'Akzeptieren') or contains(text(), 'Accept')]")
                if cookie_buttons:
                    cookie_buttons[0].click()
                    print("        ✓ Accepted cookies")
                    time.sleep(1)
            except:
                pass
            
            # Navigate to products
            print("    [3/3] Navigating to products...")
            self.driver.get(f"{self.base_url}/produktwelt/suche")
            time.sleep(3)
            
            # Scroll to show we're human
            self.driver.execute_script("window.scrollTo(0, 500);")
            time.sleep(0.5)
            self.driver.execute_script("window.scrollTo(0, 1000);")
            time.sleep(0.5)
            self.driver.execute_script("window.scrollTo(0, 0);")
            time.sleep(1)
            
            # Check if products loaded
            try:
                WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, '[class*="product"]'))
                )
                print("[✓] Session established")
                return True
            except:
                print("[!] Could not find products")
                return False
        
        except Exception as e:
            print(f"[!] Error: {e}")
            return False
    
    def scrape_all_products(self, max_pages: int = None, delay: float = 3.0) -> List[Dict]:
        """
        Scrape all products.
        
        Args:
            max_pages: Maximum pages to scrape
            delay: Delay between pages (3+ seconds recommended)
        """
        print(f"\n{'='*80}")
        print("SPAR UNDETECTED SCRAPER - Starting")
        print(f"Using undetected-chromedriver to bypass bot detection")
        print(f"{'='*80}\n")
        
        if not self.start_browser():
            return []
        
        if not self.establish_session():
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
                if page_num > 1:
                    # Navigate to page
                    url = f"{self.base_url}/produktwelt/suche?page={page_num}"
                    print(f"    Navigating to: {url}")
                    
                    self.driver.get(url)
                    time.sleep(2)
                    
                    # Check if we got redirected
                    current_url = self.driver.current_url
                    print(f"    Current URL: {current_url}")
                    
                    if f"page={page_num}" not in current_url and page_num > 1:
                        print(f"    ⚠️  Redirected! Trying to click pagination...")
                        
                        # Try clicking pagination
                        if not self._click_to_page(page_num):
                            print(f"    ❌ Could not reach page {page_num}")
                            break
                
                # Scroll to load images
                self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight / 2);")
                time.sleep(0.5)
                self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(1)
                
                # Extract products
                products = self._extract_products()
                
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
    
    def _click_to_page(self, target_page: int) -> bool:
        """Try to click to a specific page."""
        try:
            # Scroll to pagination
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(1)
            
            # Try to find page number button
            try:
                page_button = self.driver.find_element(By.XPATH, 
                    f"//a[contains(text(), '{target_page}') or @aria-label='{target_page}']")
                page_button.click()
                print(f"    ✓ Clicked page {target_page} button")
                time.sleep(3)
                return True
            except:
                pass
            
            # Try next button multiple times
            for _ in range(target_page - 1):
                try:
                    next_buttons = self.driver.find_elements(By.XPATH,
                        "//a[contains(@aria-label, 'next') or contains(text(), 'Weiter')]")
                    if next_buttons:
                        next_buttons[0].click()
                        time.sleep(2)
                    else:
                        return False
                except:
                    return False
            
            return True
        
        except Exception as e:
            print(f"    [!] Click error: {e}")
            return False
    
    def _extract_products(self) -> List[Dict]:
        """Extract products from current page."""
        products_data = []
        
        try:
            # Find product elements
            products = self.driver.find_elements(By.CSS_SELECTOR, '[class*="product-card"]')
            
            if not products:
                products = self.driver.find_elements(By.CSS_SELECTOR, '[class*="product-item"]')
            
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
        
        except Exception as e:
            return []
    
    def _extract_product_from_element(self, element) -> Optional[Dict]:
        """Extract product data from element."""
        try:
            # Name
            try:
                name_elem = element.find_element(By.CSS_SELECTOR, 'h3, h4, [class*="name"]')
                name = name_elem.text.strip()
            except:
                return None
            
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
                price_elem = element.find_element(By.CSS_SELECTOR, '[class*="price"]')
                price = self._parse_price(price_elem.text)
            except:
                all_text = element.text
                match = re.search(r'€\s*(\d+[,\.]\d{2})', all_text)
                if match:
                    price = self._parse_price(match.group(1))
            
            if not price or price <= 0:
                return None
            
            # Image
            image_url = None
            try:
                img_elem = element.find_element(By.TAG_NAME, 'img')
                for attr in ['data-src', 'data-lazy-src', 'srcset', 'src']:
                    url = img_elem.get_attribute(attr)
                    if url and not any(x in url.lower() for x in ['placeholder', 'icon', 'veggie', 'badge']):
                        if ' ' in url:
                            url = url.split(',')[-1].strip().split()[0]
                        if not url.startswith('http'):
                            url = 'https:' + url if url.startswith('//') else self.base_url + url
                        image_url = url
                        break
            except:
                pass
            
            # URL
            product_url = None
            try:
                link = element.find_element(By.TAG_NAME, 'a')
                product_url = link.get_attribute('href')
            except:
                pass
            
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
                    print(f"    [{stats['processed']}/{len(products)}]")
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
        scraper = SparUndetectedFinalScraper(headless=False)
        
        print("\n" + "="*80)
        print("TESTING UNDETECTED SCRAPER")
        print("="*80)
        print("\nThis will test 20 pages to see if pagination works.")
        print("Watch the browser - does it stay on page 2 or redirect to page 1?")
        print("\nPress Ctrl+C to stop at any time.\n")
        
        input("Press ENTER to start...")
        
        products = scraper.scrape_all_products(max_pages=20, delay=3.0)
        
        if products:
            print(f"\n✓ Got {len(products)} unique products!")
            
            if len(products) > 50:
                print("✅ SUCCESS! Pagination is working!")
                print(f"   Got {len(products)} products from multiple pages")
            else:
                print("⚠️  Only got {len(products)} products")
                print("   Pagination might still be blocked")
            
            stats = scraper.save_to_database(products, db.session)
            
            print(f"\n{'='*80}")
            print("STATISTICS")
            print(f"{'='*80}")
            for k, v in stats.items():
                print(f"{k:25s}: {v}")
            print(f"{'='*80}\n")
        else:
            print("\n❌ No products scraped")
            print("SPAR's bot protection is very strong")
            print("\nRecommendations:")
            print("1. Try with headless=False and manually interact")
            print("2. Use slower delays (5+ seconds)")
            print("3. Focus on other stores (Billa, Hofer, Lidl)")
            print("4. Contact SPAR for official API access")


if __name__ == "__main__":
    main()
