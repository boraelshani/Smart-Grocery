"""Featured deals model — class-based helper, consistent with other models."""
from pymongo import MongoClient
from bson import ObjectId
import os
from dotenv import load_dotenv
from typing import List, Optional

load_dotenv()


class FeaturedDealsModel:
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

    def list_featured_deals(self) -> List[dict]:
        docs = list(self.db.featured_deals.find({}))
        for d in docs:
            if '_id' in d:
                d['id'] = str(d['_id'])
        return docs

    def get_deal_by_title(self, title: str) -> Optional[dict]:
        if not title:
            return None
        doc = self.db.featured_deals.find_one({'title': title})
        if not doc:
            return None
        if '_id' in doc:
            doc['id'] = str(doc['_id'])
        return doc

    def get_deal_by_id(self, id_str: str) -> Optional[dict]:
        try:
            doc = self.db.featured_deals.find_one({'_id': ObjectId(id_str)})
            if not doc:
                return None
            doc['id'] = str(doc['_id'])
            return doc
        except Exception:
            return None

    def insert_deal(self, doc: dict) -> str:
        res = self.db.featured_deals.insert_one(doc)
        return str(res.inserted_id)

    def update_deal(self, id_str: str, update_doc: dict) -> bool:
        try:
            update_doc.pop('_id', None)
            res = self.db.featured_deals.update_one({'_id': ObjectId(id_str)}, {'$set': update_doc})
            return getattr(res, 'modified_count', 0) > 0
        except Exception:
            return False

    def delete_deal(self, id_str: str) -> bool:
        try:
            res = self.db.featured_deals.delete_one({'_id': ObjectId(id_str)})
            return getattr(res, 'deleted_count', 0) > 0
        except Exception:
            return False

    def close_connection(self):
        if self._client:
            self._client.close()


featured_deals_model = FeaturedDealsModel()

def list_featured_deals() -> List[dict]:
    return featured_deals_model.list_featured_deals()

def get_deal_by_title(title: str) -> Optional[dict]:
    return featured_deals_model.get_deal_by_title(title)

def insert_deal(doc: dict):
    return featured_deals_model.insert_deal(doc)
