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
from dotenv import load_dotenv
from typing import List, Optional, Dict
from datetime import datetime, timedelta
import certifi

load_dotenv()


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
        
        notifications = list(self.db.notifications.find(query)
                           .sort('created_at', -1)
                           .limit(limit))
        
        for n in notifications:
            if '_id' in n:
                n['id'] = str(n['_id'])
            if 'product_id' in n:
                n['product_id'] = str(n['product_id'])
        
        return notifications

    def get_unread_count(self, user_email: str) -> int:
        """Get count of unread notifications"""
        if not user_email:
            return 0
        
        return self.db.notifications.count_documents({
            'user_email': user_email,
            'read': False
        })

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

    def cleanup_old_notifications(self, days: int = 30) -> int:
        """Delete read notifications older than specified days"""
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        try:
            result = self.db.notifications.delete_many({
                'read': True,
                'created_at': {'$lt': cutoff_date}
            })
            return result.deleted_count
        except Exception:
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

    def broadcast_notification(self, notification_data: dict, 
                              user_emails: List[str]) -> int:
        """Send same notification to multiple users"""
        count = 0
        for email in user_emails:
            notification_data['user_email'] = email
            if self.create_notification(notification_data):
                count += 1
        return count

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
