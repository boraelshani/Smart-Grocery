"""
MODULE 6 - Periodic Update Pipeline
"""
import time
from datetime import datetime

class CronUpdatePipeline:
    def __init__(self, scrapers, db):
        self.scrapers = scrapers
        self.db = db

    def run(self):
        print("Starting Periodic Update Pipeline...")
        for scraper in self.scrapers:
            print(f"Running scraper for: {scraper.store_name}")
            new_products = scraper.scrape_all()
            
            for prod in new_products:
                self.normalize_and_match(prod)

    def normalize_and_match(self, new_prod):
        # 1. Normalize
        # norm_prod = create_unified_product(...)
        
        # 2. Extract Category (CategoryMapper)
        # 3. Fuzzy Match against DB (FuzzyMatcher)
        
        # 4. Update prices & log differences
        diffs = self._calculate_differences(new_prod)
        if diffs:
            print(f"Differences found for {new_prod.get('name')}: {diffs}")
            # self.db.update(...)
            # self._append_version_history(...)
            
    def _calculate_differences(self, product):
        # Return True if price/description changed
        return True 
