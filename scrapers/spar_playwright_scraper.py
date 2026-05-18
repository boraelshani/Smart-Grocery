"""
═══════════════════════════════════════════════════════════════════════════
SPAR AUSTRIA SCRAPER - PLAYWRIGHT VERSION
═══════════════════════════════════════════════════════════════════════════
Advanced scraper using Playwright to bypass anti-bot protection.

Installation:
    pip install playwright
    playwright install chromium

Features:
- Uses real browser to bypass bot detection
- JavaScript rendering support
- Handles dynamic content
- More reliable than requests-based scraping

Usage:
    python run_spar_playwright_scraper.py
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


class SparPlaywrightScraper:
    """
    SPAR Austria scraper using Playwright for reliable data extraction.
    """
    
    def __init__(self, headless=True):
        """
        Initialize the Playwright-based scraper.
        
        Args:
            headless: Run browser in headless mode (default: True)
        """
        self.headless = headless
        self.base_url = "https://www.spar.at"
        self.store_id = "spar"
        self.playwright = None
        self.browser = None
        self.context = None
        self.page = None
        
        # SPAR categories to scrape
        self.categories = [
            ('Lebensmittel', '/produktwelt/lebensmittel'),
            ('Getränke', '/produktwelt/getraenke'),
            ('Drogerie & Beauty', '/produktwelt/drogerie-beauty'),
            ('Haushalt', '/produktwelt/haushalt'),
        ]
        
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
        
        # Launch browser with more realistic settings
        self.browser = self.playwright.chromium.launch(
            headless=self.headless,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--disable-dev-shm-usage',
                '--no-sandbox',
                '--disable-web-security',
                '--disable-features=IsolateOrigins,site-per-process',
            ]
        )
        
        # Create context with realistic settings and persistent cookies
        self.context = self.browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            locale='de-AT',
            timezone_id='Europe/Vienna',
            accept_downloads=True,
            has_touch=False,
            is_mobile=False,
            java_script_enabled=True,
        )
        
        # Create page
        self.page = self.context.new_page()
        
        # Enhanced anti-detection
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
            window.chrome = {
                runtime: {}
            };
        """)
        
        # First, visit the homepage to establish session
        print("[*] Establishing session...")
        try:
            self.page.goto('https://www.spar.at', wait_until='domcontentloaded', timeout=30000)
            self.page.wait_for_timeout(2000)
        except:
            pass  # Continue even if homepage fails
        
        print("[✓] Browser started")
    
    def stop_browser(self):
        """Stop Playwright browser."""
        if self.page:
            self.page.close()
        if self.context:
            self.context.close()
        if self.browser:
            self.browser.close()
        if self.playwright:
            self.playwright.stop()
        print("[✓] Browser stopped")
    
    def _extract_unit_info(self, text: str) -> Tuple[Optional[str], Optional[float]]:
        """Extract unit and size from product text."""
        if not text:
            return None, None
        
        text = text.lower().replace(',', '.')
        
        # Pattern: quantity x size unit
        multi_match = re.search(r'(\d+)\s*x\s*(\d+(?:\.\d+)?)\s*(kg|g|l|ml|stk|stück)', text)
        if multi_match:
            qty = float(multi_match.group(1))
            size = float(multi_match.group(2))
            unit = multi_match.group(3)
            unit = 'stk' if unit == 'stück' else unit
            return unit, qty * size
        
        # Pattern: simple size unit
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
    
    def _parse_date(self, date_text: str) -> Optional[datetime]:
        """Parse German date formats to datetime."""
        if not date_text:
            return None
        
        match = re.search(r'(\d{1,2})\.(\d{1,2})\.(\d{4})', date_text)
        if match:
            day, month, year = match.groups()
            try:
                return datetime(int(year), int(month), int(day), tzinfo=timezone.utc)
            except ValueError:
                return None
        
        if 'woche' in date_text.lower():
            today = datetime.now(timezone.utc)
            days_until_sunday = (6 - today.weekday()) % 7
            return today + timedelta(days=days_until_sunday)
        
        return None
    
    def _generate_fingerprint(self, name: str, brand: str, unit: str, size: float) -> str:
        """Generate unique fingerprint for product deduplication."""
        name_norm = re.sub(r'[^\w\s]', '', name.lower()).strip()
        brand_norm = re.sub(r'[^\w\s]', '', (brand or '').lower()).strip()
        unit_norm = (unit or '').lower()
        size_norm = f"{size:.2f}" if size else ""
        
        parts = [p for p in [brand_norm, name_norm, size_norm, unit_norm] if p]
        return '_'.join(parts)
    
    def scrape_page(self, page_num: int = 1) -> List[Dict]:
        """
        Scrape a single page of products.
        
        Args:
            page_num: Page number to scrape
            
        Returns:
            List of product dictionaries
        """
        # Use the correct parameter order that SPAR expects
        url = f"{self.base_url}/produktwelt/suche?page={page_num}&search="
        print(f"[*] Scraping page {page_num}: {url}")
        
        try:
            # Navigate to page with longer timeout
            self.page.goto(url, wait_until='domcontentloaded', timeout=30000)
            
            # Wait for products to load
            try:
                self.page.wait_for_selector('[class*="product"]', timeout=15000)
            except PlaywrightTimeout:
                print(f"[!] Timeout waiting for products on page {page_num}")
                return []
            
            # Scroll down to trigger lazy loading
            self.page.evaluate('window.scrollTo(0, document.body.scrollHeight / 2)')
            self.page.wait_for_timeout(1000)
            self.page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
            self.page.wait_for_timeout(2000)
            
            # Wait for network to be idle (all images/data loaded)
            self.page.wait_for_load_state('networkidle', timeout=10000)
            
            # Additional wait for any animations
            self.page.wait_for_timeout(1000)
            
            # Find product elements using various selectors
            product_selectors = [
                '[class*="product-card"]',
                '[class*="product-item"]',
                '[class*="product-tile"]',
                '[data-product]',
                'article[class*="product"]',
                'div[class*="product"]'
            ]
            
            products_data = []
            products = []
            
            for selector in product_selectors:
                products = self.page.query_selector_all(selector)
                if products and len(products) > 5:  # Need reasonable number of products
                    print(f"[*] Found {len(products)} products using selector: {selector}")
                    break
            
            if not products:
                print(f"[!] No products found on page {page_num}")
                return []
            
            # Extract data from each product
            for i, product_elem in enumerate(products):
                try:
                    product_data = self._extract_product_from_element(product_elem)
                    if product_data:
                        products_data.append(product_data)
                        self.stats['products_scraped'] += 1
                    else:
                        self.stats['skipped'] += 1
                except Exception as e:
                    print(f"[!] Error extracting product {i+1}: {e}")
                    self.stats['errors'] += 1
            
            if not products_data:
                print(f"[!] No valid products extracted from page {page_num}")
            else:
                print(f"[✓] Extracted {len(products_data)} products from page {page_num}")
                # Show first product name to verify it's different
                if products_data:
                    print(f"    First product: {products_data[0]['name'][:50]}")
            
            return products_data
            
        except Exception as e:
            print(f"[!] Error scraping page {page_num}: {e}")
            self.stats['errors'] += 1
            return []
    
    def _extract_product_from_element(self, element) -> Optional[Dict]:
        """Extract product data from a Playwright element."""
        try:
            # Extract name - try multiple selectors
            name_elem = (
                element.query_selector('h3, h4') or
                element.query_selector('[class*="name"]') or
                element.query_selector('[class*="title"]') or
                element.query_selector('[class*="product-name"]') or
                element.query_selector('a[class*="product"]')
            )
            if not name_elem:
                return None
            
            name = name_elem.inner_text().strip()
            if not name:
                return None
            
            # Clean up name - add spaces between words if missing
            # "SPARPassionsfrucht" -> "SPAR Passionsfrucht"
            import re
            name = re.sub(r'([a-z])([A-Z])', r'\1 \2', name)
            name = re.sub(r'([A-Z]+)([A-Z][a-z])', r'\1 \2', name)
            name = ' '.join(name.split())  # Clean multiple spaces
            
            # Extract brand - try to identify from name or separate element
            brand_elem = element.query_selector('[class*="brand"]')
            brand = None
            
            if brand_elem:
                brand = brand_elem.inner_text().strip()
            else:
                # Try to extract brand from name
                known_brands = ['SPAR', 'S-BUDGET', 'SPAR PREMIUM', 'SPAR NATUR PUR', 
                               'Clever', 'Ja! Natürlich', 'Milka', 'Manner', 'Almdudler',
                               'Tyrolpilz', 'Bio']
                for kb in known_brands:
                    if name.upper().startswith(kb.upper()):
                        brand = kb
                        break
            
            # Extract price - try multiple selectors and methods
            price = None
            price_text = None
            
            # Try different price selectors
            price_selectors = [
                '[class*="price"]:not([class*="old"]):not([class*="was"])',
                '[class*="current-price"]',
                '[data-price]',
                '.price',
                '[class*="selling-price"]',
                'span[class*="price"]',
                'div[class*="price"]'
            ]
            
            for selector in price_selectors:
                price_elem = element.query_selector(selector)
                if price_elem:
                    price_text = price_elem.inner_text().strip()
                    if not price_text:
                        price_text = price_elem.get_attribute('data-price')
                    if price_text:
                        price = self._parse_price(price_text)
                        if price and price > 0:
                            break
            
            # If still no price, try to find any element with € symbol
            if not price or price <= 0:
                all_text = element.inner_text()
                # Look for price pattern like "€ 2,99" or "2,99 €"
                price_match = re.search(r'€\s*(\d+[,\.]\d{2})|(\d+[,\.]\d{2})\s*€', all_text)
                if price_match:
                    price_str = price_match.group(1) or price_match.group(2)
                    price = self._parse_price(price_str)
            
            if not price or price <= 0:
                return None
            
            # Extract original price - try multiple selectors
            original_price = None
            old_price_elem = (
                element.query_selector('[class*="old"]') or
                element.query_selector('[class*="was"]') or
                element.query_selector('[class*="strike"]') or
                element.query_selector('[class*="original"]')
            )
            if old_price_elem:
                original_price = self._parse_price(old_price_elem.inner_text().strip())
            
            # Extract promo text - try multiple selectors
            promo_elem = (
                element.query_selector('[class*="promo"]') or
                element.query_selector('[class*="badge"]') or
                element.query_selector('[class*="offer"]') or
                element.query_selector('[class*="discount"]')
            )
            promo_text = promo_elem.inner_text().strip() if promo_elem else None
            
            # Extract offer end date - try multiple selectors
            date_elem = (
                element.query_selector('[class*="valid"]') or
                element.query_selector('[class*="gültig"]') or
                element.query_selector('[class*="bis"]') or
                element.query_selector('[class*="until"]')
            )
            offer_end_date = None
            if date_elem:
                offer_end_date = self._parse_date(date_elem.inner_text().strip())
            
            # Extract image - try multiple sources and filter out placeholders
            img_elem = element.query_selector('img')
            image_url = None
            if img_elem:
                # Try multiple attributes
                potential_urls = [
                    img_elem.get_attribute('data-src'),
                    img_elem.get_attribute('data-lazy-src'),
                    img_elem.get_attribute('data-original'),
                    img_elem.get_attribute('srcset'),
                    img_elem.get_attribute('src')
                ]
                
                for url in potential_urls:
                    if url:
                        # Handle srcset (take highest quality - last URL)
                        if ' ' in url:
                            # srcset format: "url1 1x, url2 2x" - take the last (highest quality)
                            parts = url.split(',')
                            url = parts[-1].strip().split()[0]
                        
                        # Skip placeholder/icon images
                        if any(skip in url.lower() for skip in [
                            'placeholder', 'icon', 'logo', 'veggie', 'vegan', 
                            'bio-icon', 'label', 'badge', 'data:image'
                        ]):
                            continue
                        
                        # Make absolute URL
                        if not url.startswith('http'):
                            if url.startswith('//'):
                                url = 'https:' + url
                            elif url.startswith('/'):
                                url = self.base_url + url
                        
                        # Valid image URL found
                        if url.startswith('http'):
                            image_url = url
                            break
            
            # Extract URL
            link_elem = element.query_selector('a')
            product_url = None
            if link_elem:
                product_url = link_elem.get_attribute('href')
                if product_url and not product_url.startswith('http'):
                    if product_url.startswith('//'):
                        product_url = 'https:' + product_url
                    elif product_url.startswith('/'):
                        product_url = self.base_url + product_url
            
            # Extract unit info - try multiple selectors
            unit_elem = (
                element.query_selector('[class*="unit"]') or
                element.query_selector('[class*="size"]') or
                element.query_selector('[class*="grammage"]') or
                element.query_selector('[class*="quantity"]')
            )
            unit_text = unit_elem.inner_text().strip() if unit_elem else name
            unit, size_normalized = self._extract_unit_info(unit_text)
            
            # Determine promotion status
            is_promotion = bool(original_price and original_price > price)
            discount_percentage = None
            if is_promotion:
                discount_percentage = round(((original_price - price) / original_price) * 100, 1)
            
            return {
                'name': name,
                'brand': brand,
                'price': price,
                'original_price': original_price,
                'is_promotion': is_promotion,
                'discount_percentage': discount_percentage,
                'promo_text': promo_text,
                'offer_end_date': offer_end_date,
                'image_url': image_url,
                'product_url': product_url,
                'unit': unit,
                'size_normalized': size_normalized,
                'scraped_at': datetime.now(timezone.utc)
            }
            
        except Exception as e:
            print(f"[!] Error extracting product data: {e}")
            return None
    
    def scrape_all_products(self, max_pages: int = None, delay: float = 1.0, save_every: int = 100) -> List[Dict]:
        """
        Scrape all products from SPAR's main search (all 1178 pages).
        
        Args:
            max_pages: Maximum pages to scrape (None = all 1178 pages)
            delay: Delay between pages in seconds (default: 1.0 for efficiency)
            save_every: Save to database every N pages (default: 100)
            
        Returns:
            List of all products
        """
        print(f"\n{'='*80}")
        print("SPAR PLAYWRIGHT SCRAPER - Starting (Main Search)")
        print(f"Target: ~1178 pages (~37,692 products)")
        print(f"Strategy: Fast scraping with incremental saves")
        print(f"{'='*80}\n")
        
        self.start_browser()
        
        all_products = []
        seen_fingerprints = set()
        
        page = 1
        consecutive_empty = 0
        pages_with_no_new_products = 0
        last_save_page = 0
        
        # If no max_pages specified, scrape all 1178 pages
        if max_pages is None:
            max_pages = 1178
        
        try:
            while page <= max_pages:
                # Use main search URL
                url = f"{self.base_url}/produktwelt/suche?search=&page={page}"
                
                try:
                    products = self._scrape_search_page(url, page)
                except Exception as e:
                    print(f"[!] Error scraping page {page}: {e}")
                    consecutive_empty += 1
                    if consecutive_empty >= 10:
                        print(f"[*] {consecutive_empty} consecutive errors. Stopping.")
                        break
                    page += 1
                    time.sleep(delay * 2)  # Longer delay after error
                    continue
                
                if not products or len(products) == 0:
                    consecutive_empty += 1
                    print(f"[!] No products on page {page} (consecutive: {consecutive_empty})")
                    if consecutive_empty >= 10:
                        print(f"[*] {consecutive_empty} consecutive empty pages. Stopping.")
                        break
                else:
                    consecutive_empty = 0
                    
                    # Check for new products
                    new_products = 0
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
                            new_products += 1
                    
                    print(f"[✓] Page {page}/{max_pages} | New: {new_products} | Total: {len(all_products)}")
                    
                    # Stop if we've seen many pages with no new products
                    if new_products == 0:
                        pages_with_no_new_products += 1
                        if pages_with_no_new_products >= 50:
                            print(f"[*] No new products on last 50 pages. Likely reached the end.")
                            break
                    else:
                        pages_with_no_new_products = 0
                
                # Progress update every 25 pages
                if page % 25 == 0:
                    print(f"\n{'='*80}")
                    print(f"Progress: {page}/{max_pages} pages ({(page/max_pages*100):.1f}%)")
                    print(f"Unique products: {len(all_products)}")
                    print(f"Avg products/page: {len(all_products)/page:.1f}")
                    print(f"{'='*80}\n")
                
                # Incremental save every N pages
                if save_every and (page - last_save_page) >= save_every and len(all_products) > 0:
                    print(f"\n[*] Incremental save at page {page}...")
                    try:
                        self._incremental_save(all_products)
                        last_save_page = page
                        print(f"[✓] Saved {len(all_products)} products to database")
                    except Exception as e:
                        print(f"[!] Save error: {e}")
                
                page += 1
                
                if delay > 0:
                    time.sleep(delay)
        
        except KeyboardInterrupt:
            print(f"\n[!] Interrupted by user at page {page}")
            print(f"[*] Saving {len(all_products)} products before exit...")
            if len(all_products) > 0:
                try:
                    self._incremental_save(all_products)
                    print(f"[✓] Products saved successfully")
                except Exception as e:
                    print(f"[!] Save error: {e}")
        
        finally:
            self.stop_browser()
        
        print(f"\n{'='*80}")
        print(f"[✓] Scraping complete!")
        print(f"[*] Pages scraped: {page - 1}")
        print(f"[*] Total products scraped: {self.stats['products_scraped']}")
        print(f"[*] Unique products: {len(all_products)}")
        print(f"{'='*80}\n")
        return all_products
    
    def _incremental_save(self, products: List[Dict]):
        """Save products incrementally during scraping."""
        from app import app
        from models.postgres_models import db
        
        with app.app_context():
            self.save_to_database(products, db.session)
    
    def _scrape_search_page(self, url: str, page_num: int) -> List[Dict]:
        """
        Scrape a single search results page - OPTIMIZED VERSION.
        
        Args:
            url: Full URL to scrape
            page_num: Page number (for logging)
            
        Returns:
            List of product dictionaries
        """
        try:
            # Navigate to page with faster timeout
            self.page.goto(url, wait_until='domcontentloaded', timeout=20000)
            
            # Wait for products to load
            try:
                self.page.wait_for_selector('[class*="product"]', timeout=10000)
            except PlaywrightTimeout:
                print(f"[!] Timeout on page {page_num}")
                return []
            
            # Quick scroll to trigger lazy loading (optimized timing)
            self.page.evaluate('window.scrollTo(0, document.body.scrollHeight / 2)')
            self.page.wait_for_timeout(500)
            self.page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
            self.page.wait_for_timeout(1000)
            
            # Wait for network idle with shorter timeout
            try:
                self.page.wait_for_load_state('networkidle', timeout=5000)
            except:
                pass  # Continue even if network not idle
            
            # Find product elements - try selectors in order of likelihood
            product_selectors = [
                '[class*="product-card"]',
                '[class*="product-item"]',
                '[class*="product-tile"]',
                '[data-product-id]',
                'article[class*="product"]'
            ]
            
            products = []
            for selector in product_selectors:
                products = self.page.query_selector_all(selector)
                if products and len(products) >= 10:  # SPAR typically shows 32 per page
                    break
            
            if not products:
                return []
            
            # Extract data from each product
            products_data = []
            for product_elem in products:
                try:
                    product_data = self._extract_product_from_element(product_elem)
                    if product_data:
                        products_data.append(product_data)
                        self.stats['products_scraped'] += 1
                    else:
                        self.stats['skipped'] += 1
                except Exception as e:
                    self.stats['errors'] += 1
            
            return products_data
            
        except Exception as e:
            print(f"[!] Error on page {page_num}: {e}")
            self.stats['errors'] += 1
            return []
    
    def _scrape_category_page(self, url: str, page_num: int) -> List[Dict]:
        """
        Scrape a single category page with infinite scroll support.
        
        Args:
            url: Full URL to scrape
            page_num: Page number (for logging)
            
        Returns:
            List of product dictionaries
        """
        try:
            # Navigate to page
            self.page.goto(url, wait_until='domcontentloaded', timeout=30000)
            
            # Wait for initial products to load
            try:
                self.page.wait_for_selector('[class*="product"]', timeout=15000)
            except PlaywrightTimeout:
                print(f"[!] Timeout waiting for products on page {page_num}")
                return []
            
            # Implement infinite scroll - scroll multiple times to load all products
            previous_height = 0
            scroll_attempts = 0
            max_scrolls = 10
            
            while scroll_attempts < max_scrolls:
                # Scroll to bottom
                self.page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
                self.page.wait_for_timeout(2000)
                
                # Get new height
                new_height = self.page.evaluate('document.body.scrollHeight')
                
                # If height hasn't changed, we've reached the bottom
                if new_height == previous_height:
                    break
                
                previous_height = new_height
                scroll_attempts += 1
                print(f"    Scrolled {scroll_attempts} times, height: {new_height}")
            
            # Wait for network to be idle
            try:
                self.page.wait_for_load_state('networkidle', timeout=10000)
            except:
                pass
            
            # Additional wait
            self.page.wait_for_timeout(1000)
            
            # Find product elements
            product_selectors = [
                '[class*="product-card"]',
                '[class*="product-item"]',
                '[class*="product-tile"]',
                '[data-product]',
                'article[class*="product"]',
                'div[class*="product"]'
            ]
            
            products_data = []
            products = []
            
            for selector in product_selectors:
                products = self.page.query_selector_all(selector)
                if products and len(products) > 5:
                    print(f"[*] Found {len(products)} products using selector: {selector}")
                    break
            
            if not products:
                print(f"[!] No products found on page {page_num}")
                return []
            
            # Extract data from each product
            for i, product_elem in enumerate(products):
                try:
                    product_data = self._extract_product_from_element(product_elem)
                    if product_data:
                        products_data.append(product_data)
                        self.stats['products_scraped'] += 1
                    else:
                        self.stats['skipped'] += 1
                except Exception as e:
                    self.stats['errors'] += 1
            
            if products_data:
                print(f"[✓] Extracted {len(products_data)} products from page {page_num}")
                if products_data:
                    print(f"    First: {products_data[0]['name'][:50]}")
                    print(f"    Last: {products_data[-1]['name'][:50]}")
            else:
                print(f"[!] No valid products extracted from page {page_num}")
            
            return products_data
            
        except Exception as e:
            print(f"[!] Error scraping page {page_num}: {e}")
            self.stats['errors'] += 1
            return []
    
    def validate_product_data(self, product: Dict) -> Tuple[bool, Optional[str]]:
        """Validate product data."""
        if not product.get('name'):
            return False, "Missing product name"
        
        if not product.get('price') or product['price'] <= 0:
            return False, "Invalid price"
        
        if product['price'] > 10000:
            return False, f"Price too high: {product['price']}"
        
        if product.get('original_price'):
            if product['original_price'] < product['price']:
                return False, "Original price lower than current price"
        
        if product.get('offer_end_date'):
            if product['offer_end_date'] < datetime.now(timezone.utc):
                product['is_promotion'] = False
        
        return True, None
    
    def save_to_database(self, products: List[Dict], db_session) -> Dict:
        """Save products to database (same as original scraper)."""
        from models.postgres_models import (
            Product, ProductStore, Store, Promotion, Offer, PromotionTarget
        )
        
        print(f"\n{'='*80}")
        print("DATABASE INSERTION - Starting")
        print(f"{'='*80}\n")
        
        # Ensure SPAR store exists
        store = db_session.query(Store).filter_by(store_id='spar').first()
        if not store:
            print("[*] Creating SPAR store entry...")
            store = Store(
                store_id='spar',
                name='SPAR',
                website='https://www.spar.at',
                logo_url='https://www.spar.at/favicon.ico',
                country='AT',
                api_available=False,
                scraping_required=True,
                active=True
            )
            db_session.add(store)
            db_session.commit()
            print("[✓] SPAR store created")
        
        stats = {
            'processed': 0,
            'products_added': 0,
            'products_updated': 0,
            'product_stores_added': 0,
            'product_stores_updated': 0,
            'promotions_added': 0,
            'validation_errors': 0,
            'database_errors': 0
        }
        
        for product_data in products:
            try:
                stats['processed'] += 1
                
                # Validate
                is_valid, error_msg = self.validate_product_data(product_data)
                if not is_valid:
                    print(f"[!] Validation error: {error_msg}")
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
                    print(f"[+] New product: {product_data['name']}")
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
                
                # Handle promotions
                if product_data.get('is_promotion') and product_data.get('original_price'):
                    discount_value = product_data.get('discount_percentage', 0)
                    
                    offer = Offer(
                        name=f"SPAR {discount_value}% Rabatt",
                        description=product_data.get('promo_text', ''),
                        discount_type='percentage',
                        discount_value=Decimal(str(discount_value)),
                        is_active=True,
                        created_at=datetime.now(timezone.utc),
                        updated_at=datetime.now(timezone.utc)
                    )
                    db_session.add(offer)
                    db_session.flush()
                    
                    promotion = Promotion(
                        name=f"SPAR Aktion - {product_data['name'][:50]}",
                        description=product_data.get('promo_text', ''),
                        offer_id=offer.id,
                        start_date=datetime.now(timezone.utc).date(),
                        end_date=product_data['offer_end_date'].date() if product_data.get('offer_end_date') else None,
                        is_active=True,
                        created_at=datetime.now(timezone.utc)
                    )
                    db_session.add(promotion)
                    db_session.flush()
                    
                    promo_target = PromotionTarget(
                        promotion_id=promotion.id,
                        product_id=product.id,
                        store_id='spar',
                        created_at=datetime.now(timezone.utc)
                    )
                    db_session.add(promo_target)
                    stats['promotions_added'] += 1
                
                if stats['processed'] % 50 == 0:
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
    """Main execution function."""
    from app import app
    from models.postgres_models import db
    
    with app.app_context():
        scraper = SparPlaywrightScraper(headless=True)
        
        # Scrape products
        products = scraper.scrape_all_products(max_pages=None, delay=2.0)
        
        if products:
            print(f"\n[*] Scraped {len(products)} products. Saving to database...")
            db_stats = scraper.save_to_database(products, db.session)
            
            print(f"\n{'='*80}")
            print("DATABASE STATISTICS")
            print(f"{'='*80}")
            for key, value in db_stats.items():
                print(f"{key:25s}: {value}")
            print(f"{'='*80}\n")
        else:
            print("[!] No products scraped.")


if __name__ == "__main__":
    main()
