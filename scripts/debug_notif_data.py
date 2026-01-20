
import os
import sys
from pymongo import MongoClient
from bson import ObjectId
from dotenv import load_dotenv
import certifi

# Add project root to path
sys.path.append(os.getcwd())

load_dotenv()

def debug_notifications():
    if not os.environ.get('SSL_CERT_FILE'):
        os.environ['SSL_CERT_FILE'] = certifi.where()

    mongo_uri = os.getenv('MONGO_URI')
    client = MongoClient(mongo_uri, tlsCAFile=certifi.where())
    db = client.get_default_database()
    
    notifications = list(db.notifications.find().sort('created_at', -1).limit(5))
    print(f"Found {len(notifications)} notifications")
    
    for n in notifications:
        print("\n--- Notification ---")
        print(f"ID: {n.get('_id')}")
        print(f"Type: {n.get('type')}")
        print(f"Product ID in Notif: {n.get('product_id')} (Type: {type(n.get('product_id'))})")
        print(f"Deal ID in Notif: {n.get('deal_id')}")
        
        # Check Product
        p_id = n.get('product_id')
        if p_id:
            try:
                # Try as ObjectId
                if isinstance(p_id, str):
                    p_obj_id = ObjectId(p_id)
                else:
                    p_obj_id = p_id
                
                prod = db.products.find_one({'_id': p_obj_id})
                print(f"Product Found (by ID): {prod.get('name') if prod else 'NO'}")
                if prod:
                    print(f"  Image: {prod.get('image')}")
                    print(f"  Images: {prod.get('images')}")
                    print(f"  Price: {prod.get('price')} / {prod.get('price_val')}")
            except Exception as e:
                print(f"Product lookup failed: {e}")

        # Check Deal
        d_id = n.get('deal_id')
        if d_id:
            deal = db.featured_deals.find_one({'_id': ObjectId(d_id) if isinstance(d_id, str) else d_id})
            print(f"Deal Found: {deal.get('name') if deal else 'NO'}")

if __name__ == "__main__":
    debug_notifications()
