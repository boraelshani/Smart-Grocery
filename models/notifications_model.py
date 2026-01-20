"""
═══════════════════════════════════════════════════════════════════════════
NOTIFICATIONS MODEL - User Alerts & Messages
═══════════════════════════════════════════════════════════════════════════
Purpose: Manage user notifications for deals, updates, and alerts
Database Collection: 'notifications' in MongoDB
Notification Types:
- deal_alert: New deals on favorite products
- price_drop: Product price decreased
- back_in_stock: Out-of-stock product is available
- system: System announcements and updates
Functions:
- Create notifications
- Get user notifications
- Mark as read/unread
- Delete notifications
Used by: navigation bar, profile, background tasks
═══════════════════════════════════════════════════════════════════════════
"""
from pymongo import MongoClient
from bson import ObjectId
import os
from dotenv import load_dotenv, find_dotenv
from typing import List, Optional, Dict
from datetime import datetime, timedelta
import certifi

# Load environment variables with override to ensure .env file values take precedence
# over any existing environment variables (e.g. default localhost from system/shell)
load_dotenv(find_dotenv(usecwd=True), override=True)


class NotificationsModel:
    def __init__(self):
        mongo_uri = os.getenv('MONGO_URI') or 'mongodb://localhost:27017/smart_grocery'
        if '<' in mongo_uri or '>' in mongo_uri:
            mongo_uri = mongo_uri.replace('<', '').replace('>', '')
        database_name = os.getenv('DATABASE_NAME', None)
        
        try:
            from utils.db import mongo as flask_mongo
        except Exception:
            flask_mongo = None

        if flask_mongo is not None and getattr(flask_mongo, 'db', None) is not None:
            self.db = flask_mongo.db
            self._client = None
        else:
            # Check if using localhost (don't use SSL for local dev unless specified)
            use_ssl = True
            if 'localhost' in mongo_uri or '127.0.0.1' in mongo_uri:
                use_ssl = False

            try:
                if use_ssl:
                    self._client = MongoClient(mongo_uri, tlsCAFile=certifi.where())
                else:
                    self._client = MongoClient(mongo_uri)
            except Exception:
                # Fallback to simple connection if SSL/certifi fails or if arguments are wrong
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

    def create_notification(self, notification_data: dict) -> Optional[str]:
        """
        Create a new notification
        
        Required fields:
        - user_email: str
        - type: 'deal_alert', 'price_drop', 'back_in_stock', 'system'
        - title: str
        - message: str
        
        Optional fields:
        - product_id: str (for product-related notifications)
        - store_name: str
        - action_url: str (link to relevant page)
        - priority: 'low', 'normal', 'high'
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
        
        # Add optional references
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
        """Get notifications for a user"""
        if not user_email:
            return []
        
        query = {'user_email': user_email}
        if unread_only:
            query['read'] = False

        # Filter: Only show notifications created AFTER the user joined
        try:
            user = self.db.users.find_one({'email': user_email}, {'created_at': 1})
            if user and user.get('created_at'):
                # Ensure we also respect the 7 day limit even if cleanup hasn't run
                seven_days_ago = datetime.utcnow() - timedelta(days=7)
                limit_date = max(user['created_at'], seven_days_ago) # Use whichever is more recent
                query['created_at'] = {'$gte': limit_date}
            else:
                 # If no user creation date, just use 7 days ago
                 query['created_at'] = {'$gte': datetime.utcnow() - timedelta(days=7)}
        except Exception as e:
            print(f"Error fetching user join date for notification filtering: {e}")
            query['created_at'] = {'$gte': datetime.utcnow() - timedelta(days=7)}
        
        notifications = list(self.db.notifications.find(query)
                           .sort('created_at', -1)
                           .limit(limit))
        
        for n in notifications:
            if '_id' in n:
                n['id'] = str(n['_id'])
            
            # --- Enhanced Product/Deal Lookup ---
            
            # 1. Try Deal Lookup First
            deal = None
            if n.get('deal_id'):
                try:
                    d_id = n['deal_id']
                    query_id = ObjectId(d_id) if ObjectId.is_valid(d_id) else d_id
                    deal = self.db.featured_deals.find_one({'_id': query_id})
                except Exception:
                    pass
            
            # Fallback: Search Deal by Title if ID missing (for seeded data)
            if not deal and n.get('type') in ['deal_alert', 'deal', 'new_deal'] and n.get('title'):
                try:
                    clean_title = n['title'].replace('New Deal:', '').strip()
                    if clean_title:
                        deal = self.db.featured_deals.find_one({'title': {'$regex': clean_title, '$options': 'i'}}) 
                        # Also try matching 'name' field just in case
                        if not deal:
                            deal = self.db.featured_deals.find_one({'name': {'$regex': clean_title, '$options': 'i'}})
                except Exception:
                    pass

            if deal:
                n['product_name'] = deal.get('title') or deal.get('name')
                n['product_image'] = deal.get('image')
                n['price'] = deal.get('price')
                n['old_price'] = deal.get('original_price')
                n['store_name'] = deal.get('store')
                n['offer_name'] = deal.get('discount_label') or deal.get('offer')
                
                # IMPORTANT: Set these so the template renders the card!
                if not n.get('deal_id'):
                    n['deal_id'] = str(deal['_id'])
                if deal.get('product_id') and not n.get('product_id'):
                    n['product_id'] = str(deal['product_id'])

            # 2. If Product Info still missing, try Product Lookup

            # 2. If Product Info still missing, try Product Lookup
            if (not n.get('product_name') or not n.get('product_image')) and n.get('product_id'):
                try:
                    p_id = n['product_id']
                    query_id = ObjectId(p_id) if ObjectId.is_valid(p_id) else p_id
                    product = self.db.products.find_one({'_id': query_id})
                    
                    # Fallback: Search by name from notification title/message if ID failed
                    # e.g. "Price Drop: Milk 1L" -> search "Milk 1L"
                    if not product and n.get('title'):
                        clean_title = n['title'].replace('New Deal:', '').replace('Price Drop:', '').strip()
                        if clean_title:
                             product = self.db.products.find_one({'name': {'$regex': clean_title, '$options': 'i'}})

                    if product:
                        if not n.get('product_name'):
                            n['product_name'] = product.get('name')
                        if not n.get('product_image'):
                            n['product_image'] = product.get('image') or (product.get('images')[0] if product.get('images') else None)
                        if not n.get('price'):
                            n['price'] = product.get('price_val') or product.get('price')
                        if not n.get('store_name'):
                            stores = product.get('stores', [])
                            if stores and isinstance(stores, list) and len(stores) > 0:
                                n['store_name'] = stores[0].get('store')
                except Exception as e:
                    # print(f"Product lookup failed: {e}")
                    pass
            
            n['product_id'] = str(n.get('product_id')) if n.get('product_id') else None
        
        return notifications

    def get_unread_count(self, user_email: str) -> int:
        """Get count of unread notifications"""
        if not user_email:
            return 0
        
        # Filter out types that we are now injecting dynamically to avoid duplicates/ghost counts
        # This fixes the "50 unread vs 18 shown" issue
        ignored_types = ['deal_alert', 'new_deal', 'price_drop']
        
        query = {
            'user_email': user_email,
            'read': False,
            'type': {'$nin': ignored_types}
        }

        # Filter: Only count notifications created AFTER the user joined
        try:
            user = self.db.users.find_one({'email': user_email}, {'created_at': 1})
            if user and user.get('created_at'):
                query['created_at'] = {'$gte': user['created_at']}
        except Exception:
            pass
        
        return self.db.notifications.count_documents(query)

    def mark_as_read(self, notification_id: str, user_email: str) -> bool:
        """Mark a notification as read"""
        try:
            result = self.db.notifications.update_one(
                {'_id': ObjectId(notification_id), 'user_email': user_email},
                {'$set': {'read': True, 'read_at': datetime.utcnow()}}
            )
            return result.modified_count > 0
        except Exception:
            return False

    def mark_all_as_read(self, user_email: str) -> bool:
        """Mark all user notifications as read"""
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
        """Delete a notification"""
        try:
            result = self.db.notifications.delete_one({
                '_id': ObjectId(notification_id),
                'user_email': user_email
            })
            return result.deleted_count > 0
        except Exception:
            return False

    def delete_all_notifications(self, user_email: str) -> bool:
        """Delete all notifications for a user"""
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
        """Delete ANY notifications older than specified days (read or unread)"""
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
        """Convenience method to create a deal alert notification"""
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
        """Convenience method to create a price drop notification"""
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
        """Convenience method to create a system notification"""
        return self.create_notification({
            'user_email': user_email,
            'type': 'system',
            'title': title,
            'message': message,
            'priority': priority
        })

    def broadcast_notification(self, notification_data: dict, user_emails: List[str] = None) -> int:
        """
        Send a notification to multiple users. 
        If user_emails is None, send to ALL registered users.
        """
        count = 0
        try:
            if user_emails is None:
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

    def cleanup_old_notifications(self, days: int = 7) -> int:
        """Delete notifications older than specified days"""
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=days)
            result = self.db.notifications.delete_many({
                'created_at': {'$lt': cutoff_date}
            })
            return result.deleted_count
        except Exception as e:
            print(f"Error in cleanup_old_notifications: {e}")
            return 0

    def close_connection(self):
        if self._client:
            self._client.close()


# Singleton instance
notifications_model = NotificationsModel()

# Convenience functions
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
