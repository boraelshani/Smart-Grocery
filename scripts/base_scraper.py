"""
MODULE 2, 4, 10 - Base Scraper Adapter & Image Pipeline
"""
import time
import random
import requests
import os

class BaseStoreScraper:
    def __init__(self, store_name):
        self.store_name = store_name
        self.session = requests.Session()
        # Add User Agents and Rate Limiting
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
        
    def log(self, step, message):
        """Module 10: Write logs for EVERY step"""
        print(f"[{self.store_name}] {step} - {message}")

    def fetch_with_retry(self, url, retries=3):
        for i in range(retries):
            try:
                self.log('FETCH', f'Requesting {url}')
                time.sleep(random.uniform(1.0, 3.0)) # Rate limiting
                resp = self.session.get(url, timeout=10)
                resp.raise_for_status()
                return resp
            except Exception as e:
                self.log('ERROR', f'Attempt {i+1} failed: {e}')
                time.sleep(5)
        return None

    def optimize_image(self, image_url):
         """Module 4: Image optimization pipeline block"""
         if not image_url: return None
         
         # Avoid small thumbnails by replacing patterns
         for thumb_pattern in ['small', 'thumb', 'mini', '150x150']:
             image_url = image_url.replace(thumb_pattern, 'large').replace('width=150', 'width=800')
         
         # Logic to download, compress, and move to S3/CDN would go here
         # For now, it returns the maximized URL
         return image_url

    def standardize_product(self, external_id, name, desc, cat_path, size, price, image_url):
        return {
          "store": self.store_name,
          "externalId": external_id,
          "name": name,
          "description": desc,
          "categoryPath": cat_path,
          "size": size,
          "price": price,
          "imageUrl": self.optimize_image(image_url),
        }

    def scrape_all(self):
        """Module 2: Implement pagination support for this store and scrape all"""
        page = 1
        all_products = []
        while True:
            self.log('PAGINATION', f'Scraping page {page}')
            # Pseudo-code adapter override
            products, has_next = self._scrape_page(page)
            all_products.extend(products)
            if not has_next:
                break
            page += 1
        return all_products
        
    def _scrape_page(self, page):
        raise NotImplementedError("Each adapter must implement this.")
