"""
═══════════════════════════════════════════════════════════════════════════
PRODUCTS MODEL - Database Operations for Products
═══════════════════════════════════════════════════════════════════════════
Purpose: Handle all product database queries and operations
Database Collection: 'products' in MongoDB

Core Features:
- Product Search (Partial matching)
- Category Aggregation (Pipelines)
- Recommendation Engine (Recommends based on store/category)
- Pagination (skip/limit)
═══════════════════════════════════════════════════════════════════════════
"""
from pymongo import MongoClient
from bson import ObjectId
import os
from dotenv import load_dotenv
from typing import List, Optional

load_dotenv()


class ProductsModel:
    def __init__(self):
        """
        Initialize the ProductsModel using the shared database connection.
        
        Why 'get_db':
        We fetch the ephemeral database connection from a utility helper
        rather than maintaining a persistent static connection to ensure 
        thread safety in Flask.
        """
        # Use shared get_db to ensure we use the active Flask persistence connection
        from utils.db import get_db
        self.db = get_db()
        self._client = None


    def list_products(self, query: Optional[dict] = None, skip: int = 0, limit: int = 0) -> List[dict]:
        """
        Retrieve a filtered list of products.
        
        Features:
        - Query Filtering: Accepts MongoDB syntax filters (e.g. {'price': {'$lt': 5}})
        - Pagination: Supports skipping records and limiting result set size.
        - ID Normalization: Converts ugly '_id' ObjectIds to clean 'id' strings.
        
        Args:
            query: MongoDB filter dictionary (default: {} for all products)
            skip: Number of documents to skip (for paging)
            limit: Maximum documents to return (for paging)
        
        Returns:
            List[dict]: List of clean product dictionaries.
        """
        # 1. EXECUTE QUERY
        # Start the cursor, applying the filter criteria
        cursor = self.db.products.find(query or {})
        
        # 2. APPLY PAGINATION
        # Order matters! Skip first, then limit.
        if skip:
            cursor = cursor.skip(skip)
        if limit:
            cursor = cursor.limit(limit)
            
        # 3. FETCH AND CLEAN RESULTS
        # Iterate through the cursor to fetch actual documents from DB server
        docs = list(cursor)
        for d in docs:
            # Helper: Add friendly 'id' field
            if '_id' in d:
                d['id'] = str(d['_id'])  # Convert MongoDB ID to string for frontend compatibility
        return docs

    def get_latest_products(self, limit: int = 10) -> List[dict]:
        """
        Get the most recently added products.
        
        Technique:
        MongoDB ObjectIds contain a timestamp component in their first 4 bytes.
        Sorting by '_id' descending (-1) is a highly efficient way to get 
        "newest first" without needing a separate 'created_at' index.
        """
        try:
            # Sort by _id descending (-1), which approximates creation time for ObjectId
            cursor = self.db.products.find({}).sort('_id', -1).limit(limit)
            docs = list(cursor)
            # Normalize IDs
            for d in docs:
                if '_id' in d:
                    d['id'] = str(d['_id'])
            return docs
        except Exception as e:
            print(f"Error fetching latest products: {e}")
            return []

    def count_products(self, query: Optional[dict] = None) -> int:
        """
        Count total products matching a filter.
        Used primarily for calculating total pages in pagination logic.
        """
        # COUNT PRODUCTS matching query (Used for pagination metadata)
        return self.db.products.count_documents(query or {})

    def get_popular_products(self, limit: int = 12) -> List[dict]:
        """
        Get products sorted by popularity metrics (view_count and add_to_list_count).
        
        Sorting Logic:
        1. Primary Sort: 'view_count' (descending) - Most seen items
        2. Secondary Sort: 'add_to_list_count' (descending) - Most engaged items
        """
        # GET POPULAR PRODUCTS sorted by engagement metrics
        docs = list(self.db.products.find({}).sort([('view_count', -1), ('add_to_list_count', -1)]).limit(limit))
        for d in docs:
            if '_id' in d:
                d['id'] = str(d['_id'])
        return docs

    def get_category_counts(self) -> dict:
        """
        Calculate the number of products in each category using an aggregation pipeline.
        
        Why Aggregation:
        Instead of fetching all products to Python and counting them (slow, memory intensive),
        we ask the MongoDB server to do the math and just send us the totals.
        
        Aggregation Steps:
        1. $match: Filter out products with no category (clean data).
        2. $group: Group documents by their 'category' field.
           - _id: The unique category name.
           - count: Increment a counter by 1 for each doc in the group.
        3. $sort: Sort the results so the biggest categories appear first.
        
        Returns:
            dict: { "Dairy": 50, "Bakery": 30, ... }
        """
        pipeline = [
            {"$match": {"category": {"$exists": True, "$ne": None}}},
            {"$group": {"_id": "$category", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}}
        ]
        results = list(self.db.products.aggregate(pipeline))
        
        # Transform the raw list [{_id: 'Dairy', count: 50}, ...] 
        # into a simple dictionary {'Dairy': 50, ...} for easier Python usage.
        return {r['_id']: r['count'] for r in results}

    def upsert_product(self, key: dict, set_doc: dict) -> dict:
        """
        Insert or Update (Upsert) a product.
        
        Behavior:
        - If a document matching 'key' exists: Update it with 'set_doc'.
        - If NO document matches: Create a new one combining 'key' and 'set_doc'.
        
        Args:
            key: Filter to find the product (e.g. {'name': 'Milk, 1 Gallon'})
            set_doc: The fields to update/set.
        """
        res = self.db.products.update_one(key, {'$set': set_doc}, upsert=True)
        return {
            'upserted_id': res.upserted_id,
            'modified_count': res.modified_count,
            'matched_count': res.matched_count
        }

    def search_by_name(self, query: str, limit: int = 50) -> List[dict]:
        """
        Search products by name using case-insensitive partial match (regex).
        
        Performance Note: 
        Regex searches starting with a wildcard (like implicit .*query.*) 
        cannot efficiently use indexes and perform full Collection Scans.
        This is fine for small catalogs (<10k items) but requires Atlas Search for scale.
        """
        import re
        # re.escape ensures special characters in query (like + or *) don't break the regex
        # 'i' option makes it case-insensitive (A matches a)
        regex = {'$regex': re.escape(query), '$options': 'i'}
        
        docs = list(self.db.products.find({'name': regex}).limit(limit))
        for d in docs:
            if '_id' in d:
                d['id'] = str(d['_id'])
        return docs

    def get_category_options(self) -> List[str]:
        """Get unique categories sorted by frequency and name."""
        from collections import Counter
        all_prods = list(self.db.products.find({}, {'category': 1}))
        cat_counts = Counter(p.get('category') for p in all_prods if p.get('category'))
        # Sort first by count (desc), then by name (asc)
        return sorted(cat_counts.keys(), key=lambda c: (-cat_counts[c], c.lower()))

    def get_categories(self) -> List[str]:
        # Helper to get distinct category list directly from DB
        return self.db.products.distinct('category')

    def get_product_by_name(self, name: str) -> Optional[dict]:
        """Get a single product by exact name match (case-insensitive fallback)."""
        import re
        # Try exact case-insensitive match from start ^ to end $
        doc = self.db.products.find_one({'name': {'$regex': '^' + re.escape(name) + '$', '$options': 'i'}})
        if not doc:
            # Fallback to partial match if exact not found
            doc = self.db.products.find_one({'name': {'$regex': re.escape(name), '$options': 'i'}})
        if doc and '_id' in doc:
            doc['id'] = str(doc['_id'])
        return doc

    def count_by_store(self, store_name: str) -> int:
        """Count products available at a specific store."""
        import re
        regex = {'$regex': re.escape(store_name), '$options': 'i'}
        # Complex query: Check if store is in the 'stores' array OR is the main 'store' field
        return self.db.products.count_documents({
            '$or': [
                {'stores': {'$elemMatch': {'$or': [{'store': regex}, {'name': regex}]}}},
                {'store': regex}
            ]
        })

    def find_by_store(self, store_name: str) -> List[dict]:
        """List all products available at a specific store."""
        import re
        regex = {'$regex': re.escape(store_name), '$options': 'i'}
        docs = list(self.db.products.find({
            '$or': [
                {'stores': {'$elemMatch': {'$or': [{'store': regex}, {'name': regex}]}}},
                {'store': regex}
            ]
        }))
        for d in docs:
            if '_id' in d:
                d['id'] = str(d['_id'])
        return docs

    def get_product_by_id(self, product_id: str) -> Optional[dict]:
        """Get product by ID string. Handles conversion to ObjectId."""
        from bson import ObjectId
        try:
            doc = self.db.products.find_one({'_id': ObjectId(product_id)})
            if not doc:
                # Fallback: check if stored as simple string ID
                doc = self.db.products.find_one({'id': product_id})
            if doc and '_id' in doc:
                doc['id'] = str(doc['_id'])
            return doc
        except Exception:
            # Maybe it wasn't a valid ObjectId string, try as regular string field
            doc = self.db.products.find_one({'id': product_id})
            if doc and '_id' in doc:
                doc['id'] = str(doc['_id'])
            return doc

    def get_recommendations(self, shops: List[str], categories: List[str], target_total: int = 12) -> List[dict]:
        """
        Generate product recommendations for a user.
        
        Strategy:
        1. Find products from user's preferred shops.
        2. Find products from user's preferred categories.
        3. Fill remaining slots with random recent products.
        """
        import re
        recommended_products = []
        seen_ids = set()
        
        # 1. Try to find products from preferred shops
        for shop in shops:
            if len(recommended_products) >= target_total:
                break
            try:
                regex = {'$regex': re.escape(shop), '$options': 'i'}
                shop_products = list(self.db.products.find({
                    '$or': [
                        {'store': regex},
                        {'stores': {'$elemMatch': {'store': regex}}}
                    ]
                }).limit(3))
                
                for p in shop_products:
                    pid = str(p.get('_id'))
                    if pid not in seen_ids:
                        p['id'] = pid
                        recommended_products.append(p)
                        seen_ids.add(pid)
                        if len(recommended_products) >= target_total:
                            break
            except Exception:
                pass
        
        # 2. Then, get products from preferred categories
        for cat in categories:
            if len(recommended_products) >= target_total:
                break
            try:
                regex = {'$regex': re.escape(cat), '$options': 'i'}
                cat_products = list(self.db.products.find({'category': regex}).limit(3))
                
                for p in cat_products:
                    pid = str(p.get('_id'))
                    if pid not in seen_ids:
                        p['id'] = pid
                        recommended_products.append(p)
                        seen_ids.add(pid)
                        if len(recommended_products) >= target_total:
                            break
            except Exception:
                pass
        
        # 3. Fill with random/recent products if still not enough
        if len(recommended_products) < target_total:
            # $nin excludes already seen IDs
            remaining = list(self.db.products.find({'_id': {'$nin': [ObjectId(sid) for sid in seen_ids if len(sid) == 24]}}).limit(target_total - len(recommended_products)))
            for p in remaining:
                p['id'] = str(p['_id'])
                recommended_products.append(p)
                
        return recommended_products

    def insert_product(self, doc: dict) -> str:
        # ADD NEW PRODUCT to database (Usually Admin only)
        res = self.db.products.insert_one(doc)
        return str(res.inserted_id)

    def update_product(self, id_str: str, update_doc: dict) -> bool:
        # MODIFY PRODUCT in database (Admin only)
        try:
            update_doc.pop('_id', None)  # Never modify _id
            res = self.db.products.update_one({'_id': ObjectId(id_str)}, {'$set': update_doc})
            return getattr(res, 'modified_count', 0) > 0
        except Exception:
            return False

    def delete_product(self, id_str: str) -> bool:
        # REMOVE PRODUCT from database (Admin only)
        try:
            res = self.db.products.delete_one({'_id': ObjectId(id_str)})
            return getattr(res, 'deleted_count', 0) > 0
        except Exception:
            return False

    def close_connection(self):
        if self._client:
            self._client.close()


# Module-level convenience instance (Singleton Pattern)
products_model = ProductsModel()

# Wrapper functions for backward compatibility with older route code
def list_products() -> List[dict]:
    return products_model.list_products()

def get_product_by_name(name: str) -> Optional[dict]:
    return products_model.get_product_by_name(name)

def insert_product(doc: dict):
    return products_model.insert_product(doc)

