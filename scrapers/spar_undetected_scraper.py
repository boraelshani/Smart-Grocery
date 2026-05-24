"""
SPAR Scraper using Undetected ChromeDriver
This bypasses bot detection to scrape all 37,692 products
"""

import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
import re
from datetime import datetime, timezone
from typing import List, Dict, Optional, Tuple
from decimal import Decimal


class SparUndetectedScraper:
    """SPAR scraper using undetected-chromedriver to bypass bot detection."""
    
    def __init__(self, headless=False):
        self.headless = headless
        self.base_url = "https://www.spar.at"
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
        
        options = uc.ChromeOptions()
        if self.headless:
            options.add_argument('--headless=new')
        
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-blink-features=AutomationControlled')
        options.add_argument('--lang=de-AT')
        
        # Use undetected chromedriver
        self.driver = uc.Chrome(options=options, version_main=None)
        self.driver.set_page_load_timeout(30)
        
        # Visit homepage first to establish session
        print("[*] Establishing session...")
        try:
            self.driver.get('https://www.spar.at')
            time.sleep(3)
        except:
            pass
        
        print("[✓] Browser started")
    
    def stop_browser(self):
        """Stop browser."""
        if self.driver:
            self.driver.quit()
        print("[✓] Browser stopped")
    
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
    
    def scrape_page(self, page_num: int) -> List[Dict]:
        """Scrape a single page."""
        url = f"{self.base_url}/produktwelt/suche?search=&page={page_num}"
        
        try:
            print(f"[*] Loading page {page_num}...")
            self.driver.get(url)
            
            # Wait for products to load
            try:
                WebDriverWait(self.driver, 15).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, '[class*="product"]'))
                )
            except:
                print(f"[!] Timeout waiting for products on page {page_num}")
                return []
            
            # Additional wait for dynamic content
            time.sleep(3)
            
            # Scroll to load lazy images
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight / 2);")
            time.sleep(1)
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(2)
            
            # Find product elements
            products = self.driver.find_elements(By.CSS_SELECTOR, '[class*="product-card"]')
            
            if not products:
                print(f"[!] No products found on page {page_num}")
                return []
            
            print(f"    Found {len(products)} product elements")
            
            products_data = []
            
            for product_elem in products:
                try:
                    # Extract name
                    try:
                        name_elem = product_elem.find_element(By.CSS_SELECTOR, 'h3, h4, [class*="name"]')
                        name = name_elem.text.strip()
                    except:
                        continue
                    
                    if not name:
                        continue
                    
                    # Clean name
                    name = re.sub(r'([a-z])([A-Z])', r'\1 \2', name)
                    name = re.sub(r'([A-Z]+)([A-Z][a-z])', r'\1 \2', name)
                    name = ' '.join(name.split())
                    
                    # Extract brand
                    brand = None
                    known_brands = ['SPAR', 'S-BUDGET', 'DESPAR', 'SPAR PREMIUM']
                    for kb in known_brands:
                        if name.upper().startswith(kb.upper()):
                            brand = kb
                            break
                    
                    # Extract price
                    price = None
                    try:
                        # Try multiple selectors
                        price_elem = product_elem.find_element(By.CSS_SELECTOR, '[class*="price"]')
                        price_text = price_elem.text.strip()
                        price = self._parse_price(price_text)
                    except:
                        # Try finding price in all text
                        all_text = product_elem.text
                        price_match = re.search(r'€\s*(\d+[,\.]\d{2})|(\d+[,\.]\d{2})\s*€', all_text)
                        if price_match:
                            price_str = price_match.group(1) or price_match.group(2)
                            price = self._parse_price(price_str)
                    
                    if not price or price <= 0:
                        continue
                    
                    # Extract image
                    image_url = None
                    try:
                        img_elem = product_elem.find_element(By.TAG_NAME, 'img')
                        image_url = img_elem.get_attribute('src') or img_elem.get_attribute('data-src')
                    except:
                        pass
                    
                    # Extract URL
                    product_url = None
                    try:
                        link_elem = product_elem.find_element(By.TAG_NAME, 'a')
                        product_url = link_elem.get_attribute('href')
                    except:
                        pass
                    
                    # Extract unit info
                    unit, size_normalized = self._extract_unit_info(name)
                    
                    product_data = {
                        'name': name,
                        'brand': brand,
                        'price': price,
                        'image_url': image_url,
                        'product_url': product_url,
                        'unit': unit,
                        'size_normalized': size_normalized,
                        'scraped_at': datetime.now(timezone.utc)
                    }
                    
                    products_data.append(product_data)
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
            print(f"[!] Error scraping page {page_num}: {e}")
            self.stats['errors'] += 1
            return []
    
    def scrape_all_products(self, max_pages: int = None, delay: float = 2.0) -> List[Dict]:
        """Scrape all products from SPAR."""
        print(f"\n{'='*80}")
        print("SPAR UNDETECTED SCRAPER - Starting")
        print(f"Target: All 1178 pages (~37,692 products)")
        print(f"{'='*80}\n")
        
        self.start_browser()
        
        all_products = []
        seen_fingerprints = set()
        
        if max_pages is None:
            max_pages = 1178
        
        page = 1
        consecutive_empty = 0
        pages_with_no_new = 0
        
        try:
            while page <= max_pages:
                products = self.scrape_page(page)
                
                if not products:
                    consecutive_empty += 1
                    if consecutive_empty >= 5:
                        print(f"[*] {consecutive_empty} consecutive empty pages. Stopping.")
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
    
    # ── Name normalisation helpers for cross-store matching ──────────────────

    _SIZE_RE = re.compile(
        r'\d+[\.,]?\d*\s*(g|kg|mg|ml|l|cl|dl|stk|stück|x|\d+er)\b',
        re.IGNORECASE,
    )
    _STOP = frozenset({
        'g','kg','ml','l','cl','stk','x','und','mit','von','der','die','das',
        'bio','pack','set','je','pro','im','aus','fur','natur','natural',
    })

    def _normalise_words(self, name: str):
        n = name.lower()
        for src, tgt in (('ä','ae'),('ö','oe'),('ü','ue'),('ß','ss')):
            n = n.replace(src, tgt)
        n = self._SIZE_RE.sub(' ', n)
        n = re.sub(r'[^\w\s]', ' ', n)
        return frozenset(w for w in n.split() if len(w) >= 3 and w not in self._STOP)

    def _similarity(self, ws1, ws2):
        if not ws1 or not ws2:
            return 0.0
        return len(ws1 & ws2) / max(len(ws1), len(ws2))

    def _find_billa_match(self, spar_name: str, billa_index: dict,
                          billa_word_sets: dict, threshold: float = 0.6):
        """Return (billa_product_id, score) or (None, 0)."""
        spar_words = self._normalise_words(spar_name)
        candidates = set()
        for w in spar_words:
            candidates.update(billa_index.get(w, set()))
        best_id, best_score = None, 0.0
        for bpid in candidates:
            score = self._similarity(spar_words, billa_word_sets[bpid])
            if score > best_score:
                best_score, best_id = score, bpid
        return (best_id, best_score) if best_score >= threshold else (None, 0.0)

    def _build_billa_index(self, db_session):
        """Load all BILLA products and build an inverted word index."""
        from models.postgres_models import Product, ProductStore
        from collections import defaultdict
        rows = (
            db_session.query(Product.id, Product.name, Product.name_de)
            .join(ProductStore, ProductStore.product_id == Product.id)
            .filter(ProductStore.store_id == 'billa')
            .all()
        )
        word_sets = {}
        index = defaultdict(set)
        for row in rows:
            name = row.name or row.name_de or ''
            ws = self._normalise_words(name)
            word_sets[row.id] = ws
            for w in ws:
                index[w].add(row.id)
        print(f"[*] BILLA index built: {len(rows):,} products")
        return index, word_sets

    # ── Main save method ──────────────────────────────────────────────────────

    def save_to_database(self, products: List[Dict], db_session) -> Dict:
        """
        Save scraped SPAR products to the database.

        For each product we first check whether a matching BILLA product
        already exists (by normalised name similarity ≥ 0.6).  If so, we
        attach a SPAR ProductStore row to that existing product instead of
        creating a new Product row.  This is what makes cross-store price
        comparison possible on the compare page.
        """
        from models.postgres_models import Product, ProductStore, Store

        print(f"\n{'='*80}")
        print("DATABASE INSERTION - Starting (with cross-store linking)")
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

        # Pre-load BILLA index for fast cross-store matching
        billa_index, billa_word_sets = self._build_billa_index(db_session)

        stats = {
            'processed': 0,
            'linked_to_billa': 0,
            'products_added': 0,
            'products_updated': 0,
            'product_stores_added': 0,
            'product_stores_updated': 0,
            'validation_errors': 0,
            'database_errors': 0,
        }

        for product_data in products:
            try:
                stats['processed'] += 1

                if not product_data.get('name') or not product_data.get('price'):
                    stats['validation_errors'] += 1
                    continue

                spar_name  = product_data['name']
                spar_price = Decimal(str(product_data['price']))
                spar_url   = product_data.get('product_url')
                spar_image = product_data.get('image_url')
                now        = datetime.now(timezone.utc)

                # ── Try to match a BILLA product first ───────────────────────
                billa_pid, score = self._find_billa_match(
                    spar_name, billa_index, billa_word_sets
                )

                if billa_pid:
                    # Attach SPAR price to the existing BILLA product row
                    existing_ps = db_session.query(ProductStore).filter_by(
                        product_id=billa_pid, store_id='spar'
                    ).first()

                    if not existing_ps:
                        db_session.add(ProductStore(
                            product_id=billa_pid,
                            store_id='spar',
                            base_price=spar_price,
                            is_available=True,
                            product_url=spar_url,
                            last_seen=now,
                            created_at=now,
                        ))
                        stats['product_stores_added'] += 1
                    else:
                        existing_ps.base_price = spar_price
                        existing_ps.is_available = True
                        existing_ps.last_seen = now
                        stats['product_stores_updated'] += 1

                    # Back-fill image if BILLA product has none
                    if spar_image:
                        billa_product = db_session.get(Product, billa_pid)
                        if billa_product and not billa_product.default_image_url:
                            billa_product.default_image_url = spar_image

                    stats['linked_to_billa'] += 1

                else:
                    # ── No BILLA match — save as standalone SPAR product ─────
                    fingerprint = self._generate_fingerprint(
                        spar_name,
                        product_data.get('brand', ''),
                        product_data.get('unit', ''),
                        product_data.get('size_normalized'),
                    )
                    product = db_session.query(Product).filter_by(
                        fingerprint=fingerprint
                    ).first()

                    if not product:
                        product = Product(
                            fingerprint=fingerprint,
                            name=spar_name,
                            name_de=spar_name,
                            brand=product_data.get('brand'),
                            unit_normalized=product_data.get('unit'),
                            size_normalized=product_data.get('size_normalized'),
                            default_image_url=spar_image,
                            created_at=now,
                            updated_at=now,
                        )
                        db_session.add(product)
                        db_session.flush()
                        stats['products_added'] += 1
                    else:
                        if spar_image and not product.default_image_url:
                            product.default_image_url = spar_image
                            product.updated_at = now
                        stats['products_updated'] += 1

                    ps = db_session.query(ProductStore).filter_by(
                        product_id=product.id, store_id='spar'
                    ).first()
                    if not ps:
                        db_session.add(ProductStore(
                            product_id=product.id,
                            store_id='spar',
                            base_price=spar_price,
                            is_available=True,
                            product_url=spar_url,
                            last_seen=now,
                            created_at=now,
                        ))
                        stats['product_stores_added'] += 1
                    else:
                        ps.base_price = spar_price
                        ps.is_available = True
                        ps.last_seen = now
                        stats['product_stores_updated'] += 1

                if stats['processed'] % 100 == 0:
                    db_session.commit()
                    print(
                        f"[*] {stats['processed']}/{len(products)} | "
                        f"linked={stats['linked_to_billa']} "
                        f"new={stats['products_added']}"
                    )

            except Exception as e:
                print(f"[!] DB error on '{product_data.get('name','?')}': {e}")
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
        scraper = SparUndetectedScraper(headless=True)
        
        # Scrape products
        products = scraper.scrape_all_products(max_pages=None, delay=1.5)
        
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
