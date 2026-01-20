"""
═══════════════════════════════════════════════════════════════════════════
PRODUCTS MODEL - Database Operations for Products
═══════════════════════════════════════════════════════════════════════════
Purpose: Handle all product database queries and operations
Database Collection: 'products' in MongoDB
Functions:
- Get all products
- Get product by ID or name
- Search products
- Filter by store/category
- Update product information
Used by: main_routes, home page, compare page, product detail pages
═══════════════════════════════════════════════════════════════════════════
"""
from pymongo import MongoClient
from bson import ObjectId
import os
from dotenv import load_dotenv
from typing import List, Optional

load_dotenv()


class ProductsModel:
    # CONNECT TO MONGODB: Either use app's connection or create new one
    def __init__(self):
        mongo_uri = os.getenv('MONGO_URI') or 'mongodb://localhost:27017/smart_grocery'
        # guard against empty/whitespace values which trigger pymongo ConfigurationError
        if isinstance(mongo_uri, str) and not mongo_uri.strip():
            mongo_uri = 'mongodb://localhost:27017/smart_grocery'
        # sanitize common mistake: remove angle-brackets if user pasted URI with <...>
        if '<' in mongo_uri or '>' in mongo_uri:
            mongo_uri = mongo_uri.replace('<', '').replace('>', '')
            try:
                os.environ['MONGO_URI'] = mongo_uri
            except Exception:
                pass
        database_name = os.getenv('DATABASE_NAME', None)

        # Prefer Flask-PyMongo `mongo` if available to reuse the app connection
        try:
            from utils.db import mongo as flask_mongo
        except Exception:
            flask_mongo = None

        if flask_mongo is not None and getattr(flask_mongo, 'db', None) is not None:
            self.db = flask_mongo.db
            self._client = None
        else:
            try:
                import certifi
                self._client = MongoClient(mongo_uri, tlsCAFile=certifi.where())
            except (ImportError, TypeError):
                self._client = MongoClient(mongo_uri)
                
            if database_name:
                self.db = self._client[database_name]
            else:
                # If URI includes a database, use it; otherwise default
                try:
                    self.db = self._client.get_default_database()
                    if self.db is None:
                        self.db = self._client['smart_grocery']
                except Exception:
                    self.db = self._client['smart_grocery']

    def list_products(self, query: Optional[dict] = None, skip: int = 0, limit: int = 0) -> List[dict]:
        # GET ALL PRODUCTS from database
        cursor = self.db.products.find(query or {})
        if skip:
            cursor = cursor.skip(skip)
        if limit:
            cursor = cursor.limit(limit)
            
        docs = list(cursor)
        for d in docs:
            if '_id' in d:
                d['id'] = str(d['_id'])  # Convert MongoDB ID to string for frontend
        return docs

    def get_latest_products(self, limit: int = 10) -> List[dict]:
        """Get the latest products added to the database"""
        try:
            # Sort by _id descending (approximate creation time for ObjectId)
            cursor = self.db.products.find({}).sort('_id', -1).limit(limit)
            docs = list(cursor)
            for d in docs:
                if '_id' in d:
                    d['id'] = str(d['_id'])
            return docs
        except Exception as e:
            print(f"Error fetching latest products: {e}")
            return []

    def count_products(self, query: Optional[dict] = None) -> int:
        # COUNT PRODUCTS matching query
        return self.db.products.count_documents(query or {})

    def get_popular_products(self, limit: int = 12) -> List[dict]:
        # GET POPULAR PRODUCTS sorted by engagement metrics
        docs = list(self.db.products.find({}).sort([('view_count', -1), ('add_to_list_count', -1)]).limit(limit))
        for d in docs:
            if '_id' in d:
                d['id'] = str(d['_id'])
        return docs

    def get_category_counts(self) -> dict:
        # GET counts of products by category
        pipeline = [
            {"$match": {"category": {"$exists": True, "$ne": None}}},
            {"$group": {"_id": "$category", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}}
        ]
        results = list(self.db.products.aggregate(pipeline))
        return {r['_id']: r['count'] for r in results}

    def upsert_product(self, key: dict, set_doc: dict) -> dict:
        res = self.db.products.update_one(key, {'$set': set_doc}, upsert=True)
        return {
            'upserted_id': res.upserted_id,
            'modified_count': res.modified_count,
            'matched_count': res.matched_count
        }

    def search_by_name(self, query: str, limit: int = 50) -> List[dict]:
        import re
        regex = {'$regex': re.escape(query), '$options': 'i'}
        docs = list(self.db.products.find({'name': regex}).limit(limit))
        for d in docs:
            if '_id' in d:
                d['id'] = str(d['_id'])
        return docs

    def get_category_options(self) -> List[str]:
        from collections import Counter
        all_prods = list(self.db.products.find({}, {'category': 1}))
        cat_counts = Counter(p.get('category') for p in all_prods if p.get('category'))
        return sorted(cat_counts.keys(), key=lambda c: (-cat_counts[c], c.lower()))

    def get_categories(self) -> List[str]:
        return self.db.products.distinct('category')

    def get_product_by_name(self, name: str) -> Optional[dict]:
        import re
        doc = self.db.products.find_one({'name': {'$regex': '^' + re.escape(name) + '$', '$options': 'i'}})
        if not doc:
            doc = self.db.products.find_one({'name': {'$regex': re.escape(name), '$options': 'i'}})
        if doc and '_id' in doc:
            doc['id'] = str(doc['_id'])
        return doc

    def count_by_store(self, store_name: str) -> int:
        import re
        regex = {'$regex': re.escape(store_name), '$options': 'i'}
        return self.db.products.count_documents({
            '$or': [
                {'stores': {'$elemMatch': {'$or': [{'store': regex}, {'name': regex}]}}},
                {'store': regex}
            ]
        })

    def find_by_store(self, store_name: str) -> List[dict]:
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
        from bson import ObjectId
        try:
            doc = self.db.products.find_one({'_id': ObjectId(product_id)})
            if not doc:
                doc = self.db.products.find_one({'id': product_id})
            if doc and '_id' in doc:
                doc['id'] = str(doc['_id'])
            return doc
        except Exception:
            # Maybe it wasn't an ObjectId
            doc = self.db.products.find_one({'id': product_id})
            if doc and '_id' in doc:
                doc['id'] = str(doc['_id'])
            return doc

    def get_recommendations(self, shops: List[str], categories: List[str], target_total: int = 12) -> List[dict]:
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
            remaining = list(self.db.products.find({'_id': {'$nin': [ObjectId(sid) for sid in seen_ids if len(sid) == 24]}}).limit(target_total - len(recommended_products)))
            for p in remaining:
                p['id'] = str(p['_id'])
                recommended_products.append(p)
                
        return recommended_products

    def get_product_by_name(self, name: str) -> Optional[dict]:
        # SEARCH FOR PRODUCT by name (used for compare prices feature)
        if not name:
            return None
        doc = self.db.products.find_one({'name': name})
        if not doc:
            return None
        if '_id' in doc:
            doc['id'] = str(doc['_id'])
        return doc

    def get_product_by_id(self, id_str: str) -> Optional[dict]:
        # GET SINGLE PRODUCT by MongoDB ID (used for product detail pages)
        try:
            doc = self.db.products.find_one({'_id': ObjectId(id_str)})
            if not doc:
                return None
            doc['id'] = str(doc['_id'])
            return doc
        except Exception:
            return None

    def insert_product(self, doc: dict) -> str:
        # ADD NEW PRODUCT to database (admin only)
        res = self.db.products.insert_one(doc)
        return str(res.inserted_id)

    def update_product(self, id_str: str, update_doc: dict) -> bool:
        # MODIFY PRODUCT in database (admin only)
        try:
            update_doc.pop('_id', None)  # Never modify _id
            res = self.db.products.update_one({'_id': ObjectId(id_str)}, {'$set': update_doc})
            return getattr(res, 'modified_count', 0) > 0
        except Exception:
            return False

    def delete_product(self, id_str: str) -> bool:
        # REMOVE PRODUCT from database (admin only)
        try:
            res = self.db.products.delete_one({'_id': ObjectId(id_str)})
            return getattr(res, 'deleted_count', 0) > 0
        except Exception:
            return False

    def close_connection(self):
        if self._client:
            self._client.close()


# Module-level convenience instance (keeps compatibility with previous usage style)
products_model = ProductsModel()

def list_products() -> List[dict]:
    return products_model.list_products()

def get_product_by_name(name: str) -> Optional[dict]:
    return products_model.get_product_by_name(name)

def insert_product(doc: dict):
    return products_model.insert_product(doc)
