"""
═══════════════════════════════════════════════════════════════════════════
QUANTITY DISCOUNTS MODEL - Bulk Buy Discounts & Tier-Based Pricing
═══════════════════════════════════════════════════════════════════════════
Purpose: Handle tier-based quantity discounts (e.g., "Buy 2+ get 30% off")
Database Collection: 'quantity_discounts' in MongoDB
Examples:
- Buy 2+ → 15% off all items
- Buy 5+ → 25% off all items  
- Buy 10+ → 30% off all items
- Second item 50% off (special case)
Functions:
- Get discount for specific quantity
- Calculate effective price with quantity tiers
- List all quantity discount products
Used by: shopping list, product pages, bulk buying
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
        mongo_uri = os.getenv('MONGO_URI') or 'mongodb://localhost:27017/smart_grocery'
        if '<' in mongo_uri or '>' in mongo_uri:
            mongo_uri = mongo_uri.replace('<', '').replace('>', '')
        database_name = os.getenv('DATABASE_NAME', None)
        
        try:
            from utils.db import mongo as flask_mongo
        except Exception:
            flask_mongo = None

        if flask_mongo is not None and getattr(flask_mongo, 'db', None) is not None:
            self.db = flask_mongo.db
            self._client = None
        else:
            try:
                self._client = MongoClient(mongo_uri, tlsCAFile=certifi.where())
            except TypeError:
                self._client = MongoClient(mongo_uri)
            if database_name:
                self.db = self._client[database_name]
            else:
                try:
                    self.db = self._client.get_default_database()
                    if self.db is None:
                        self.db = self._client['smart_grocery']
                except Exception:
                    self.db = self._client['smart_grocery']

    def list_active_discounts(self) -> List[dict]:
        """Get all active quantity discount products"""
        docs = list(self.db.quantity_discounts.find({'active': True}))
        for d in docs:
            if '_id' in d:
                d['id'] = str(d['_id'])
        return docs

    def get_discount_by_product(self, product_id: str) -> Optional[dict]:
        """Get quantity discount config for a product"""
        try:
            doc = self.db.quantity_discounts.find_one({'product_id': ObjectId(product_id)})
            if doc and '_id' in doc:
                doc['id'] = str(doc['_id'])
            return doc
        except Exception:
            return None

    def calculate_price_with_quantity_tiers(self, base_price: float, quantity: int, 
                                           discount_tiers: List[Dict]) -> Dict[str, any]:
        """
        Calculate price with quantity tier discounts
        
        Args:
            base_price: Regular unit price
            quantity: Total quantity
            discount_tiers: List of tier objects with min_qty, max_qty, discount_percent
        
        Returns:
            Dict with total_price, effective_unit_price, applied_tier, savings
        
        Example discount_tiers:
        [
            {'min_qty': 2, 'max_qty': 4, 'discount_percent': 15},
            {'min_qty': 5, 'max_qty': 9, 'discount_percent': 25},
            {'min_qty': 10, 'discount_percent': 30}
        ]
        """
        if not discount_tiers or quantity < 1:
            return {
                'total_price': base_price * quantity,
                'effective_unit_price': base_price,
                'applied_tier': None,
                'savings': 0.0
            }
        
        # Find applicable tier based on quantity
        applied_tier = None
        discount_percent = 0
        
        for tier in discount_tiers:
            min_qty = tier.get('min_qty', 0)
            max_qty = tier.get('max_qty')  # None means "and above"
            
            if quantity >= min_qty:
                if max_qty is None or quantity <= max_qty:
                    applied_tier = tier
                    discount_percent = tier.get('discount_percent', 0)
        
        # Calculate price
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
        Calculate price for special offer types
        
        Args:
            base_price: Regular unit price
            quantity: Total quantity
            offer_type: 'second_half_off' (2nd item 50% off), 'second_free' (2nd free), etc.
        
        Returns:
            Dict with total_price, effective_unit_price, savings
        """
        if offer_type == 'second_half_off':
            # Buy 1 at full price, 2nd at 50% off, repeat
            # 1 item: full price
            # 2 items: full + half
            # 3 items: full + half + full
            # 4 items: full + half + full + half
            pairs = quantity // 2
            remainder = quantity % 2
            
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
            # Buy 1, get 2nd free (pairs only)
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
            # Unknown type, return regular price
            return {
                'total_price': base_price * quantity,
                'effective_unit_price': base_price,
                'savings': 0.0
            }

    def create_discount(self, discount_data: dict) -> str:
        """Create a new quantity discount entry"""
        discount_data['created_at'] = datetime.utcnow()
        discount_data['active'] = discount_data.get('active', True)
        
        if 'product_id' in discount_data and isinstance(discount_data['product_id'], str):
            discount_data['product_id'] = ObjectId(discount_data['product_id'])
        
        result = self.db.quantity_discounts.insert_one(discount_data)
        return str(result.inserted_id)

    def update_discount(self, discount_id: str, update_data: dict) -> bool:
        """Update a quantity discount"""
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
        """Delete or deactivate a discount"""
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

# Convenience functions
def list_active_discounts() -> List[dict]:
    return quantity_discounts_model.list_active_discounts()

def get_discount_by_product(product_id: str) -> Optional[dict]:
    return quantity_discounts_model.get_discount_by_product(product_id)

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
