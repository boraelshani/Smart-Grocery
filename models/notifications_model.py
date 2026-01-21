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


class NotificationsModel:
    def __init__(self):
        # Database dependency injection
        from utils.db import get_db
        self.db = get_db()
        self._client = None


    def create_notification(self, notification_data: dict) -> Optional[str]:
        """
        Create a new persistent notification.
        
        Fields:
        - type: 'deal_alert', 'price_drop', 'system'
        - priority: Used for sorting or UI highlighting (e.g., Red bell icon).
        """
        if not notification_data.get('user_email') or not notification_data.get('type'):
            return None
        
        notification = {
            'user_email': notification_data['user_email'],
            'type': notification_data['type'],
            'title': notification_data.get('title', ''),
            'message': notification_data.get('message', ''),
            'action_url': notification_data.get('action_url', ''),
            'priority': notification_data.get('priority', 'normal'),
            'read': False,
            'created_at': datetime.utcnow()
        }
        
        # Add optional references (store as Strings or ObjectIds depending on access pattern)
        if notification_data.get('product_id'):
            try:
                notification['product_id'] = ObjectId(notification_data['product_id'])
            except Exception:
                pass
        
        if notification_data.get('deal_id'):
            notification['deal_id'] = notification_data['deal_id']
        
        if notification_data.get('store_name'):
            notification['store_name'] = notification_data['store_name']
        
        try:
            result = self.db.notifications.insert_one(notification)
            return str(result.inserted_id)
        except Exception as e:
            print(f"Error creating notification: {e}")
            return None

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
           we want the user to see the *current* state when they click it,
           or at least have a valid link.
        4. Fallback: If ID lookup fails (deal deleted?), try matching by Title string.
        """
        if not user_email:
            return []
        
        query = {'user_email': user_email}
        if unread_only:
            query['read'] = False

        # Filter: Only show notifications created AFTER the user joined, 
        # or within the last 7 days standard window.
        try:
            user = self.db.users.find_one({'email': user_email}, {'created_at': 1})
            start_date = datetime.utcnow() - timedelta(days=7)
            if user and user.get('created_at'):
                # Use whichever is more recent: User Join Date OR 7 days ago
                # This prevents showing "Welcome" messages to old users who re-login?
                # Actually it prevents showing ancient notifications if we increase retention.
                start_date = max(user['created_at'], start_date)
            query['created_at'] = {'$gte': start_date}
        except Exception as e:
            # Fallback safe default
            query['created_at'] = {'$gte': datetime.utcnow() - timedelta(days=7)}
        
        notifications = list(self.db.notifications.find(query)
                           .sort('created_at', -1)
                           .limit(limit))
        
        # --- HYDRATION LOOP ---
        for n in notifications:
            if '_id' in n:
                n['id'] = str(n['_id'])
            
            # Strategy 1: Try to load Deal details
            deal = None
            if n.get('deal_id'):
                try:
                    d_id = n['deal_id']
                    query_id = ObjectId(d_id) if ObjectId.is_valid(d_id) else d_id
                    deal = self.db.featured_deals.find_one({'_id': query_id})
                except Exception:
                    pass
            
            # Fallback Strategy: Strings. "New Deal: Coca Cola" -> Search "Coca Cola"
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

            # Populate from Deal
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

            # Strategy 2: If no Deal found, try Product Lookup (for Price Drops)
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

    def get_unread_count(self, user_email: str) -> int:
        """Get count of unread notifications."""
        if not user_email:
            return 0
        
        # Exclude dynamic/injected types if necessary to match frontend logic
        ignored_types = ['deal_alert', 'new_deal', 'price_drop']
        
        query = {
            'user_email': user_email,
            'read': False,
            'type': {'$nin': ignored_types}
        }

        try:
            # Respect the join date filter same as get_notifications
            user = self.db.users.find_one({'email': user_email}, {'created_at': 1})
            if user and user.get('created_at'):
                query['created_at'] = {'$gte': user['created_at']}
        except Exception:
            pass
        
        return self.db.notifications.count_documents(query)

    def mark_as_read(self, notification_id: str, user_email: str) -> bool:
        """Mark specific notification as read."""
        try:
            result = self.db.notifications.update_one(
                {'_id': ObjectId(notification_id), 'user_email': user_email},
                {'$set': {'read': True, 'read_at': datetime.utcnow()}}
            )
            return result.modified_count > 0
        except Exception:
            return False

    def mark_all_as_read(self, user_email: str) -> bool:
        """Bulk mark all as read."""
        if not user_email:
            return False
        
        try:
            result = self.db.notifications.update_many(
                {'user_email': user_email, 'read': False},
                {'$set': {'read': True, 'read_at': datetime.utcnow()}}
            )
            return result.modified_count > 0
        except Exception:
            return False

    def delete_notification(self, notification_id: str, user_email: str) -> bool:
        """Delete a notification permanently."""
        try:
            result = self.db.notifications.delete_one({
                '_id': ObjectId(notification_id),
                'user_email': user_email
            })
            return result.deleted_count > 0
        except Exception:
            return False

    def delete_all_notifications(self, user_email: str) -> bool:
        """Delete all notifications for a user."""
        if not user_email:
            return False
        
        try:
            result = self.db.notifications.delete_many({
                'user_email': user_email
            })
            return result.deleted_count > 0
        except Exception:
            return False

    def cleanup_old_notifications(self, days: int = 7) -> int:
        """
        Delete ANY notifications older than specified days (read or unread).
        Keeps database size manageable.
        """
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        try:
            result = self.db.notifications.delete_many({
                'created_at': {'$lt': cutoff_date}
            })
            return result.deleted_count
        except Exception as e:
            print(f"Error cleaning up old notifications: {e}")
            return 0

    def create_deal_alert(self, user_email: str, product_id: str, 
                         product_name: str, store_name: str, 
                         discount_percent: int) -> Optional[str]:
        """Convenience: Create 'New Deal' alert."""
        return self.create_notification({
            'user_email': user_email,
            'type': 'deal_alert',
            'title': f'New Deal: {product_name}',
            'message': f'{discount_percent}% off at {store_name}!',
            'product_id': product_id,
            'store_name': store_name,
            'action_url': f'/product/{product_id}',
            'priority': 'normal'
        })

    def create_price_drop_alert(self, user_email: str, product_id: str,
                               product_name: str, old_price: float, 
                               new_price: float) -> Optional[str]:
        """Convenience: Create 'Price Drop' alert."""
        savings = old_price - new_price
        return self.create_notification({
            'user_email': user_email,
            'type': 'price_drop',
            'title': f'Price Drop: {product_name}',
            'message': f'Now €{new_price:.2f} (was €{old_price:.2f}) - Save €{savings:.2f}!',
            'product_id': product_id,
            'action_url': f'/product/{product_id}',
            'priority': 'high'
        })

    def create_system_notification(self, user_email: str, title: str, 
                                  message: str, priority: str = 'normal') -> Optional[str]:
        """Convenience: Create system-wide alert (e.g. 'Maintenance')."""
        return self.create_notification({
            'user_email': user_email,
            'type': 'system',
            'title': title,
            'message': message,
            'priority': priority
        })

    def broadcast_notification(self, notification_data: dict, user_emails: List[str] = None) -> int:
        """
        Send a notification to multiple users (or ALL users).
        Used for global announcements.
        """
        count = 0
        try:
            if user_emails is None:
                # Get all users (projection for efficiency)
                users = list(self.db.users.find({}, {'email': 1}))
                target_emails = [u.get('email') for u in users if u.get('email')]
            else:
                target_emails = user_emails

            for email in target_emails:
                data = notification_data.copy()
                data['user_email'] = email
                if self.create_notification(data):
                    count += 1
        except Exception as e:
            print(f"Error broadcasting notification: {e}")
        return count

    def close_connection(self):
        if self._client:
            self._client.close()


# Singleton instance
notifications_model = NotificationsModel()

# ════════════════════════════════════════════════════════════════════════════
# MODULE LEVEL CONVENIENCE FUNCTIONS
# ════════════════════════════════════════════════════════════════════════════

def create_notification(notification_data: dict) -> Optional[str]:
    return notifications_model.create_notification(notification_data)

def get_user_notifications(user_email: str, unread_only: bool = False, 
                          limit: int = 50) -> List[dict]:
    return notifications_model.get_user_notifications(user_email, unread_only, limit)

def get_unread_count(user_email: str) -> int:
    return notifications_model.get_unread_count(user_email)

def mark_as_read(notification_id: str, user_email: str) -> bool:
    return notifications_model.mark_as_read(notification_id, user_email)

def mark_all_as_read(user_email: str) -> bool:
    return notifications_model.mark_all_as_read(user_email)

def delete_notification(notification_id: str, user_email: str) -> bool:
    return notifications_model.delete_notification(notification_id, user_email)

def create_deal_alert(user_email: str, product_id: str, product_name: str,
                     store_name: str, discount_percent: int) -> Optional[str]:
    return notifications_model.create_deal_alert(
        user_email, product_id, product_name, store_name, discount_percent
    )

def create_price_drop_alert(user_email: str, product_id: str, product_name: str,
                           old_price: float, new_price: float) -> Optional[str]:
    return notifications_model.create_price_drop_alert(
        user_email, product_id, product_name, old_price, new_price
    )
