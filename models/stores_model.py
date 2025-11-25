"""Stores model — class-based MongoDB helper with fallback to Flask-PyMongo when available.
"""
from pymongo import MongoClient
from bson import ObjectId
import os
from dotenv import load_dotenv
from typing import List, Optional

load_dotenv()


class StoresModel:
    def __init__(self):
        mongo_uri = os.getenv('MONGO_URI', 'mongodb://localhost:27017/smart_grocery')
        database_name = os.getenv('DATABASE_NAME', None)

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
                try:
                    self.db = self._client.get_default_database()
                    if self.db is None:
                        self.db = self._client['smart_grocery']
                except Exception:
                    self.db = self._client['smart_grocery']

    def list_stores(self) -> List[dict]:
        docs = list(self.db.stores.find({}))
        for d in docs:
            if '_id' in d:
                d['id'] = str(d['_id'])
        return docs

    def get_store_by_name(self, name: str) -> Optional[dict]:
        if not name:
            return None
        doc = self.db.stores.find_one({'name': name})
        if not doc:
            return None
        if '_id' in doc:
            doc['id'] = str(doc['_id'])
        return doc

    def get_store_by_id(self, id_str: str) -> Optional[dict]:
        try:
            doc = self.db.stores.find_one({'_id': ObjectId(id_str)})
            if not doc:
                return None
            doc['id'] = str(doc['_id'])
            return doc
        except Exception:
            return None

    def insert_store(self, doc: dict) -> str:
        res = self.db.stores.insert_one(doc)
        return str(res.inserted_id)

    def update_store(self, id_str: str, update_doc: dict) -> bool:
        try:
            update_doc.pop('_id', None)
            res = self.db.stores.update_one({'_id': ObjectId(id_str)}, {'$set': update_doc})
            return getattr(res, 'modified_count', 0) > 0
        except Exception:
            return False

    def delete_store(self, id_str: str) -> bool:
        try:
            res = self.db.stores.delete_one({'_id': ObjectId(id_str)})
            return getattr(res, 'deleted_count', 0) > 0
        except Exception:
            return False

    def close_connection(self):
        if self._client:
            self._client.close()


stores_model = StoresModel()

def list_stores() -> List[dict]:
    return stores_model.list_stores()

def get_store_by_name(name: str) -> Optional[dict]:
    return stores_model.get_store_by_name(name)

def insert_store(doc: dict):
    return stores_model.insert_store(doc)
