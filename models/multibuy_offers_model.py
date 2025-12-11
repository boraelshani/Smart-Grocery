"""
═══════════════════════════════════════════════════════════════════════════
MULTI-BUY OFFERS MODEL - 2+1, BOGO, Buy X Get Y Deals
═══════════════════════════════════════════════════════════════════════════
Purpose: Handle multi-buy promotional offers separately from featured deals
Database Collection: 'multibuy_offers' in MongoDB
Offer Types:
- 2+1 Free (Buy 2 Get 1 Free)
- BOGO (Buy One Get One Free)
- Buy X Get Y (e.g., Buy 3 Get 2 Free)
- Quantity discounts (e.g., 3 for $5)
Functions:
- Get all active multi-buy offers
- Get offers by product/store
- Calculate effective pricing
- Validate offer rules
Used by: shopping list, featured deals, product pages
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


class MultibuyOffersModel:
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

    def list_active_offers(self) -> List[dict]:
        """Get all active multi-buy offers"""
        now = datetime.utcnow()
        query = {
            'active': True,
            '$or': [
                {'valid_until': {'$exists': False}},
                {'valid_until': None},
                {'valid_until': {'$gte': now}}
            ]
        }
        docs = list(self.db.multibuy_offers.find(query))
        for d in docs:
            if '_id' in d:
                d['id'] = str(d['_id'])
        return docs

    def get_offer_by_id(self, offer_id: str) -> Optional[dict]:
        """Get specific offer by ID"""
        try:
            doc = self.db.multibuy_offers.find_one({'_id': ObjectId(offer_id)})
            if doc and '_id' in doc:
                doc['id'] = str(doc['_id'])
            return doc
        except Exception:
            return None

    def get_offers_by_product(self, product_id: str) -> List[dict]:
        """Get all active offers for a specific product"""
        now = datetime.utcnow()
        query = {
            'product_id': ObjectId(product_id),
            'active': True,
            '$or': [
                {'valid_until': {'$exists': False}},
                {'valid_until': None},
                {'valid_until': {'$gte': now}}
            ]
        }
        docs = list(self.db.multibuy_offers.find(query))
        for d in docs:
            if '_id' in d:
                d['id'] = str(d['_id'])
        return docs

    def get_offers_by_store(self, store_name: str) -> List[dict]:
        """Get all active offers for a specific store"""
        now = datetime.utcnow()
        query = {
            'store': store_name,
            'active': True,
            '$or': [
                {'valid_until': {'$exists': False}},
                {'valid_until': None},
                {'valid_until': {'$gte': now}}
            ]
        }
        docs = list(self.db.multibuy_offers.find(query))
        for d in docs:
            if '_id' in d:
                d['id'] = str(d['_id'])
        return docs

    def calculate_effective_price(self, unit_price: float, quantity: int, 
                                  buy_qty: int, free_qty: int) -> Dict[str, float]:
        """
        Calculate the effective price for a multi-buy offer
        
        Args:
            unit_price: Regular price per item
            quantity: Total quantity customer wants
            buy_qty: Number of items to buy in offer (X in "Buy X Get Y")
            free_qty: Number of free items in offer (Y in "Buy X Get Y")
        
        Returns:
            Dict with total_price, effective_unit_price, savings
        """
        if buy_qty <= 0 or free_qty < 0:
            return {
                'total_price': unit_price * quantity,
                'effective_unit_price': unit_price,
                'savings': 0.0
            }
        
        cycle = buy_qty + free_qty
        full_cycles = quantity // cycle
        remainder = quantity % cycle
        
        # Pay for buy_qty items per cycle, get free_qty free
        paid_items = full_cycles * buy_qty + min(remainder, buy_qty)
        total_price = paid_items * unit_price
        
        # Calculate savings
        regular_price = quantity * unit_price
        savings = regular_price - total_price
        effective_unit_price = total_price / quantity if quantity > 0 else unit_price
        
        return {
            'total_price': round(total_price, 2),
            'effective_unit_price': round(effective_unit_price, 2),
            'savings': round(savings, 2)
        }

    def create_offer(self, offer_data: dict) -> str:
        """Create a new multi-buy offer"""
        offer_data['created_at'] = datetime.utcnow()
        offer_data['active'] = offer_data.get('active', True)
        
        # Ensure product_id is ObjectId
        if 'product_id' in offer_data and isinstance(offer_data['product_id'], str):
            offer_data['product_id'] = ObjectId(offer_data['product_id'])
        
        result = self.db.multibuy_offers.insert_one(offer_data)
        return str(result.inserted_id)

    def update_offer(self, offer_id: str, update_data: dict) -> bool:
        """Update an existing offer"""
        try:
            update_data.pop('_id', None)
            update_data['updated_at'] = datetime.utcnow()
            
            result = self.db.multibuy_offers.update_one(
                {'_id': ObjectId(offer_id)},
                {'$set': update_data}
            )
            return result.modified_count > 0
        except Exception:
            return False

    def delete_offer(self, offer_id: str) -> bool:
        """Delete an offer (or mark as inactive)"""
        try:
            # Soft delete: mark as inactive
            result = self.db.multibuy_offers.update_one(
                {'_id': ObjectId(offer_id)},
                {'$set': {'active': False, 'deleted_at': datetime.utcnow()}}
            )
            return result.modified_count > 0
        except Exception:
            return False

    def close_connection(self):
        if self._client:
            self._client.close()


# Singleton instance
multibuy_offers_model = MultibuyOffersModel()

# Convenience functions
def list_active_offers() -> List[dict]:
    return multibuy_offers_model.list_active_offers()

def get_offer_by_id(offer_id: str) -> Optional[dict]:
    return multibuy_offers_model.get_offer_by_id(offer_id)

def get_offers_by_product(product_id: str) -> List[dict]:
    return multibuy_offers_model.get_offers_by_product(product_id)

def get_offers_by_store(store_name: str) -> List[dict]:
    return multibuy_offers_model.get_offers_by_store(store_name)

def calculate_multibuy_price(unit_price: float, quantity: int, 
                            buy_qty: int, free_qty: int) -> Dict[str, float]:
    return multibuy_offers_model.calculate_effective_price(
        unit_price, quantity, buy_qty, free_qty
    )

def create_multibuy_offer(offer_data: dict) -> str:
    return multibuy_offers_model.create_offer(offer_data)
