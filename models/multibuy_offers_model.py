"""
═══════════════════════════════════════════════════════════════════════════
MULTI-BUY OFFERS MODEL - Complex Discount Logic
═══════════════════════════════════════════════════════════════════════════
Purpose: Handle multi-buy promotional offers (e.g., "Buy X Get Y Free")
Database Collection: 'multibuy_offers' in MongoDB

Core Features:
- Offer validation (Active/Expired checks)
- Dynamic Price Calculation (Effective unit price)
- Product Enrichment (Attaching offer metadata to product objects)

Algorithms:
- `calculate_effective_price`: Mathematical model for BOGO, 3-for-2, etc.
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
        # Database dependency injection
        from utils.db import get_db
        self.db = get_db()
        # Internal client reference if needed
        self._client = None


    def list_active_offers(self) -> List[dict]:
        """
        Get all offers where 'active' is True AND 'valid_until' is future/null.
        
        Returns:
            List of active offer documents.
        """
        now = datetime.utcnow()
        # Query: Active flag is true AND (No expiration OR Expiration is in future)
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

    def get_offers_count(self) -> int:
        return self.db.multibuy_offers.count_documents({'active': True})

    def get_latest_offers(self, limit: int = 5) -> List[dict]:
        """Get the latest multibuy offers added to the database."""
        cursor = self.db.multibuy_offers.find({'active': True}).sort('_id', -1).limit(limit)
        docs = list(cursor)
        for d in docs:
            if '_id' in d:
                d['id'] = str(d['_id'])
        return docs

    def get_offer_by_id(self, offer_id: str) -> Optional[dict]:
        """Get specific offer by ID."""
        try:
            doc = self.db.multibuy_offers.find_one({'_id': ObjectId(offer_id)})
            if doc and '_id' in doc:
                doc['id'] = str(doc['_id'])
            return doc
        except Exception:
            return None

    def get_offers_by_product(self, product_id: str) -> List[dict]:
        """Get all active offers applicable to a specific product ID."""
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

    def attach_offers_to_products(self, products: List[dict]) -> List[dict]:
        """
        Enrich product objects with offer data.
        
        Why: Efficiency. Instead of querying the DB for each product in a loop (N+1 problem),
        we fetch all active offers once and map them in memory.
        
        Args:
            products: List of product dictionaries.
            
        Returns:
            The same list, but with 'offer', 'offer_type', 'discount_label' fields added.
        """
        if not products:
            return products
            
        try:
            # 1. Fetch all active offers
            mb_offers = self.list_active_offers()
            
            # 2. Fetch all quantity discounts (Lazy load to avoid circular import)
            from models.quantity_discounts_model import quantity_discounts_model
            q_discounts = quantity_discounts_model.list_active_discounts()
            
            # 3. Create Lookup Maps for O(1) access
            # Map by ID
            mb_map_id = {}
            # Map by Name (fallback)
            mb_map_name = {}
            
            for o in mb_offers:
                pid = str(o.get('product_id'))
                if pid: mb_map_id[pid] = o
                
                pname = o.get('product_name')
                if pname: mb_map_name[pname.lower().strip()] = o
                
            qd_map = {}
            for q in q_discounts:
                pid = str(q.get('product_id'))
                if pid: qd_map[pid] = q
                
            # 4. Iterate products and attach data
            for p in products:
                pid = str(p.get('id') or p.get('_id') or '')
                pname = str(p.get('name') or '').lower().strip()
                
                # ... [Existing Logic Preserved for Compatibility] ...
                ox_raw = p.get('buy_quantity') or p.get('multibuy_buy') or ''
                oy_raw = p.get('free_quantity') or p.get('multibuy_free') or ''
                
                if p.get('offer'):
                    offer_obj = p.get('offer') if isinstance(p.get('offer'), dict) else None
                    if offer_obj:
                        p['offer_type'] = offer_obj.get('type') or p.get('offer_type', '')
                        p['offer_x'] = offer_obj.get('x') or ox_raw
                        p['offer_y'] = offer_obj.get('y') or oy_raw
                
                if not p.get('offer_x'): p['offer_x'] = ox_raw
                if not p.get('offer_y'): p['offer_y'] = oy_raw
                if not p.get('offer_type') and p.get('offer_x') and p.get('offer_y'):
                    p['offer_type'] = 'buyXgetY'

                # Look in lookup maps
                offer = None
                if not p.get('offer_x'):
                    if pid in mb_map_id:
                        offer = mb_map_id[pid]
                    elif pname in mb_map_name:
                        offer = mb_map_name[pname]

                if offer:
                    if not offer.get('type'):
                        offer['type'] = 'buyXgetY'
                        
                    if 'offer' not in p: p['offer'] = offer
                    p['offer_type'] = offer.get('type')
                    ox = offer.get('x') or offer.get('buy_quantity') or offer.get('multibuy_buy') or 0
                    oy = offer.get('y') or offer.get('free_quantity') or offer.get('multibuy_free') or 0
                    p['offer_x'] = ox
                    p['offer_y'] = oy
                    
                    if offer.get('original_price'):
                        p['original_price'] = offer.get('original_price')
                    elif offer.get('price'): 
                        p['original_price'] = offer.get('price')

                    p['buy_quantity'] = ox
                    p['free_quantity'] = oy
                
                if p.get('offer_x') and p.get('offer_y') and not p.get('discount_label'):
                    p['discount_label'] = f"{p['offer_x']}+{p['offer_y']} FREE"

                # Check Quantity Discounts if no multibuy found
                if not p.get('offer_type') and pid in qd_map:
                    qd = qd_map[pid]
                    p['offer'] = qd
                    p['offer_type'] = 'quantity_discount'
                    if not p.get('discount_label'):
                        p['discount_label'] = "VOLUME DEAL"
                    if qd.get('original_price'):
                        p['original_price'] = qd.get('original_price')
                    
        except Exception as e:
            print(f"Error attaching offers to products: {e}")
            
        return products

    def get_offers_by_store(self, store_name: str) -> List[dict]:
        """Get all active offers for a specific store."""
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
        Calculate the effective price for a "Buy X Get Y Free" offer.
        
        Logic:
        1. Calculate cycle size (Buy X + Get Y = Cycle Size).
        2. Determine how many full cycles fit in the desired quantity.
        3. Calculate remainder items.
        4. Determine how many items are actually paid for vs free.
        
        Args:
            unit_price: Regular price per item.
            quantity: Total quantity customer wants to buy.
            buy_qty: Number of items to pay for in a cycle (X).
            free_qty: Number of free items in a cycle (Y).
        
        Returns:
            Dict: {'total_price', 'effective_unit_price', 'savings'}
        """
        if buy_qty <= 0 or free_qty < 0:
            # Fallback for invalid offer data
            return {
                'total_price': unit_price * quantity,
                'effective_unit_price': unit_price,
                'savings': 0.0
            }
        
        cycle = buy_qty + free_qty
        full_cycles = quantity // cycle
        remainder = quantity % cycle
        
        # Items paid for = (Cycles * Pay items) + (Remainder items capped at Pay items)
        # e.g., Buy 2 Get 1 Free (Cycle 3).
        # Buy 4: 1 Cycle (3 items, pay 2) + Remainder 1 (pay 1) = Pay 3.
        paid_items = full_cycles * buy_qty + min(remainder, buy_qty)
        total_price = paid_items * unit_price
        
        # Savings
        regular_price = quantity * unit_price
        savings = regular_price - total_price
        effective_unit_price = total_price / quantity if quantity > 0 else unit_price
        
        return {
            'total_price': round(total_price, 2),
            'effective_unit_price': round(effective_unit_price, 2),
            'savings': round(savings, 2)
        }

    def create_offer(self, offer_data: dict) -> str:
        """Create a new multi-buy offer (Admin)."""
        offer_data['created_at'] = datetime.utcnow()
        offer_data['active'] = offer_data.get('active', True)
        
        if 'product_id' in offer_data and isinstance(offer_data['product_id'], str):
            offer_data['product_id'] = ObjectId(offer_data['product_id'])
        
        result = self.db.multibuy_offers.insert_one(offer_data)
        return str(result.inserted_id)

    def update_offer(self, offer_id: str, update_data: dict) -> bool:
        """Update an existing offer (Admin)."""
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
        """
        Soft delete an offer.
        We prefer setting 'active': False over physical deletion to preserve history.
        """
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

def get_offers_count() -> int:
    return multibuy_offers_model.get_offers_count()

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
