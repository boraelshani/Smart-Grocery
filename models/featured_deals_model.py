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


class FeaturedDealsModel:
    def __init__(self):
        # Database dependency injection
        from utils.db import get_db
        self.db = get_db()
        self._client = None


    def get_deal_by_id(self, deal_id: str) -> Optional[dict]:
        """
        Retrieve a specific deal by its ID.
        Handles both ObjectId strings and potential legacy/manual string IDs.
        """
        from bson import ObjectId
        try:
            # First attempt: Look up by standard MongoDB ObjectId
            doc = self.db.featured_deals.find_one({'_id': ObjectId(deal_id)})
            if doc and '_id' in doc:
                doc['id'] = str(doc['_id'])
            return doc
        except Exception:
            # Fallback 1: Look for 'id' string field (sometimes used in seeded data)
            doc = self.db.featured_deals.find_one({'id': deal_id})
            if not doc:
                # Fallback 2: Look for 'title' match (rare but possible in URL slugs)
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
        """Count total active deals."""
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
        """Count deals available at a specific store."""
        import re
        regex = {'$regex': re.escape(store_name), '$options': 'i'}
        return self.db.featured_deals.count_documents({
            '$or': [
                {'store': regex},
                {'source': regex}
            ]
        })

    def find_by_store(self, store_name: str) -> List[dict]:
        """List deals from a specific store."""
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

    def insert_deal(self, doc: dict) -> str:
        """
        Add a new deal to the database.
        Triggers a notification broadcast to all users about the new deal.
        """
        # ADD NEW DEAL to database (admin only)
        if 'created_at' not in doc:
            from datetime import datetime
            doc['created_at'] = datetime.utcnow() # Timestamp for sorting
        res = self.db.featured_deals.insert_one(doc)
        deal_id = str(res.inserted_id)
        
        # BROADCAST NOTIFICATION: Alert all users about the new deal
        try:
            from models.notifications_model import NotificationsModel
            from models.users_model import get_all_users
            
            nm = NotificationsModel()
            users = get_all_users()
            
            # This loop sends a personal notification to every registered user
            # In a massive scale app, this would be a background job/queue task
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

