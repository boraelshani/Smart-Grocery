"""
═══════════════════════════════════════════════════════════════════════════
FEATURED DEALS MODEL - Promotional Offers & Special Sales
═══════════════════════════════════════════════════════════════════════════
Purpose: Handle all featured deals and promotional offers
Database Collection: 'featured_deals' in MongoDB

Deal Types:
- Multi-buy promotions (e.g., 2+1 free)
- Percentage discounts
- Limited-time offers

Key Functions:
- List active deals
- Create new deals (triggers user notifications)
- Track deal claims (user engagement)
═══════════════════════════════════════════════════════════════════════════
"""
from pymongo import MongoClient
from bson import ObjectId
import os
from dotenv import load_dotenv
from typing import List, Optional
import certifi

load_dotenv()

# ═══════════════════════════════════════════════════════════════════════════
# CATEGORY: INITIALIZATION
# ═══════════════════════════════════════════════════════════════════════════

class FeaturedDealsModel:
    def __init__(self):
        """
        Initialize Featured Deals Model.
        """
        # Database dependency injection
        # Fetches the shared database connection from utils.db
        from utils.db import get_db
        self.db = get_db()
        self.collection = self._collection()
        self._client = None # Placeholder for potential direct client if needed

    def _collection(self):
        if self.db is not None:
            try:
                if 'promotions' in self.db.list_collection_names():
                    return self.db.promotions
            except Exception:
                pass
        return self.db.featured_deals

    @staticmethod
    def _normalize_deal(doc: dict) -> dict:
        if not isinstance(doc, dict):
            return doc
        out = dict(doc)
        if '_id' in out:
            out['id'] = str(out['_id'])
        out['store'] = out.get('store') or out.get('storeName')
        out['source'] = out.get('source') or out.get('sourceCollection')
        out['title'] = out.get('title') or out.get('name')
        out['name'] = out.get('name') or out['title']
        out['price'] = out.get('price') or out.get('priceText')
        return out


    # ═══════════════════════════════════════════════════════════════════════════
    # CATEGORY: READ OPERATIONS (SINGLE ITEM)
    # ═══════════════════════════════════════════════════════════════════════════

    def get_deal_by_id(self, deal_id: str) -> Optional[dict]:
        """
        Retrieve a specific deal by its ID.
        Handles both ObjectId strings and potential legacy/manual string IDs.
        """
        from bson import ObjectId
        collection = self._collection()
        
        # 1. Try ObjectId Lookup
        try:
            # First attempt: Look up by standard MongoDB ObjectId
            # This is the most common case for real records
            doc = collection.find_one({'_id': ObjectId(deal_id)})
            
            # If found, format it and return
            if doc:
                return self._normalize_deal(doc)
        except Exception:
            # If deal_id is not a valid ObjectId format, ignore and proceed to fallback
            pass

        # 2. Fallback 1: Manual ID String
        # Look for 'id' string field (sometimes used in seeded JSON data)
        doc = collection.find_one({'id': deal_id})
        if doc:
            return self._normalize_deal(doc)

        # 3. Fallback 2: Title Match
        # Look for 'title' match (rare, but useful for slug-based URLs)
        doc = collection.find_one({'title': deal_id})
        if doc:
            return self._normalize_deal(doc)
            
        # Return None if nothing matched
        return None


    # ═══════════════════════════════════════════════════════════════════════════
    # CATEGORY: LIST OPERATIONS (COLLECTIONS)
    # ═══════════════════════════════════════════════════════════════════════════

    def list_featured_deals(self) -> List[dict]:
        """
        GET ALL DEALS: Return information on all featured sales.
        Used for the main 'Featured Deals' page.
        """
        # 1. Fetch all documents from 'featured_deals' collection
        docs = list(self._collection().find({'promotionType': 'featured_deal'}) if 'promotions' in self.db.list_collection_names() else self.db.featured_deals.find({}))
        
        # 2. Normalize Data
        return [self._normalize_deal(d) for d in docs]

    def get_deals_count(self) -> int:
        """
        Count total active deals.
        Used for the 'Total Savings Available' counter on the dashboard.
        """
        # Count all documents in the collection
        if 'promotions' in self.db.list_collection_names():
            return self.db.promotions.count_documents({'promotionType': 'featured_deal'})
        return self.db.featured_deals.count_documents({})

    def get_latest_deals(self, limit: int = 10) -> List[dict]:
        """
        Get the latest featured deals added to the database.
        Includes handling for 'created_at' if available, otherwise sorts by _id.
        """
        # 1. Sort by '_id' Descending (-1)
        # In MongoDB, implicit timestamp is built into the ObjectId, 
        # so sorting by _id gives us chronological order.
        if 'promotions' in self.db.list_collection_names():
            cursor = self.db.promotions.find({'promotionType': 'featured_deal'}).sort('_id', -1).limit(limit)
        else:
            cursor = self.db.featured_deals.find({}).sort('_id', -1).limit(limit)
        
        # 2. Convert cursor to list
        docs = list(cursor)
        
        # 3. Normalize IDs
        return [self._normalize_deal(d) for d in docs]


    # ═══════════════════════════════════════════════════════════════════════════
    # CATEGORY: SEARCH OPERATIONS
    # ═══════════════════════════════════════════════════════════════════════════

    def count_by_store(self, store_name: str) -> int:
        """Count deals available at a specific store."""
        import re
        # Create case-insensitive regex for the store name
        regex = {'$regex': re.escape(store_name), '$options': 'i'}
        
        # Count documents where 'store' matches OR 'source' matches
        collection = self._collection()
        if 'promotions' in self.db.list_collection_names():
            return collection.count_documents({
                'promotionType': 'featured_deal',
                '$or': [
                    {'store': regex},
                    {'storeName': regex},
                    {'source': regex},
                    {'sourceCollection': regex}
                ]
            })
        return collection.count_documents({
            '$or': [
                {'store': regex},
                {'storeName': regex},
                {'source': regex},
                {'sourceCollection': regex}
            ]
        })

    def find_by_store(self, store_name: str) -> List[dict]:
        """List deals from a specific store."""
        import re
        # Create case-insensitive regex
        regex = {'$regex': re.escape(store_name), '$options': 'i'}
        
        # Find all matching documents
        collection = self._collection()
        if 'promotions' in self.db.list_collection_names():
            docs = list(collection.find({
                'promotionType': 'featured_deal',
                '$or': [
                    {'store': regex},
                    {'storeName': regex},
                    {'source': regex},
                    {'sourceCollection': regex}
                ]
            }))
        else:
            docs = list(collection.find({
                '$or': [
                    {'store': regex},
                    {'storeName': regex},
                    {'source': regex},
                    {'sourceCollection': regex}
                ]
            }))
        
        # Normalize IDs
        return [self._normalize_deal(d) for d in docs]


# Initialize the singleton instance
featured_deals_model = FeaturedDealsModel()
