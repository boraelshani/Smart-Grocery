"""
═══════════════════════════════════════════════════════════════════════════
FEATURED DEALS MODEL - Promotional Offers & Special Sales
═══════════════════════════════════════════════════════════════════════════
Purpose: Handle all featured deals and promotional offers
Database Collection: 'featured_deals' in MongoDB
Deal Types:
- Multi-buy promotions (e.g., 2+1 free, buy 3 get 50% off)
- Percentage discounts
- Limited-time offers
Functions:
- Get all active deals
- Get deals by store
- Get deals by product
- Claim deals to add to shopping list
Used by: featured deals page, main dashboard, shopping list
═══════════════════════════════════════════════════════════════════════════
"""
from pymongo import MongoClient
from bson import ObjectId
import os
from dotenv import load_dotenv
from typing import List, Optional
import certifi

load_dotenv()


class FeaturedDealsModel:
    # CONNECT TO MONGODB: Use Flask connection or create new one
    def __init__(self):
        mongo_uri = os.getenv('MONGO_URI') or 'mongodb://localhost:27017/smart_grocery'
        # sanitize common mistake: remove angle-brackets if user pasted URI with <...>
        if '<' in mongo_uri or '>' in mongo_uri:
            mongo_uri = mongo_uri.replace('<', '').replace('>', '')
            try:
                os.environ['MONGO_URI'] = mongo_uri
            except Exception:
                pass
        database_name = os.getenv('DATABASE_NAME', None)
        try:
            from utils.db import mongo as flask_mongo
        except Exception:
            flask_mongo = None

        if flask_mongo is not None and getattr(flask_mongo, 'db', None) is not None:
            self.db = flask_mongo.db
            self._client = None
        else:
            # use certifi CA bundle for TLS connections
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

    def get_deal_by_id(self, deal_id: str) -> Optional[dict]:
        from bson import ObjectId
        try:
            doc = self.db.featured_deals.find_one({'_id': ObjectId(deal_id)})
            if doc and '_id' in doc:
                doc['id'] = str(doc['_id'])
            return doc
        except Exception:
            # Fallback to searching by id field if it's a string
            doc = self.db.featured_deals.find_one({'id': deal_id})
            if not doc:
                doc = self.db.featured_deals.find_one({'title': deal_id})
            if doc and '_id' in doc:
                doc['id'] = str(doc['_id'])
            return doc

    def list_featured_deals(self) -> List[dict]:
        # GET ALL DEALS: Return all featured sales
        docs = list(self.db.featured_deals.find({}))
        for d in docs:
            if '_id' in d:
                d['id'] = str(d['_id'])  # Convert MongoDB ID to string
        return docs

    def get_deals_count(self) -> int:
        return self.db.featured_deals.count_documents({})

    def get_latest_deals(self, limit: int = 10) -> List[dict]:
        """
        Get the latest featured deals added to the database.
        Includes handling for 'created_at' if available, otherwise sorts by _id.
        """
        cursor = self.db.featured_deals.find({}).sort('_id', -1).limit(limit)
        docs = list(cursor)
        for d in docs:
            if '_id' in d:
                d['id'] = str(d['_id'])
        return docs

    def count_by_store(self, store_name: str) -> int:
        import re
        regex = {'$regex': re.escape(store_name), '$options': 'i'}
        return self.db.featured_deals.count_documents({
            '$or': [
                {'store': regex},
                {'source': regex}
            ]
        })

    def find_by_store(self, store_name: str) -> List[dict]:
        import re
        regex = {'$regex': re.escape(store_name), '$options': 'i'}
        docs = list(self.db.featured_deals.find({
            '$or': [
                {'store': regex},
                {'source': regex}
            ]
        }))
        for d in docs:
            if '_id' in d:
                d['id'] = str(d['_id'])
        return docs

    def get_deal_by_title(self, title: str) -> Optional[dict]:
        # SEARCH DEAL by title
        if not title:
            return None
        doc = self.db.featured_deals.find_one({'title': title})
        if not doc:
            return None
        if '_id' in doc:
            doc['id'] = str(doc['_id'])
        return doc

    def get_deal_by_id(self, id_str: str) -> Optional[dict]:
        # GET SINGLE DEAL by MongoDB ID (used for deal detail page)
        try:
            doc = self.db.featured_deals.find_one({'_id': ObjectId(id_str)})
            if not doc:
                return None
            doc['id'] = str(doc['_id'])
            return doc
        except Exception:
            return None

    def insert_deal(self, doc: dict) -> str:
        # ADD NEW DEAL to database (admin only)
        if 'created_at' not in doc:
            from datetime import datetime
            doc['created_at'] = datetime.utcnow()
        res = self.db.featured_deals.insert_one(doc)
        deal_id = str(res.inserted_id)
        
        # BROADCAST NOTIFICATION to all users
        try:
            from models.notifications_model import NotificationsModel
            from models.users_model import get_all_users
            
            nm = NotificationsModel()
            users = get_all_users()
            
            for user in users:
                user_email = user.get('email')
                if not user_email:
                    continue
                
                nm.create_notification({
                    'user_email': user_email,
                    'type': 'deal_alert',
                    'title': 'New Featured Deal!',
                    'message': f"A new deal on {doc.get('title', 'a product')} is now available.",
                    'deal_id': deal_id,
                    'action_url': f"/featured-deal/{deal_id}",
                    'priority': 'normal'
                })
        except Exception as e:
            print(f"Error sending broadcast notifications: {e}")
            
        return deal_id

    def update_deal(self, id_str: str, update_doc: dict) -> bool:
        # MODIFY DEAL in database (admin only)
        try:
            update_doc.pop('_id', None)  # Never modify _id
            res = self.db.featured_deals.update_one({'_id': ObjectId(id_str)}, {'$set': update_doc})
            return getattr(res, 'modified_count', 0) > 0
        except Exception:
            return False

    def delete_deal(self, id_str: str) -> bool:
        # REMOVE DEAL from database (admin only)
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

def get_deals_count() -> int:
    return featured_deals_model.get_deals_count()

def get_deal_by_title(title: str) -> Optional[dict]:
    return featured_deals_model.get_deal_by_title(title)

def insert_deal(doc: dict):
    return featured_deals_model.insert_deal(doc)
