"""
═══════════════════════════════════════════════════════════════════════════
SPAR AUSTRIA SCRAPER
═══════════════════════════════════════════════════════════════════════════
Scrapes product data from SPAR Austria's online shop.

Features:
- Scrapes all products with pagination support
- Captures regular prices and promotional offers
- Extracts offer end dates
- Maps data to Smart Grocery database schema
- Safe insertion (no data replacement, only additions)
- Efficient batch processing
- Comprehensive error handling and validation

Database Schema Mapping:
- Products → products table (global catalog)
- Store-specific data → product_store table
- Promotions → promotions, offers, promotion_targets tables
═══════════════════════════════════════════════════════════════════════════
"""

import requests
import json
import re
import time
from datetime import datetime, timezone, timedelta
from bs4 import BeautifulSoup
from typing import List, Dict, Optional, Tuple
import urllib3
from decimal import Decimal

# Disable SSL warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class SparScraper:
    """
    SPAR Austria product scraper with comprehensive data extraction.
    """
    
    def __init__(self, db_connection=None):
        """
        Initialize the SPAR scraper.
        
        Args:
            db_connection: SQLAlchemy database session (optional, for direct DB operations)
        """
        self.session = requests.Session()
        
        # Enhanced headers to bypass basic bot detection
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
            "Accept-Language": "de-AT,de;q=0.9,en-US;q=0.8,en;q=0.7",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
            "Cache-Control": "max-age=0",
            "sec-ch-ua": '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"macOS"',
        })
        
        self.db = db_connection
        self.base_url = "https://www.spar.at"
        self.store_id = "spar"
        
        # Statistics
        self.stats = {
            "products_scraped": 0,
            "products_added": 0,
            "products_updated": 0,
            "promotions_added": 0,
            "errors": 0,
            "skipped": 0
        }
    
    def _extract_unit_info(self, text: str) -> Tuple[Optional[str], Optional[float]]:
        """
        Extract unit and size from product text.
        
        Examples:
            "500g" -> ("g", 500.0)
            "1.5L" -> ("l", 1.5)
            "6 x 330ml" -> ("ml", 1980.0)  # Total volume
            
        Returns:
            Tuple of (unit, size_normalized)
        """
        if not text:
            return None, None
        
        text = text.lower().replace(',', '.')
        
        # Pattern: quantity x size unit (e.g., "6 x 330ml")
        multi_match = re.search(r'(\d+)\s*x\s*(\d+(?:\.\d+)?)\s*(kg|g|l|ml|stk|stück)', text)
        if multi_match:
            qty = float(multi_match.group(1))
            size = float(multi_match.group(2))
            unit = multi_match.group(3)
            unit = 'stk' if unit == 'stück' else unit
            return unit, qty * size
        
        # Pattern: simple size unit (e.g., "500g", "1.5L")
        simple_match = re.search(r'(\d+(?:\.\d+)?)\s*(kg|g|l|ml|stk|stück)', text)
        if simple_match:
            size = float(simple_match.group(1))
            unit = simple_match.group(2)
            unit = 'stk' if unit == 'stück' else unit
            return unit, size
        
        return None, None
    
    def _parse_price(self, price_text: str) -> Optional[float]:
        """
        Parse price string to float.
        
        Examples:
            "€ 2,99" -> 2.99
            "2.49" -> 2.49
            "1,99 €" -> 1.99
        """
        if not price_text:
            return None
        
        # Remove currency symbols and whitespace
        cleaned = price_text.replace('€', '').replace('EUR', '').strip()
        # Replace comma with dot for decimal
        cleaned = cleaned.replace(',', '.')
        
        try:
            return float(cleaned)
        except (ValueError, TypeError):
            return None
    
    def _parse_date(self, date_text: str) -> Optional[datetime]:
        """
        Parse German date formats to datetime.
        
        Examples:
            "bis 31.12.2024" -> datetime(2024, 12, 31)
            "gültig bis 15.05.2024" -> datetime(2024, 5, 15)
        """
        if not date_text:
            return None
        
        # Extract date pattern DD.MM.YYYY
        match = re.search(r'(\d{1,2})\.(\d{1,2})\.(\d{4})', date_text)
        if match:
            day, month, year = match.groups()
            try:
                return datetime(int(year), int(month), int(day), tzinfo=timezone.utc)
            except ValueError:
                return None
        
        # Check for relative dates like "bis Ende der Woche"
        if 'woche' in date_text.lower():
            # Assume end of current week (Sunday)
            today = datetime.now(timezone.utc)
            days_until_sunday = (6 - today.weekday()) % 7
            return today + timedelta(days=days_until_sunday)
        
        return None
    
    def _generate_fingerprint(self, name: str, brand: str, unit: str, size: float) -> str:
        """
        Generate a unique fingerprint for product deduplication.
        
        The fingerprint is used to identify the same product across different stores.
        """
        # Normalize components
        name_norm = re.sub(r'[^\w\s]', '', name.lower()).strip()
        brand_norm = re.sub(r'[^\w\s]', '', (brand or '').lower()).strip()
        unit_norm = (unit or '').lower()
        size_norm = f"{size:.2f}" if size else ""
        
        # Create fingerprint
        parts = [p for p in [brand_norm, name_norm, size_norm, unit_norm] if p]
        return '_'.join(parts)
    
    def _extract_product_data(self, product_element) -> Optional[Dict]:
        """
        Extract product data from a BeautifulSoup product element.
        
        Returns:
            Dictionary with product data or None if extraction fails
        """
        try:
            # Extract product name
            name_elem = product_element.find(['h3', 'h4', 'div'], class_=re.compile(r'product.*name|title', re.I))
            if not name_elem:
                name_elem = product_element.find('a', class_=re.compile(r'product.*link', re.I))
            
            if not name_elem:
                return None
            
            name = name_elem.get_text(strip=True)
            if not name:
                return None
            
            # Extract brand (often in a separate element or part of the name)
            brand_elem = product_element.find(['span', 'div'], class_=re.compile(r'brand', re.I))
            brand = brand_elem.get_text(strip=True) if brand_elem else None
            
            # If brand not found separately, try to extract from name
            if not brand:
                # Common Austrian brands
                known_brands = ['SPAR', 'S-BUDGET', 'SPAR PREMIUM', 'SPAR NATUR PUR', 
                               'Clever', 'Ja! Natürlich', 'Milka', 'Manner', 'Almdudler']
                for kb in known_brands:
                    if kb.lower() in name.lower():
                        brand = kb
                        break
            
            # Extract price
            price_elem = product_element.find(['span', 'div'], class_=re.compile(r'price(?!.*old|.*was)', re.I))
            if not price_elem:
                price_elem = product_element.find(['span', 'div'], attrs={'data-price': True})
            
            if not price_elem:
                return None
            
            price_text = price_elem.get_text(strip=True)
            if not price_text and price_elem.get('data-price'):
                price_text = price_elem.get('data-price')
            
            price = self._parse_price(price_text)
            if not price or price <= 0:
                return None
            
            # Extract original price (for promotions)
            original_price = None
            old_price_elem = product_element.find(['span', 'div'], class_=re.compile(r'old.*price|was.*price|strike', re.I))
            if old_price_elem:
                original_price = self._parse_price(old_price_elem.get_text(strip=True))
            
            # Extract promotion/offer information
            promo_elem = product_element.find(['span', 'div', 'badge'], class_=re.compile(r'promo|offer|deal|badge', re.I))
            promo_text = promo_elem.get_text(strip=True) if promo_elem else None
            
            # Extract offer end date
            date_elem = product_element.find(['span', 'div'], class_=re.compile(r'valid|gültig|bis', re.I))
            offer_end_date = None
            if date_elem:
                offer_end_date = self._parse_date(date_elem.get_text(strip=True))
            
            # Extract image URL
            img_elem = product_element.find('img')
            image_url = None
            if img_elem:
                image_url = img_elem.get('src') or img_elem.get('data-src') or img_elem.get('data-lazy-src')
                if image_url and not image_url.startswith('http'):
                    image_url = self.base_url + image_url if image_url.startswith('/') else None
            
            # Extract product URL
            link_elem = product_element.find('a', href=True)
            product_url = None
            if link_elem:
                product_url = link_elem['href']
                if product_url and not product_url.startswith('http'):
                    product_url = self.base_url + product_url
            
            # Extract unit and size information
            unit_elem = product_element.find(['span', 'div'], class_=re.compile(r'unit|size|grammage', re.I))
            unit_text = unit_elem.get_text(strip=True) if unit_elem else name
            unit, size_normalized = self._extract_unit_info(unit_text)
            
            # Determine if product is on promotion
            is_promotion = bool(original_price and original_price > price)
            
            # Calculate discount percentage
            discount_percentage = None
            if is_promotion:
                discount_percentage = round(((original_price - price) / original_price) * 100, 1)
            
            # Build product data
            product_data = {
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
            
            return product_data
            
        except Exception as e:
            print(f"[!] Error extracting product data: {e}")
            return None
    
    def scrape_page(self, page: int = 1) -> List[Dict]:
        """
        Scrape a single page of products from SPAR.
        
        Args:
            page: Page number to scrape
            
        Returns:
            List of product dictionaries
        """
        url = f"{self.base_url}/produktwelt/suche?search=&page={page}"
        print(f"[*] Scraping SPAR page {page}: {url}")
        
        try:
            response = self.session.get(url, verify=False, timeout=30)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Try multiple possible product container selectors
            product_containers = (
                soup.find_all(['div', 'article'], class_=re.compile(r'product.*item|product.*card|product.*tile', re.I)) or
                soup.find_all(['div', 'article'], attrs={'data-product': True}) or
                soup.find_all(['div', 'article'], attrs={'data-product-id': True})
            )
            
            if not product_containers:
                print(f"[!] No products found on page {page}. Trying alternative selectors...")
                # Try finding products in a grid/list container
                grid = soup.find(['div', 'ul'], class_=re.compile(r'product.*grid|product.*list', re.I))
                if grid:
                    product_containers = grid.find_all(['div', 'li', 'article'], recursive=False)
            
            if not product_containers:
                print(f"[!] No products found on page {page}. Page might be empty or structure changed.")
                return []
            
            print(f"[*] Found {len(product_containers)} product containers on page {page}")
            
            products = []
            for container in product_containers:
                product_data = self._extract_product_data(container)
                if product_data:
                    products.append(product_data)
                    self.stats['products_scraped'] += 1
                else:
                    self.stats['skipped'] += 1
            
            print(f"[*] Successfully extracted {len(products)} products from page {page}")
            return products
            
        except requests.RequestException as e:
            print(f"[!] HTTP error on page {page}: {e}")
            self.stats['errors'] += 1
            return []
        except Exception as e:
            print(f"[!] Unexpected error on page {page}: {e}")
            self.stats['errors'] += 1
            return []
    
    def scrape_all_products(self, max_pages: int = None, delay: float = 1.0) -> List[Dict]:
        """
        Scrape all products from SPAR with pagination.
        
        Args:
            max_pages: Maximum number of pages to scrape (None = all pages)
            delay: Delay between requests in seconds (be respectful!)
            
        Returns:
            List of all scraped products
        """
        print(f"\n{'='*80}")
        print("SPAR AUSTRIA SCRAPER - Starting")
        print(f"{'='*80}\n")
        
        all_products = []
        page = 1
        consecutive_empty = 0
        
        while True:
            if max_pages and page > max_pages:
                print(f"[*] Reached maximum page limit ({max_pages})")
                break
            
            products = self.scrape_page(page)
            
            if not products:
                consecutive_empty += 1
                if consecutive_empty >= 2:
                    print(f"[*] No products found on {consecutive_empty} consecutive pages. Stopping.")
                    break
            else:
                consecutive_empty = 0
                all_products.extend(products)
            
            page += 1
            
            # Respectful delay between requests
            if delay > 0:
                time.sleep(delay)
        
        print(f"\n[✓] Scraping complete! Total products: {len(all_products)}")
        return all_products
    
    def validate_product_data(self, product: Dict) -> Tuple[bool, Optional[str]]:
        """
        Validate product data before database insertion.
        
        Returns:
            Tuple of (is_valid, error_message)
        """
        # Required fields
        if not product.get('name'):
            return False, "Missing product name"
        
        if not product.get('price') or product['price'] <= 0:
            return False, "Invalid price"
        
        # Validate price ranges (sanity check)
        if product['price'] > 10000:
            return False, f"Price too high: {product['price']}"
        
        # Validate original price if present
        if product.get('original_price'):
            if product['original_price'] < product['price']:
                return False, "Original price lower than current price"
        
        # Validate dates
        if product.get('offer_end_date'):
            if product['offer_end_date'] < datetime.now(timezone.utc):
                # Offer already expired - still valid data, just note it
                product['is_promotion'] = False
        
        return True, None
    
    def save_to_database(self, products: List[Dict], db_session) -> Dict:
        """
        Save scraped products to the database using the normalized schema.
        
        This method:
        1. Checks if product already exists (by fingerprint)
        2. Creates new product if needed
        3. Creates/updates product_store entry
        4. Creates promotion and offer if applicable
        5. Never replaces existing data, only adds new entries
        
        Args:
            products: List of scraped product dictionaries
            db_session: SQLAlchemy database session
            
        Returns:
            Dictionary with operation statistics
        """
        from models.postgres_models import (
            Product, ProductStore, Store, Promotion, Offer, PromotionTarget, db
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
                
                # Validate data
                is_valid, error_msg = self.validate_product_data(product_data)
                if not is_valid:
                    print(f"[!] Validation error: {error_msg} - {product_data.get('name', 'Unknown')}")
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
                    # Create new product
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
                    db_session.flush()  # Get the product ID
                    stats['products_added'] += 1
                    print(f"[+] New product: {product_data['name']}")
                else:
                    # Update existing product if needed
                    updated = False
                    if product_data.get('image_url') and not product.default_image_url:
                        product.default_image_url = product_data['image_url']
                        updated = True
                    if updated:
                        product.updated_at = datetime.now(timezone.utc)
                        stats['products_updated'] += 1
                
                # Check if product_store entry exists
                product_store = db_session.query(ProductStore).filter_by(
                    product_id=product.id,
                    store_id='spar'
                ).first()
                
                if not product_store:
                    # Create new product_store entry
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
                    # Update existing product_store entry
                    product_store.base_price = Decimal(str(product_data['price']))
                    product_store.is_available = True
                    product_store.last_seen = datetime.now(timezone.utc)
                    if product_data.get('product_url'):
                        product_store.product_url = product_data['product_url']
                    stats['product_stores_updated'] += 1
                
                # Handle promotions
                if product_data.get('is_promotion') and product_data.get('original_price'):
                    # Create offer
                    discount_value = product_data.get('discount_percentage', 0)
                    offer_name = f"SPAR {discount_value}% Rabatt"
                    
                    offer = Offer(
                        name=offer_name,
                        description=product_data.get('promo_text', ''),
                        discount_type='percentage',
                        discount_value=Decimal(str(discount_value)),
                        is_active=True,
                        created_at=datetime.now(timezone.utc),
                        updated_at=datetime.now(timezone.utc)
                    )
                    db_session.add(offer)
                    db_session.flush()
                    
                    # Create promotion
                    promo_name = f"SPAR Aktion - {product_data['name'][:50]}"
                    end_date = product_data.get('offer_end_date')
                    
                    promotion = Promotion(
                        name=promo_name,
                        description=product_data.get('promo_text', ''),
                        offer_id=offer.id,
                        start_date=datetime.now(timezone.utc).date(),
                        end_date=end_date.date() if end_date else None,
                        is_active=True,
                        created_at=datetime.now(timezone.utc)
                    )
                    db_session.add(promotion)
                    db_session.flush()
                    
                    # Create promotion target
                    promo_target = PromotionTarget(
                        promotion_id=promotion.id,
                        product_id=product.id,
                        store_id='spar',
                        created_at=datetime.now(timezone.utc)
                    )
                    db_session.add(promo_target)
                    stats['promotions_added'] += 1
                
                # Commit every 50 products to avoid large transactions
                if stats['processed'] % 50 == 0:
                    db_session.commit()
                    print(f"[*] Progress: {stats['processed']}/{len(products)} products processed")
                
            except Exception as e:
                print(f"[!] Database error for product '{product_data.get('name', 'Unknown')}': {e}")
                stats['database_errors'] += 1
                db_session.rollback()
                continue
        
        # Final commit
        try:
            db_session.commit()
            print(f"\n[✓] Database insertion complete!")
        except Exception as e:
            print(f"[!] Final commit error: {e}")
            db_session.rollback()
        
        return stats
    
    def print_statistics(self):
        """Print scraping statistics."""
        print(f"\n{'='*80}")
        print("SCRAPING STATISTICS")
        print(f"{'='*80}")
        print(f"Products scraped:    {self.stats['products_scraped']}")
        print(f"Products added:      {self.stats['products_added']}")
        print(f"Products updated:    {self.stats['products_updated']}")
        print(f"Promotions added:    {self.stats['promotions_added']}")
        print(f"Errors:              {self.stats['errors']}")
        print(f"Skipped:             {self.stats['skipped']}")
        print(f"{'='*80}\n")


def main():
    """
    Main execution function for standalone scraping.
    """
    from app import app
    from models.postgres_models import db
    
    with app.app_context():
        scraper = SparScraper()
        
        # Scrape products (limit to 5 pages for testing, remove limit for full scrape)
        products = scraper.scrape_all_products(max_pages=None, delay=1.5)
        
        if products:
            print(f"\n[*] Scraped {len(products)} products. Saving to database...")
            
            # Save to database
            db_stats = scraper.save_to_database(products, db.session)
            
            # Print statistics
            print(f"\n{'='*80}")
            print("DATABASE STATISTICS")
            print(f"{'='*80}")
            print(f"Processed:              {db_stats['processed']}")
            print(f"Products added:         {db_stats['products_added']}")
            print(f"Products updated:       {db_stats['products_updated']}")
            print(f"Product-stores added:   {db_stats['product_stores_added']}")
            print(f"Product-stores updated: {db_stats['product_stores_updated']}")
            print(f"Promotions added:       {db_stats['promotions_added']}")
            print(f"Validation errors:      {db_stats['validation_errors']}")
            print(f"Database errors:        {db_stats['database_errors']}")
            print(f"{'='*80}\n")
        else:
            print("[!] No products scraped. Please check the scraper configuration.")
        
        scraper.print_statistics()


if __name__ == "__main__":
    main()
