"""
═══════════════════════════════════════════════════════════════════════════
QUANTITY DISCOUNTS MODEL - Bulk & Special Pricing Logic
═══════════════════════════════════════════════════════════════════════════
Purpose: Manage complex pricing rules beyond simple unit prices.
Database Collection: 'quantity_discounts' in MongoDB

Core Concepts:
1. Tiered Discounts: "Buy X+ items to get Y% off".
2. Special Offers: "Second item half price", "Second item free", etc.

Algorithms:
- `calculate_price_with_quantity_tiers`: Finds the best applicable tier based on qty.
- `calculate_special_offer_price`: Mathematical logic for BOGO-style discounts.
═══════════════════════════════════════════════════════════════════════════
"""
from pymongo import MongoClient
from bson import ObjectId
import os
from dotenv import load_dotenv
from typing import List, Optional, Dict
from datetime import datetime
import certifi

load_dotenv()


# ═══════════════════════════════════════════════════════════════════════════
# CATEGORY: INITIALIZATION
# ═══════════════════════════════════════════════════════════════════════════

class QuantityDiscountsModel:
    def __init__(self):
        """
        Initialize Model.
        Note: We use a property for db access to ensure context is always fresh.
        """
        self._db = None

    @property
    def db(self):
        """Dynamic property to get database connection."""
        from utils.db import get_db
        return get_db()


    # ═══════════════════════════════════════════════════════════════════════════
    # CATEGORY: READ OPERATIONS
    # ═══════════════════════════════════════════════════════════════════════════

    def list_active_discounts(self) -> List[dict]:
        """Get all active discount rules, normalized for frontend display."""
        if self.db is None: 
            return []

        try:
            # Fetch active discounts
            docs = list(self.db.quantity_discounts.find({'active': True}))
            
            # Normalize and Decorate
            for d in docs:
                # 1. ID Normalization
                if '_id' in d:
                    d['id'] = str(d['_id'])
                
                # 2. Name Normalization (Templates expect 'name' or 'title')
                if 'product_name' in d and 'name' not in d:
                    d['name'] = d['product_name']
                    
                # 3. Price Normalization (Templates expect 'price')
                if 'base_price' in d and 'price' not in d:
                    d['price'] = d['base_price']
                
                # 4. Discount Label Generation
                # Create a readable label from the first tier (e.g., "30% off (Buy 2+)")
                tiers = d.get('discount_tiers', [])
                if tiers and len(tiers) > 0:
                    best_tier = tiers[0] # Assuming first is relevant or simplest
                    pct = best_tier.get('discount_percent', 0)
                    qty = best_tier.get('min_qty', 2)
                    d['discount_label'] = f"{pct}% off (Buy {qty}+)"
                    
                    # Set discount_percent for sort logic
                    d['discount_percent'] = pct
                    
            return docs
        except Exception as e:
            print(f"Error in list_active_discounts: {e}")
            return []

    def get_latest_discounts(self, limit: int = 3) -> List[dict]:
        """Get the most recently added active discounts."""
        if self.db is None: return []
        cursor = self.db.quantity_discounts.find({'active': True}).sort('_id', -1).limit(limit)
        docs = list(cursor)
        for d in docs:
            if '_id' in d:
                d['id'] = str(d['_id'])
        return docs

    def get_discount_by_id(self, discount_id: str) -> Optional[dict]:
        """Get specific discount rule by ID."""
        try:
            if self.db is None: return None
            doc = self.db.quantity_discounts.find_one({'_id': ObjectId(discount_id)})
            if doc and '_id' in doc:
                doc['id'] = str(doc['_id'])
            return doc
        except Exception:
            return None

    def get_discount_by_product(self, product_id: str) -> Optional[dict]:
        """Get discount rule associated with a specific product."""
        try:
            if self.db is None: return None
            doc = self.db.quantity_discounts.find_one({'product_id': ObjectId(product_id)})
            if doc and '_id' in doc:
                doc['id'] = str(doc['_id'])
            return doc
        except Exception:
            return None


    # ═══════════════════════════════════════════════════════════════════════════
    # CATEGORY: PRODUCT ENRICHMENT
    # ═══════════════════════════════════════════════════════════════════════════

    def attach_discounts_to_products(self, products: List[dict]):
        """
        Enrich a list of products with their quantity discount rules.
        """
        if not products:
            return

        # Fetch all active discounts once
        discounts = self.list_active_discounts()
        
        # Create Map: product_id (str) -> discount doc
        discount_map = {}
        for d in discounts:
             pid = str(d.get('product_id', ''))
             if pid:
                 discount_map[pid] = d

        # Iterate products and attach tiers if found in map
        for p in products:
             pid = str(p.get('id') or p.get('_id', ''))
             if pid in discount_map:
                 d = discount_map[pid]
                 p['discount_tiers'] = d.get('tiers', [])
                 # Also attach special offer type if present
                 if d.get('offer_type'):
                     p['special_offer_type'] = d.get('offer_type')


    # ═══════════════════════════════════════════════════════════════════════════
    # CATEGORY: PRICING LOGIC (MATH ALGORITHMS)
    # ═══════════════════════════════════════════════════════════════════════════

    def calculate_price_with_quantity_tiers(self, base_price: float, quantity: int, 
                                           discount_tiers: List[Dict]) -> Dict[str, any]:
        """
        Calculate price based on tiered volume discounts.
        
        Logic:
        - Tiers define ranges (min_qty to max_qty).
        - We find the single best applicable tier for the *entire* quantity usually, 
          or specific tiers if the rule allows mixing. 
        - This implementation looks for the specific range the total quantity falls into.
        
        Args:
            base_price: Regular unit price.
            quantity: Purchase count.
            discount_tiers: List of dicts [{'min_qty': 2, 'max_qty': 5, 'discount_percent': 10}, ...]
            
        Returns:
            Dict with financial breakdown.
        """
        if not discount_tiers or quantity < 1:
            return {
                'total_price': base_price * quantity,
                'effective_unit_price': base_price,
                'applied_tier': None,
                'savings': 0.0,
                'discount_percent': 0
            }
        
        # Find applicable tier based on quantity
        applied_tier = None
        discount_percent = 0
        
        # Iterate tiers to find the one that matches current quantity
        for tier in discount_tiers:
            min_qty = tier.get('min_qty', 0)
            max_qty = tier.get('max_qty')  # None means "and above"
            
            if quantity >= min_qty:
                if max_qty is None or quantity <= max_qty:
                    applied_tier = tier
                    discount_percent = tier.get('discount_percent', 0)
                    # We found the matching tier, safe to break assuming non-overlapping tiers
                    break
        
        # Calculate price based on potential discount
        if discount_percent > 0:
            effective_unit_price = base_price * (1 - discount_percent / 100)
            total_price = effective_unit_price * quantity
            regular_price = base_price * quantity
            savings = regular_price - total_price
        else:
            effective_unit_price = base_price
            total_price = base_price * quantity
            savings = 0.0
        
        return {
            'total_price': round(total_price, 2),
            'effective_unit_price': round(effective_unit_price, 2),
            'applied_tier': applied_tier,
            'savings': round(savings, 2),
            'discount_percent': discount_percent
        }

    def calculate_special_offer_price(self, base_price: float, quantity: int,
                                     offer_type: str) -> Dict[str, float]:
        """
        Calculate price for named special offer types (Future Implementation).
        Supported Types: BOGO, Second Half Price, etc.
        """
        # Placeholder for future logic logic expansion
        pass


# Initialize the singleton instance
quantity_discounts_model = QuantityDiscountsModel()
