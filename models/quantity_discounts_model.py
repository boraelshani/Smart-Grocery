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


class QuantityDiscountsModel:
    def __init__(self):
        # Database dependency injection
        # Use simple init, resolve db at method time to ensure App Context
        self._db = None

    @property
    def db(self):
        from utils.db import get_db
        return get_db()

    def list_active_discounts(self) -> List[dict]:
        """Get all active discount rules, normalized for frontend display."""
        # Use self.db property which gets fresh db handle
        if self.db is None: 
            return []

        try:
            docs = list(self.db.quantity_discounts.find({'active': True}))
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
                    # Set discount_percent for sorting logic in routes
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

    def attach_discounts_to_products(self, products: List[dict]):
        """
        Enrich a list of products with their quantity discount rules.
        """
        if not products:
            return

        discounts = self.list_active_discounts()
        # Map product_id (str) -> discount doc
        discount_map = {}
        for d in discounts:
             pid = str(d.get('product_id', ''))
             if pid:
                 discount_map[pid] = d

        for p in products:
             pid = str(p.get('id') or p.get('_id', ''))
             if pid in discount_map:
                 d = discount_map[pid]
                 p['discount_tiers'] = d.get('tiers', [])
                 # Also attach special offer type if present
                 if d.get('offer_type'):
                     p['special_offer_type'] = d.get('offer_type')

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
        Calculate price for named special offer types.
        
        Supported Types:
        - 'second_half_off': Every 2nd item is 50% price.
        - 'second_free': Every 2nd item is free (equivalent to Buy 1 Get 1 Free).
        
        Args:
            base_price: Regular unit price.
            quantity: Total items.
            offer_type: The string identifier of the logic to apply.
        """
        if offer_type == 'second_half_off':
            # Logic: Buy 1 full, 2nd half. Pattern repeats every 2 items.
            # 5 items = (Pair, Pair, Remainder) = (Full+Half, Full+Half, Full)
            pairs = quantity // 2
            remainder = quantity % 2
            
            # Cost = (Pairs * 1.5 * Price) + (Remainder * Price)
            total = (pairs * (base_price + base_price * 0.5)) + (remainder * base_price)
            regular = base_price * quantity
            savings = regular - total
            effective = total / quantity if quantity > 0 else base_price
            
            return {
                'total_price': round(total, 2),
                'effective_unit_price': round(effective, 2),
                'savings': round(savings, 2)
            }
        
        elif offer_type == 'second_free':
            # Logic: Buy 1 full, 2nd free. 
            # Cost = (Pairs * 1.0 * Price) + (Remainder * Price)
            pairs = quantity // 2
            remainder = quantity % 2
            
            total = pairs * base_price + remainder * base_price
            regular = base_price * quantity
            savings = regular - total
            effective = total / quantity if quantity > 0 else base_price
            
            return {
                'total_price': round(total, 2),
                'effective_unit_price': round(effective, 2),
                'savings': round(savings, 2)
            }
        
        else:
            # Fallback for unknown types
            return {
                'total_price': base_price * quantity,
                'effective_unit_price': base_price,
                'savings': 0.0
            }

    def create_discount(self, discount_data: dict) -> str:
        """Create a new quantity discount entry."""
        discount_data['created_at'] = datetime.utcnow()
        discount_data['active'] = discount_data.get('active', True)
        
        if 'product_id' in discount_data and isinstance(discount_data['product_id'], str):
            discount_data['product_id'] = ObjectId(discount_data['product_id'])
        
        result = self.db.quantity_discounts.insert_one(discount_data)
        return str(result.inserted_id)

    def update_discount(self, discount_id: str, update_data: dict) -> bool:
        """Update a quantity discount rule."""
        try:
            update_data.pop('_id', None)
            update_data['updated_at'] = datetime.utcnow()
            
            result = self.db.quantity_discounts.update_one(
                {'_id': ObjectId(discount_id)},
                {'$set': update_data}
            )
            return result.modified_count > 0
        except Exception:
            return False

    def delete_discount(self, discount_id: str) -> bool:
        """Soft delete (deactivate) a discount."""
        try:
            result = self.db.quantity_discounts.update_one(
                {'_id': ObjectId(discount_id)},
                {'$set': {'active': False, 'deleted_at': datetime.utcnow()}}
            )
            return result.modified_count > 0
        except Exception:
            return False

    def close_connection(self):
        if self._client:
            self._client.close()


# Singleton instance
quantity_discounts_model = QuantityDiscountsModel()

# ════════════════════════════════════════════════════════════════════════════
# MODULE LEVEL CONVENIENCE FUNCTIONS
# ════════════════════════════════════════════════════════════════════════════
# wrappers to maintain compatibility with older code import styles

def list_active_discounts() -> List[dict]:
    return quantity_discounts_model.list_active_discounts()

def get_discount_by_id(discount_id: str) -> Optional[dict]:
    return quantity_discounts_model.get_discount_by_id(discount_id)

def get_discount_by_product(product_id: str) -> Optional[dict]:
    return quantity_discounts_model.get_discount_by_product(product_id)

def attach_discounts_to_products(products: List[dict]):
    return quantity_discounts_model.attach_discounts_to_products(products)

def calculate_price_with_tiers(base_price: float, quantity: int, 
                               discount_tiers: List[Dict]) -> Dict[str, any]:
    return quantity_discounts_model.calculate_price_with_quantity_tiers(
        base_price, quantity, discount_tiers
    )

def calculate_special_offer(base_price: float, quantity: int, 
                           offer_type: str) -> Dict[str, float]:
    return quantity_discounts_model.calculate_special_offer_price(
        base_price, quantity, offer_type
    )

def create_discount(discount_data: dict) -> str:
    return quantity_discounts_model.create_discount(discount_data)
