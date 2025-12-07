"""Products model — class-based MongoDB helper with in-memory fallback.
Matches the structure used in `users_model.py` and prefers the Flask `utils.db.mongo` when available.
"""
from pymongo import MongoClient
from bson import ObjectId
import os
from dotenv import load_dotenv
from typing import List, Optional

load_dotenv()


class ProductsModel:
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

    def list_products(self) -> List[dict]:
        docs = list(self.db.products.find({}))
        for d in docs:
            if '_id' in d:
                d['id'] = str(d['_id'])
        return docs

    def get_product_by_name(self, name: str) -> Optional[dict]:
        if not name:
            return None
        doc = self.db.products.find_one({'name': name})
        if not doc:
            return None
        if '_id' in doc:
            doc['id'] = str(doc['_id'])
        return doc

    def get_product_by_id(self, id_str: str) -> Optional[dict]:
        try:
            doc = self.db.products.find_one({'_id': ObjectId(id_str)})
            if not doc:
                return None
            doc['id'] = str(doc['_id'])
            return doc
        except Exception:
            return None

    def insert_product(self, doc: dict) -> str:
        res = self.db.products.insert_one(doc)
        return str(res.inserted_id)

    def update_product(self, id_str: str, update_doc: dict) -> bool:
        try:
            update_doc.pop('_id', None)
            res = self.db.products.update_one({'_id': ObjectId(id_str)}, {'$set': update_doc})
            return getattr(res, 'modified_count', 0) > 0
        except Exception:
            return False

    def delete_product(self, id_str: str) -> bool:
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
