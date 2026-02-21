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

# ═══════════════════════════════════════════════════════════════════════════
# CATEGORY: INITIALIZATION
# ═══════════════════════════════════════════════════════════════════════════

class MultibuyOffersModel:
    def __init__(self):
        """
        Initialize the MultibuyOffers Model.
        """
        # Database dependency injection
        from utils.db import get_db
        self.db = get_db()
        self._client = None


    # ═══════════════════════════════════════════════════════════════════════════
    # CATEGORY: READING & LOOKUP
    # ═══════════════════════════════════════════════════════════════════════════

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
        
        # Normalize IDs
        for d in docs:
            if '_id' in d:
                d['id'] = str(d['_id'])
        return docs

    def get_offers_count(self) -> int:
        """Count active offers for statistics."""
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
        
        # Check active status and expiration date
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


    # ═══════════════════════════════════════════════════════════════════════════
    # CATEGORY: PRODUCT ENRICHMENT (JOIN LOGIC)
    # ═══════════════════════════════════════════════════════════════════════════

    def attach_offers_to_products(self, products: List[dict]) -> List[dict]:
        """
        Enrich product objects with offer data.
        
        Optimization Strategy: "Bulk Logic"
        Instead of querying the DB 50 times for 50 products (N+1 problem),
        we fetch ALL active offers once, map them in memory, and then attach.
        """
        if not products:
            return products
            
        try:
            # 1. Fetch all active offers
            mb_offers = self.list_active_offers()
            
            # 2. Fetch all quantity discounts (Lazy load to avoid circular import)
            from models.quantity_discounts_model import quantity_discounts_model
            q_discounts = quantity_discounts_model.list_active_discounts()
            
            # 3. Create Lookup Maps for O(1) access speed
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
                
            # 4. Iterate products and attach matched offers
            for p in products:
                # Normalize keys for lookup
                pid = str(p.get('id') or p.get('_id') or '')
                pname = str(p.get('name') or '').lower().strip()
                
                # Check embedded data (if offer string is already in product doc)
                ox_raw = p.get('buy_quantity') or p.get('multibuy_buy') or ''
                oy_raw = p.get('free_quantity') or p.get('multibuy_free') or ''
                
                # Handle dictionary offer objects embedded in product
                if p.get('offer'):
                    offer_obj = p.get('offer') if isinstance(p.get('offer'), dict) else None
                    if offer_obj:
                        p['offer_type'] = offer_obj.get('type') or p.get('offer_type', '')
                        p['offer_x'] = offer_obj.get('x') or ox_raw
                        p['offer_y'] = offer_obj.get('y') or oy_raw
                
                # Normalize basic Multibuy fields
                if not p.get('offer_x'): p['offer_x'] = ox_raw
                if not p.get('offer_y'): p['offer_y'] = oy_raw
                if not p.get('offer_type') and p.get('offer_x') and p.get('offer_y'):
                    p['offer_type'] = 'buyXgetY'

                # Perform Lookup in our maps
                offer = None
                if not p.get('offer_x'):
                    if pid in mb_map_id:
                        offer = mb_map_id[pid]
                    elif pname in mb_map_name:
                        offer = mb_map_name[pname]

                # If offer found in maps, attach details to product
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
                
                # Generate a human-readable label if possible
                if p.get('offer_x') and p.get('offer_y') and not p.get('discount_label'):
                    p['discount_label'] = f"{p['offer_x']}+{p['offer_y']} FREE"

                # If no Multi-buy, check Quantity Discounts
                if not p.get('offer_type') and pid in qd_map:
                    qd = qd_map[pid]
                    p['offer'] = qd
                    p['offer_type'] = 'quantity_discount'
                    if not p.get('discount_label'):
                        p['discount_label'] = "VOLUME DEAL"
                    if qd.get('original_price'):
                        p['original_price'] = qd.get('original_price')
            
            return products
            
        except Exception as e:
            # Fallback: Return original products if enrichment crashes
            print(f"Error attaching offers: {e}")
            return products


# Initialize the singleton instance
multibuy_offers_model = MultibuyOffersModel()
