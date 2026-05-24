"""
===========================================================================
SPAR AUSTRIA SCRAPER - SESSION-BASED VERSION
===========================================================================
This version establishes a proper session before scraping to avoid redirects.

Strategy:
1. Visit homepage first
2. Navigate to search page naturally
3. Interact with page (scroll, wait)
4. Then start pagination
===========================================================================
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
        
        print("[[OK]] Browser started")
    
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
        print("[[OK]] Browser stopped")
    
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
                for selector in [
                    'button:has-text("Akzeptieren")',
                    'button:has-text("Accept")',
                    '[class*="cookie"] button',
                    '[id*="cookie"] button',
                ]:
                    try:
                        button = self.page.query_selector(selector)
                        if button:
                            button.click()
                            print("        [OK] Accepted cookies")
                            time.sleep(1)
                            break
                    except:
                        continue
            except:
                pass

            # Step 3: Navigate to product listing page 1
            print("    [3/4] Navigating to products...")
            self.page.goto(
                f"{self.base_url}/produktwelt/suche?page=1",
                wait_until='domcontentloaded', timeout=30000
            )
            # SPA needs time to hydrate and render all products
            time.sleep(4)
            # Dismiss any CMP overlay left behind after cookie accept
            self._dismiss_overlay()

            # Step 4: Scroll to trigger lazy-loading, then wait for full render
            print("    [4/4] Interacting with page...")
            self.page.evaluate('window.scrollTo(0, 600)')
            time.sleep(1)
            self.page.evaluate('window.scrollTo(0, 1200)')
            time.sleep(1)
            self.page.evaluate('window.scrollTo(0, 0)')
            time.sleep(1)

            # Wait until we see at least 20 product cards (full render)
            try:
                self.page.wait_for_function(
                    "document.querySelectorAll('[class*=\"product-card\"]').length >= 20",
                    timeout=15000
                )
                count = len(self.page.query_selector_all('[class*="product-card"]'))
                print(f"[[OK]] Session established — {count} product cards visible")
                self.session_established = True
                return True
            except:
                # Accept whatever is there
                count = len(self.page.query_selector_all('[class*="product-card"]'))
                if count > 0:
                    print(f"[[OK]] Session established ({count} products found, less than expected)")
                    self.session_established = True
                    return True
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

        max_pages_limit = max_pages or 1181
        page_num = 1
        consecutive_empty = 0

        try:
            while page_num <= max_pages_limit:
                print(f"\n[*] Page {page_num}/{max_pages_limit}")

                # Wait for the SPA to render products (needs ~4 s after navigation)
                time.sleep(4)
                self.page.evaluate('window.scrollTo(0, 600)')
                time.sleep(0.5)
                self.page.evaluate('window.scrollTo(0, 0)')
                time.sleep(0.5)

                # Wait until at least 20 product cards are in the DOM
                try:
                    self.page.wait_for_function(
                        "document.querySelectorAll('[class*=\"product-card\"]').length >= 20",
                        timeout=12000
                    )
                except:
                    pass  # proceed with whatever is there

                # Extract products from current page
                products = self._extract_products_from_current_page()

                if not products:
                    print(f"    [!] No products found on page {page_num}")
                    consecutive_empty += 1
                    if consecutive_empty >= 3:
                        break
                    # Try to advance anyway
                    if not self._click_next_page_button():
                        break
                    page_num += 1
                    continue

                consecutive_empty = 0

                # Count new products
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

                print(f"[[OK]] Page {page_num} | Found: {len(products)} | New: {new_count} | Total: {len(all_products)}")
                if products:
                    print(f"    First: {products[0]['name'][:60]}")

                if page_num >= max_pages_limit:
                    break

                # Navigate to next page by clicking the SPAR pagination arrow
                # (URL navigation doesn't work — SPAR is a SPA that ignores ?page=N on reload)
                if not self._click_next_page_button():
                    print(f"[*] No next page button found. Scraping complete.")
                    break

                page_num += 1

                if page_num % 25 == 0:
                    print(f"\n{'='*80}")
                    print(f"Progress: {page_num}/{max_pages_limit} | Products: {len(all_products)}")
                    print(f"{'='*80}\n")

                # Small extra polite delay between pages
                time.sleep(delay)

        except KeyboardInterrupt:
            print(f"\n[!] Interrupted at page {page_num}")

        finally:
            self.stop_browser()

        print(f"\n{'='*80}")
        print(f"[[OK]] Complete! Pages: {page_num} | Products: {len(all_products)}")
        print(f"{'='*80}\n")

        return all_products

    def _dismiss_overlay(self):
        """Remove/disable any cookie/CMP overlay that blocks pointer events."""
        try:
            self.page.evaluate("""
                // Disable pointer-events on cookie consent wrappers
                ['cmpwrapper', 'cmpbox', 'cmp-wrapper', 'cmp-box'].forEach(id => {
                    const el = document.getElementById(id);
                    if (el) el.style.pointerEvents = 'none';
                });
                // Also catch any fixed/absolute overlay covering the viewport
                document.querySelectorAll('[id^="cmp"], [class*="cmp-"]').forEach(el => {
                    el.style.pointerEvents = 'none';
                });
            """)
        except:
            pass

    def _click_next_page_button(self) -> bool:
        """Find and click SPAR's next-page pagination arrow. Returns True if clicked."""
        try:
            # Dismiss CMP overlay — it intercepts pointer events and blocks clicks
            self._dismiss_overlay()
            time.sleep(0.2)

            # SPAR's "next page" button has data-tosca="plp-pagination-next-btn"
            # This is the most reliable selector (aria-label is language-dependent)
            for selector in [
                '[data-tosca="plp-pagination-next-btn"]:not(.btn--disabled)',
                '[data-tosca="plp-pagination-next-btn"]',
            ]:
                try:
                    self.page.click(selector, timeout=5000)
                    time.sleep(1)
                    return True
                except:
                    pass

            # Fallback: aria-label of the next button
            for aria in [
                'button[aria-label="Zur nächsten Seite"]:not(.btn--disabled)',
                'button[aria-label*="nächsten"]:not(.btn--disabled)',
            ]:
                try:
                    self.page.click(aria, timeout=3000)
                    time.sleep(1)
                    return True
                except:
                    pass

            # Last resort: scroll to bottom and force-click the next button
            self.page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
            time.sleep(0.8)
            self._dismiss_overlay()

            for selector in [
                '[data-tosca="plp-pagination-next-btn"]',
                '[class*="pagination__arrow"]:not([class*="btn--disabled"])',
            ]:
                try:
                    btn = self.page.query_selector(selector)
                    if btn:
                        btn.scroll_into_view_if_needed()
                        time.sleep(0.3)
                        btn.click(force=True)
                        time.sleep(1)
                        return True
                except:
                    continue

            return False
        except:
            return False

    def _try_click_to_page(self, target_page: int) -> bool:
        """Try to click to a specific page number."""
        try:
            self.page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
            time.sleep(0.5)
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
            # SPAR uses class "product-tile spar-plp__product-card"
            # Both selectors below match it; stop at first with >=5 hits.
            selectors = [
                '[class*="product-card"]',   # matches spar-plp__product-card
                '[class*="product-tile"]',   # also matches product-tile
                '[class*="product-item"]',
                'article[class*="product"]',
                '[data-testid*="product"]',
            ]
            products = []

            for selector in selectors:
                candidates = self.page.query_selector_all(selector)
                if candidates and len(candidates) >= 5:
                    products = candidates
                    break

            # Fallback: any element containing a € price
            if not products:
                for fallback in ['article', 'li[class]']:
                    candidates = self.page.query_selector_all(fallback)
                    with_price = [
                        el for el in candidates
                        if '€' in (el.inner_text() or '') and len(el.inner_text() or '') > 15
                    ]
                    if len(with_price) >= 5:
                        products = with_price
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
        """Extract product data from a SPAR product card element."""
        try:
            # ── Name ──────────────────────────────────────────────────────────
            # SPAR uses class "product-tile__name" for the product name
            name_elem = (
                element.query_selector('[class*="product-tile__name"]')
                or element.query_selector('[class*="name"]')
                or element.query_selector('h2, h3, h4')
            )
            if not name_elem:
                return None
            name = name_elem.inner_text().strip()
            if not name or len(name) < 3:
                return None
            # Remove size info that SPAR appends directly to the name text
            # e.g. "Schloss Fels Grüner Veltliner 0,75 L" → keep as-is (it's useful)
            # Clean up camelCase artifacts and extra whitespace
            name = re.sub(r'([a-z])([A-Z])', r'\1 \2', name)
            name = ' '.join(name.split())

            # ── Brand ─────────────────────────────────────────────────────────
            brand = None
            for kb in ['SPAR', 'S-BUDGET', 'DESPAR']:
                if name.upper().startswith(kb):
                    brand = kb
                    break

            # ── Price ─────────────────────────────────────────────────────────
            # SPAR's "product-price__price" element always contains just the
            # current price (e.g. "5,32"), even for promotional / bundle items.
            price = None
            price_elem = element.query_selector('[class*="product-price__price"]')
            if price_elem:
                price = self._parse_price(price_elem.inner_text())

            if not price:
                # Fallback: price-box (may contain "statt 7,99 5,32" — take last number)
                pb = element.query_selector('[class*="price-box"]')
                if pb:
                    matches = re.findall(r'(\d+[,\.]\d{2})', pb.inner_text())
                    if matches:
                        try:
                            price = float(matches[-1].replace(',', '.'))
                        except:
                            pass

            if not price:
                # Last resort: scan full element text for any price
                all_text = element.inner_text()
                matches = re.findall(r'(\d+[,\.]\d{2})', all_text)
                prices = []
                for m in matches:
                    try:
                        prices.append(float(m.replace(',', '.')))
                    except:
                        pass
                if prices:
                    # Filter out per-unit/unreasonable values; take the cheapest
                    reasonable = [p for p in prices if 0.05 <= p <= 999]
                    if reasonable:
                        price = min(reasonable)

            if not price or price <= 0:
                return None

            # ── Image ─────────────────────────────────────────────────────────
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

            # ── Product URL ───────────────────────────────────────────────────
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
                'scraped_at': datetime.now(timezone.utc),
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
    
    # -- Name-normalisation helpers for cross-store matching ------------------

    _SIZE_RE = re.compile(
        r'\d+[\.,]?\d*\s*(g|kg|mg|ml|l|cl|dl|stk|stück|x|\d+er)\b',
        re.IGNORECASE,
    )
    _STOP = frozenset({
        'g','kg','ml','l','cl','stk','x','und','mit','von','der','die','das',
        'bio','pack','set','je','pro','im','aus','fur','natur','natural',
    })

    def _norm_words(self, name: str) -> frozenset:
        n = name.lower()
        for s, t in (('ä','ae'),('ö','oe'),('ü','ue'),('ß','ss')):
            n = n.replace(s, t)
        n = self._SIZE_RE.sub(' ', n)
        n = re.sub(r'[^\w\s]', ' ', n)
        return frozenset(w for w in n.split() if len(w) >= 3 and w not in self._STOP)

    def _similarity(self, a: frozenset, b: frozenset) -> float:
        if not a or not b:
            return 0.0
        return len(a & b) / max(len(a), len(b))

    def _build_billa_index(self, db_session):
        from models.postgres_models import Product, ProductStore
        from collections import defaultdict
        rows = (
            db_session.query(Product.id, Product.name, Product.name_de)
            .join(ProductStore, ProductStore.product_id == Product.id)
            .filter(ProductStore.store_id == 'billa')
            .all()
        )
        word_sets, index = {}, defaultdict(set)
        for r in rows:
            ws = self._norm_words(r.name or r.name_de or '')
            word_sets[r.id] = ws
            for w in ws:
                index[w].add(r.id)
        print(f"[*] BILLA index: {len(rows):,} products")
        return index, word_sets

    def _find_billa_match(self, name, billa_index, billa_word_sets, threshold=0.6):
        spar_words = self._norm_words(name)
        candidates = set()
        for w in spar_words:
            candidates.update(billa_index.get(w, set()))
        best_id, best_score = None, 0.0
        for bpid in candidates:
            score = self._similarity(spar_words, billa_word_sets[bpid])
            if score > best_score:
                best_score, best_id = score, bpid
        return (best_id, best_score) if best_score >= threshold else (None, 0.0)

    # -- Main save method ------------------------------------------------------

    def save_to_database(self, products: List[Dict], db_session) -> Dict:
        """
        Save SPAR products, auto-linking to existing BILLA products where
        names match (similarity >= 0.6).  Matched products share one Product
        row; two ProductStore rows give the side-by-side price comparison.
        """
        from models.postgres_models import Product, ProductStore, Store

        print(f"\n[*] Saving {len(products)} products (with BILLA cross-linking)...")

        store = db_session.query(Store).filter_by(store_id='spar').first()
        if not store:
            store = Store(store_id='spar', name='SPAR', website='https://www.spar.at',
                         country='AT', active=True)
            db_session.add(store)
            db_session.commit()

        billa_index, billa_word_sets = self._build_billa_index(db_session)

        stats = {
            'processed': 0, 'linked_to_billa': 0,
            'products_added': 0, 'products_updated': 0,
            'product_stores_added': 0, 'product_stores_updated': 0,
        }

        for pd in products:
            try:
                stats['processed'] += 1
                if not pd.get('name') or not pd.get('price'):
                    continue

                name       = pd['name']
                price      = Decimal(str(pd['price']))
                now        = datetime.now(timezone.utc)
                spar_url   = pd.get('product_url')
                spar_image = pd.get('image_url')

                # Try BILLA match first
                billa_pid, _ = self._find_billa_match(name, billa_index, billa_word_sets)

                if billa_pid:
                    ps = db_session.query(ProductStore).filter_by(
                        product_id=billa_pid, store_id='spar').first()
                    if not ps:
                        db_session.add(ProductStore(
                            product_id=billa_pid, store_id='spar',
                            base_price=price, is_available=True,
                            product_url=spar_url, last_seen=now, created_at=now))
                        stats['product_stores_added'] += 1
                    else:
                        ps.base_price = price
                        ps.is_available = True
                        ps.last_seen = now
                        stats['product_stores_updated'] += 1

                    if spar_image:
                        bp = db_session.get(Product, billa_pid)
                        if bp and not bp.default_image_url:
                            bp.default_image_url = spar_image

                    stats['linked_to_billa'] += 1

                else:
                    fp = self._generate_fingerprint(
                        name, pd.get('brand', ''), pd.get('unit', ''),
                        pd.get('size_normalized'))
                    product = db_session.query(Product).filter_by(fingerprint=fp).first()
                    if not product:
                        product = Product(
                            fingerprint=fp, name=name, name_de=name,
                            brand=pd.get('brand'), unit_normalized=pd.get('unit'),
                            size_normalized=pd.get('size_normalized'),
                            default_image_url=spar_image,
                            created_at=now, updated_at=now)
                        db_session.add(product)
                        db_session.flush()
                        stats['products_added'] += 1
                    else:
                        if spar_image and not product.default_image_url:
                            product.default_image_url = spar_image
                        stats['products_updated'] += 1

                    ps = db_session.query(ProductStore).filter_by(
                        product_id=product.id, store_id='spar').first()
                    if not ps:
                        db_session.add(ProductStore(
                            product_id=product.id, store_id='spar',
                            base_price=price, is_available=True,
                            product_url=spar_url, last_seen=now, created_at=now))
                        stats['product_stores_added'] += 1
                    else:
                        ps.base_price = price
                        ps.is_available = True
                        ps.last_seen = now
                        stats['product_stores_updated'] += 1

                if stats['processed'] % 100 == 0:
                    db_session.commit()
                    print(f"[*] {stats['processed']}/{len(products)} | "
                          f"linked={stats['linked_to_billa']} new={stats['products_added']}")

            except Exception as e:
                db_session.rollback()
                continue

        db_session.commit()
        print(f"[[OK]] Done! linked={stats['linked_to_billa']} "
              f"new={stats['products_added']} updated={stats['products_updated']}")
        return stats


def main():
    """Main execution — scrapes ALL SPAR pages and links products to BILLA."""
    from app import app
    from models.postgres_models import db

    with app.app_context():
        scraper = SparSessionScraper(headless=False)
        # Scrape all pages (headless=False so the browser window is visible)
        products = scraper.scrape_all_products(max_pages=None, delay=1.5)

        if products:
            print(f"\n[*] Scraped {len(products):,} unique products. Saving...")
            stats = scraper.save_to_database(products, db.session)
            print(f"\n{'='*60}")
            for k, v in stats.items():
                print(f"  {k:<30} {v}")
            print(f"{'='*60}\n")
        else:
            print("[!] No products scraped.")


if __name__ == "__main__":
    main()
