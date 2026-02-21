"""
═══════════════════════════════════════════════════════════════════════════
NOTIFICATIONS MODEL - Alert System
═══════════════════════════════════════════════════════════════════════════
Purpose: Manages persistent user alerts (Price drops, New deals, System msgs).
Database Collection: 'notifications' in MongoDB

Core Features:
- Persistent storage of alerts.
- Smart Lookup: Tries to "rehydrate" deal/product info even if the original
  deal ID is invalid or deleted (using Title matching fallback).
- Auto-Cleanup: Older notifications (default 7 days) can be purged.

Complex Logic:
- `get_user_notifications`: Performs "Join-like" operations manually.
  It stores references (product_id), but queries the Products collection
  at read-time to get the *latest* price/image, rather than showing stale data.
═══════════════════════════════════════════════════════════════════════════
"""
from pymongo import MongoClient
from bson import ObjectId
import os
from dotenv import load_dotenv, find_dotenv
from typing import List, Optional, Dict
from datetime import datetime, timedelta
import certifi

# Load environment variables with override to check local .env
load_dotenv(find_dotenv(usecwd=True), override=True)


# ═══════════════════════════════════════════════════════════════════════════
# CATEGORY: INITIALIZATION
# ═══════════════════════════════════════════════════════════════════════════

class NotificationsModel:
    def __init__(self):
        """
        Initialize Notifications Model.
        """
        # Database dependency injection
        from utils.db import get_db
        self.db = get_db()
        self._client = None


    # ═══════════════════════════════════════════════════════════════════════════
    # CATEGORY: CREATE ALERTS
    # ═══════════════════════════════════════════════════════════════════════════

    def create_notification(self, notification_data: dict) -> Optional[str]:
        """
        Create a new persistent notification.
        
        Fields:
        - type: 'deal_alert', 'price_drop', 'system'
        - priority: Used for sorting or UI highlighting (e.g., Red bell icon).
        """
        # 1. Validate Required Fields
        if not notification_data.get('user_email') or not notification_data.get('type'):
            return None
        
        # 2. Build Document
        notification = {
            'user_email': notification_data['user_email'],
            'type': notification_data['type'],
            'title': notification_data.get('title', ''),
            'message': notification_data.get('message', ''),
            'action_url': notification_data.get('action_url', ''),
            'priority': notification_data.get('priority', 'normal'),
            'read': False, # Default state
            'created_at': datetime.utcnow()
        }
        
        # 3. Add Context References (Links to Product/Deal)
        if notification_data.get('product_id'):
            try:
                notification['product_id'] = ObjectId(notification_data['product_id'])
            except Exception:
                pass
        
        if notification_data.get('deal_id'):
            notification['deal_id'] = notification_data['deal_id']
        
        if notification_data.get('store_name'):
            notification['store_name'] = notification_data['store_name']
        
        # 4. Insert into Database
        try:
            result = self.db.notifications.insert_one(notification)
            return str(result.inserted_id)
        except Exception as e:
            print(f"Error creating notification: {e}")
            return None


    # ═══════════════════════════════════════════════════════════════════════════
    # CATEGORY: READ NOTIFICATIONS (WITH HYDRATION)
    # ═══════════════════════════════════════════════════════════════════════════

    def get_user_notifications(self, user_email: str, 
                              unread_only: bool = False,
                              limit: int = 50) -> List[dict]:
        """
        Fetch notifications with "Hydrated" product data.
        
        Logic (The Professor Check):
        1. Fetch raw notification docs.
        2. Iterate and check if `product_id` or `deal_id` exists.
        3. Perform a fresh DB lookup for that deal/product.
           Why? If a product price changed *after* the notification was sent,
           we want the user to see the *current* state when they click it.
        4. Fallback: If ID lookup fails (deal deleted?), try matching by Title string.
        """
        if not user_email:
            return []
        
        # 1. Build Query
        query = {'user_email': user_email}
        if unread_only:
            query['read'] = False

        # 2. Filter: Only show recent notifications (e.g. User join date or 7 days)
        try:
            user = self.db.users.find_one({'email': user_email}, {'created_at': 1})
            start_date = datetime.utcnow() - timedelta(days=7)
            if user and user.get('created_at'):
                # Use whichever is more recent: User Join Date OR 7 days ago
                start_date = max(user['created_at'], start_date)
            query['created_at'] = {'$gte': start_date}
        except Exception as e:
            # Fallback safe default
            query['created_at'] = {'$gte': datetime.utcnow() - timedelta(days=7)}
        
        # 3. Execute Query
        notifications = list(self.db.notifications.find(query)
                           .sort('created_at', -1)
                           .limit(limit))
        
        # 4. START HYDRATION LOOP
        for n in notifications:
            if '_id' in n:
                n['id'] = str(n['_id'])
            
            # Strategy A: Try to load Deal details
            deal = None
            if n.get('deal_id'):
                try:
                    d_id = n['deal_id']
                    query_id = ObjectId(d_id) if ObjectId.is_valid(d_id) else d_id
                    deal = self.db.featured_deals.find_one({'_id': query_id})
                except Exception:
                    pass
            
            # Fallback A: String Title Match (If deal ID invalid)
            if not deal and n.get('type') in ['deal_alert', 'deal', 'new_deal'] and n.get('title'):
                try:
                    clean_title = n['title'].replace('New Deal:', '').strip()
                    if clean_title:
                        # Regex search for approximate match
                        deal = self.db.featured_deals.find_one({'title': {'$regex': clean_title, '$options': 'i'}}) 
                        if not deal:
                            deal = self.db.featured_deals.find_one({'name': {'$regex': clean_title, '$options': 'i'}})
                except Exception:
                    pass

            # If Deal Found: Populate notification fields
            if deal:
                n['product_name'] = deal.get('title') or deal.get('name')
                n['product_image'] = deal.get('image')
                n['price'] = deal.get('price')
                n['old_price'] = deal.get('original_price')
                n['store_name'] = deal.get('store')
                n['offer_name'] = deal.get('discount_label') or deal.get('offer')
                
                # Fix missing IDs for links
                if not n.get('deal_id'): n['deal_id'] = str(deal['_id'])
                if deal.get('product_id') and not n.get('product_id'):
                    n['product_id'] = str(deal['product_id'])

            # Strategy B: If no Deal found, try Product Lookup (for Price Drops)
            if (not n.get('product_name') or not n.get('product_image')) and n.get('product_id'):
                try:
                    p_id = n['product_id']
                    query_id = ObjectId(p_id) if ObjectId.is_valid(p_id) else p_id
                    product = self.db.products.find_one({'_id': query_id})
                    
                    if not product and n.get('title'):
                        clean_title = n['title'].replace('New Deal:', '').replace('Price Drop:', '').strip()
                        if clean_title:
                             product = self.db.products.find_one({'name': {'$regex': clean_title, '$options': 'i'}})

                    if product:
                        if not n.get('product_name'): n['product_name'] = product.get('name')
                        if not n.get('product_image'): 
                            n['product_image'] = product.get('image') or (product.get('images')[0] if product.get('images') else None)
                        if not n.get('price'): n['price'] = product.get('price_val') or product.get('price')
                        if not n.get('store_name'):
                            stores = product.get('stores', [])
                            if stores and isinstance(stores, list) and len(stores) > 0:
                                n['store_name'] = stores[0].get('store')
                except Exception:
                    pass
            
            n['product_id'] = str(n.get('product_id')) if n.get('product_id') else None
        
        return notifications


    # ═══════════════════════════════════════════════════════════════════════════
    # CATEGORY: UTILITY OPERATIONS
    # ═══════════════════════════════════════════════════════════════════════════

    def get_unread_count(self, user_email: str) -> int:
        """Get count of unread notifications."""
        if not user_email:
            return 0
        
        # Simple count filtering by 'read': False
        # We perform a date check similar to get_notifications to stay consistent
        query = {
            'user_email': user_email,
            'read': False,
            'created_at': {'$gte': datetime.utcnow() - timedelta(days=7)}
        }
        return self.db.notifications.count_documents(query)

    def mark_all_read(self, user_email: str) -> bool:
        """Mark ALL notifications as read for a user."""
        if not user_email: return False
        
        result = self.db.notifications.update_many(
            {'user_email': user_email, 'read': False},
            {'$set': {'read': True}}
        )
        return result.modified_count > 0

    def mark_as_read(self, notification_id: str) -> bool:
        """Mark a single notification as read."""
        if not notification_id: return False
        
        try:
            self.db.notifications.update_one(
                {'_id': ObjectId(notification_id)},
                {'$set': {'read': True}}
            )
            return True
        except Exception:
            return False


    def cleanup_old_notifications(self, days=7):
        """
        Delete notifications older than X days.
        """
        if self.db is None: return False
        
        try:
            cutoff = datetime.utcnow() - timedelta(days=days)
            res = self.db.notifications.delete_many({'created_at': {'$lt': cutoff}})
            return getattr(res, 'deleted_count', 0) > 0
        except Exception:
            return False

    def delete_notification(self, notification_id: str, user_email: str) -> bool:
        """Delete a notification."""
        try:
             # Add user_email check for security
             result = self.db.notifications.delete_one({'_id': ObjectId(notification_id), 'user_email': user_email})
             return result.deleted_count > 0
        except Exception:
             return False


# Initialize the singleton instance
notifications_model = NotificationsModel()

# Module-level aliases
def cleanup_old_notifications(days=7):
    return notifications_model.cleanup_old_notifications(days)

def get_user_notifications(user_email, unread_only=False, limit=50):
    return notifications_model.get_user_notifications(user_email, unread_only, limit)

def get_unread_count(user_email):
    return notifications_model.get_unread_count(user_email)

def mark_all_read(user_email):
    return notifications_model.mark_all_read(user_email)

def mark_as_read(notification_id):
    return notifications_model.mark_as_read(notification_id)

def create_notification(data):
    return notifications_model.create_notification(data)

def delete_notification(notification_id, user_email):
    return notifications_model.delete_notification(notification_id, user_email)
