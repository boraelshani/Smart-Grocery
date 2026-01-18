import os
import sys
from datetime import datetime
from pymongo import MongoClient
from bson import ObjectId
from dotenv import load_dotenv

# Add project root to path
sys.path.append(os.getcwd())

load_dotenv()

def migrate_and_seed_notifications():
    mongo_uri = os.getenv('MONGO_URI')
    client = MongoClient(mongo_uri)
    db = client.get_database()
    
    # 1. Migrate existing notification types to match template IDs
    print("Migrating existing notification types...")
    res = db.notifications.update_many({'type': 'deal'}, {'$set': {'type': 'deal_alert'}})
    print(f"Updated {res.modified_count} 'deal' -> 'deal_alert'")
    
    res = db.notifications.update_many({'type': 'new_deal'}, {'$set': {'type': 'deal_alert'}})
    print(f"Updated {res.modified_count} 'new_deal' -> 'deal_alert'")
    
    # 2. Get all users
    users = list(db.users.find({}, {'email': 1}))
    if not users:
        print("No users found. Exiting.")
        return

    # 3. Get some products and deals to use as samples
    products = list(db.products.find().limit(5))
    deals = list(db.featured_deals.find().limit(3))
    
    print(f"Seeding notifications for {len(users)} users...")
    
    notifs_to_insert = []
    for user in users:
        email = user.get('email')
        if not email: continue
        
        # System Notification
        notifs_to_insert.append({
            'user_email': email,
            'type': 'system',
            'title': 'Welcome to Alert Center!',
            'message': 'You will now receive notifications about price drops, new deals, and profile updates here.',
            'priority': 'normal',
            'read': False,
            'created_at': datetime.utcnow()
        })
        
        # Product/Price Drop (if we have products)
        for p in products:
            notifs_to_insert.append({
                'user_email': email,
                'type': 'price_drop',
                'title': f"Price Drop: {p.get('name')}",
                'message': f"Great news! {p.get('name')} is now cheaper at {p.get('stores', [{}])[0].get('store', 'your favorite store')}.",
                'product_id': p['_id'],
                'priority': 'high',
                'read': False,
                'created_at': datetime.utcnow()
            })
            break # Just one per user
            
        # Deal Alert (if we have deals)
        for d in deals:
            notifs_to_insert.append({
                'user_email': email,
                'type': 'deal_alert',
                'title': f"New Deal: {d.get('title')}",
                'message': f"Flash sale! {d.get('description', 'Check out this featured deal.')}",
                'priority': 'high',
                'read': False,
                'created_at': datetime.utcnow()
            })
            break # Just one per user

    if notifs_to_insert:
        db.notifications.delete_many({}) # Clear existing to avoid clutter during fix
        db.notifications.insert_many(notifs_to_insert)
        print(f"Successfully seeded {len(notifs_to_insert)} notifications.")
    else:
        print("No notifications to insert.")

if __name__ == "__main__":
    migrate_and_seed_notifications()
