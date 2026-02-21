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


# ═══════════════════════════════════════════════════════════════════════════
# CATEGORY: INITIALIZATION
# ═══════════════════════════════════════════════════════════════════════════

class ProductsModel:
    def __init__(self):
        """
        Initialize the ProductsModel using the shared database connection.
        
        Why 'get_db':
        We fetch the ephemeral database connection from a utility helper
        rather than maintaining a persistent static connection to ensure 
        thread safety in Flask and prevent connection timeouts.
        """
        # Use shared get_db to ensure we use the active Flask persistence connection
        from utils.db import get_db
        self.db = get_db()
        self._client = None # Placeholder


    # ═══════════════════════════════════════════════════════════════════════════
    # CATEGORY: LIST & FILTER OPERATIONS
    # ═══════════════════════════════════════════════════════════════════════════

    def list_products(self, query: Optional[dict] = None, skip: int = 0, limit: int = 0) -> List[dict]:
        """
        Retrieve a filtered list of products with pagination.
        
        Args:
            query: MongoDB filter dictionary (default: {} for all products)
            skip: Number of documents to skip (for paging)
            limit: Maximum documents to return (for paging)
        
        Returns:
            List[dict]: List of clean product dictionaries.
        """
        # 1. EXECUTE QUERY
        # Start the cursor based on the filter criteria (or empty if None)
        cursor = self.db.products.find(query or {})
        
        # 2. APPLY PAGINATION
        # Apply strict ordering: Sort (implicit _id) -> Skip -> Limit
        # Skip: Used to jump over previous pages of results
        if skip:
            cursor = cursor.skip(skip)
        
        # Limit: Restrict the size of the returned batch
        if limit:
            cursor = cursor.limit(limit)
            
        # 3. FETCH AND CLEAN RESULTS
        # Execute the cursor and load documents into memory list
        docs = list(cursor)
        for d in docs:
            # Helper: Add friendly 'id' field string for frontend use
            if '_id' in d:
                d['id'] = str(d['_id'])
                
        return docs

    def get_latest_products(self, limit: int = 10) -> List[dict]:
        """
        Get the most recently added products.
        
        Technique:
        MongoDB ObjectIds contain an embedded timestamp.
        Sorting by '_id' descending (-1) is a highly efficient way to get 
        "newest first" without needing a separate 'created_at' index field.
        """
        try:
            # Sort by _id descending (-1)
            cursor = self.db.products.find({}).sort('_id', -1).limit(limit)
            docs = list(cursor)
            
            # Normalize IDs
            for d in docs:
                if '_id' in d:
                    d['id'] = str(d['_id'])
            return docs
        except Exception as e:
            # Log error defensively
            print(f"Error fetching latest products: {e}")
            return []

    def count_products(self, query: Optional[dict] = None) -> int:
        """
        Count total products matching a filter.
        Used primarily for calculating total pages in pagination logic.
        """
        # Use count_documents for accurate count matching the query
        return self.db.products.count_documents(query or {})

    def get_popular_products(self, limit: int = 12) -> List[dict]:
        """
        Get products sorted by popularity metrics.
        
        Sorting Logic:
        1. Primary Sort: 'view_count' (descending) - Most seen items
        2. Secondary Sort: 'add_to_list_count' (descending) - Most engaged items
        """
        # Execute complex sort
        docs = list(self.db.products.find({})
                    .sort([('view_count', -1), ('add_to_list_count', -1)])
                    .limit(limit))
                    
        # Normalize IDs
        for d in docs:
            if '_id' in d:
                d['id'] = str(d['_id'])
        return docs


    # ═══════════════════════════════════════════════════════════════════════════
    # CATEGORY: AGGREGATION & ANALYTICS
    # ═══════════════════════════════════════════════════════════════════════════

    def get_category_counts(self) -> dict:
        """
        Calculate the number of products in each category using an aggregation pipeline.
        
        Why Aggregation:
        Instead of fetching all products to Python and counting them loop-by-loop (slow),
        we ask the MongoDB server to do the grouping and just send us the totals.
        """
        # 1. Define Pipeline
        pipeline = [
            # Stage 1: Filter out products with no category
            {"$match": {"category": {"$exists": True, "$ne": None}}},
            
            # Stage 2: Group by category name and count them
            {"$group": {"_id": "$category", "count": {"$sum": 1}}},
            
            # Stage 3: Sort by count descending (most popular categories first)
            {"$sort": {"count": -1}}
        ]
        
        # 2. Execute Aggregation
        results = list(self.db.products.aggregate(pipeline))
        
        # 3. Transform Data
        # Turn [{_id: 'Dairy', count: 50}, ...] into {'Dairy': 50, ...}
        return {r['_id']: r['count'] for r in results}

    def get_category_options(self) -> List[str]:
        """Get unique categories sorted by frequency and name."""
        from collections import Counter
        # Fetch just the category field to save bandwidth
        all_prods = list(self.db.products.find({}, {'category': 1}))
        
        # Count occurrences in Python
        cat_counts = Counter(p.get('category') for p in all_prods if p.get('category'))
        
        # Sort keys: First by Count (desc), then by Name (alpha)
        return sorted(cat_counts.keys(), key=lambda c: (-cat_counts[c], c.lower()))

    def get_categories(self) -> List[str]:
        """Helper to get distinct category list directly from DB (Primitive)."""
        # MongoDB distinct() command returns list of unique values for a field
        return self.db.products.distinct('category')


    # ═══════════════════════════════════════════════════════════════════════════
    # CATEGORY: WRITE OPERATIONS
    # ═══════════════════════════════════════════════════════════════════════════

    def upsert_product(self, key: dict, set_doc: dict) -> dict:
        """
        Insert or Update (Upsert) a product.
        
        Behavior:
        - If matching 'key' found: Update it with 'set_doc'.
        - If NO match found: Create new doc with 'key' + 'set_doc'.
        """
        # update_one with upsert=True is the standard "Save/Update" pattern
        res = self.db.products.update_one(key, {'$set': set_doc}, upsert=True)
        
        return {
            'upserted_id': res.upserted_id,
            'modified_count': res.modified_count,
            'matched_count': res.matched_count
        }


    # ═══════════════════════════════════════════════════════════════════════════
    # CATEGORY: SEARCH & SINGLE ITEM LOOKUP
    # ═══════════════════════════════════════════════════════════════════════════

    def search_by_name(self, query: str, limit: int = 50) -> List[dict]:
        """
        Search products by name using case-insensitive partial match (regex).
        """
        import re
        # re.escape sanitizes the input string so symbols like '+' don't crash the regex
        # 'i' option makes it case-insensitive (A == a)
        regex = {'$regex': re.escape(query), '$options': 'i'}
        
        # Limit results to prevent overwhelming the UI
        docs = list(self.db.products.find({'name': regex}).limit(limit))
        
        for d in docs:
            if '_id' in d:
                d['id'] = str(d['_id'])
        return docs

    def get_product_by_name(self, name: str) -> Optional[dict]:
        """Get a single product by exact name match (with case-insensitive fallback)."""
        import re
        
        # 1. Exact Match (Case-Insensitive)
        # ^...$ anchors ensure "Milk" doesn't match "Milky Way"
        doc = self.db.products.find_one({'name': {'$regex': '^' + re.escape(name) + '$', '$options': 'i'}})
        
        # 2. Loose Match Fallback
        # If exact match fails, find *anything* containing the name
        if not doc:
            doc = self.db.products.find_one({'name': {'$regex': re.escape(name), '$options': 'i'}})
        
        if doc and '_id' in doc:
            doc['id'] = str(doc['_id'])
        return doc

    def get_product_by_id(self, product_id: str) -> Optional[dict]:
        """Get product by ID string. Handles conversion to ObjectId."""
        from bson import ObjectId
        try:
            # Try finding with proper ObjectId
            doc = self.db.products.find_one({'_id': ObjectId(product_id)})
            
            # Fallback for manual IDs (unlikely in prod, possible in test)
            if not doc:
                doc = self.db.products.find_one({'id': product_id})
                
            if doc and '_id' in doc:
                doc['id'] = str(doc['_id'])
            return doc
        except Exception:
            # If ID format is invalid, last ditch try as string field
            doc = self.db.products.find_one({'id': product_id})
            if doc and '_id' in doc:
                doc['id'] = str(doc['_id'])
            return doc


    # ═══════════════════════════════════════════════════════════════════════════
    # CATEGORY: DEAL SPECIFIC SEARCHING
    # ═══════════════════════════════════════════════════════════════════════════

    def count_by_store(self, store_name: str) -> int:
        """Count products available at a specific store."""
        import re
        regex = {'$regex': re.escape(store_name), '$options': 'i'}
        
        # Complex Query:
        # Check if store matches the flat 'store' field
        # OR if it exists inside the nested 'stores' array
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

    def get_recommendations(self, shops: List[str], categories: List[str], target_total: int = 12) -> List[dict]:
        """
        Generate product recommendations for a user.
        
        Strategy:
        1. Fill first slots with products from user's preferred shops.
        2. Fill next slots with products from user's preferred categories.
        3. Fill remaining slots with trending/random products.
        """
        import re
        recommended_products = []
        seen_ids = set()
        
        # 1. SCOPE: SHOP PREFERENCES
        for shop in shops:
            if len(recommended_products) >= target_total:
                break
            try:
                regex = {'$regex': re.escape(shop), '$options': 'i'}
                # Find up to 3 products per shop
                shop_products = list(self.db.products.find({
                    '$or': [
                        {'store': regex},
                        {'stores': {'$elemMatch': {'store': regex}}}
                    ]
                }).limit(3))
                
                # Add unique items only
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
        
        # 2. SCOPE: CATEGORY PREFERENCES
        for cat in categories:
            if len(recommended_products) >= target_total:
                break
            try:
                # Find up to 3 products per category
                cat_products = list(self.db.products.find({'category': cat}).limit(3))
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
                
        # 3. SCOPE: BACKFILL (TRENDING)
        # If we still have empty slots, fill with popular items
        if len(recommended_products) < target_total:
            remaining = target_total - len(recommended_products)
            popular = self.get_popular_products(limit=remaining + 10) # Fetch extras to ensure uniqueness
            
            for p in popular:
                if len(recommended_products) >= target_total:
                    break
                pid = str(p.get('_id'))
                if pid not in seen_ids:
                    p['id'] = pid
                    recommended_products.append(p)
                    seen_ids.add(pid)
                    
        return recommended_products


# Initialize the singleton instance
products_model = ProductsModel()
