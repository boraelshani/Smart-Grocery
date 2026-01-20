
import os
import sys
from pymongo import MongoClient
from dotenv import load_dotenv
import certifi

# Add project root to path
sys.path.append(os.getcwd())
load_dotenv()

def clear_and_regenerate():
    if not os.environ.get('SSL_CERT_FILE'):
        os.environ['SSL_CERT_FILE'] = certifi.where()

    mongo_uri = os.getenv('MONGO_URI')
    client = MongoClient(mongo_uri, tlsCAFile=certifi.where())
    db = client.get_default_database()
    
    # 1. DELETE ALL NOTIFICATIONS
    print("Deleting all existing notifications...")
    result = db.notifications.delete_many({})
    print(f"Deleted {result.deleted_count} notifications.")
    
    # 2. RUN GENERATION LOGIC DIRECTLY
    # (Copying logic from generate_real_notifications.py to avoid import issues or re-run complications)
    import random
    from datetime import datetime
    
    products = list(db.products.find().limit(20))
    users = list(db.users.find({}, {'email': 1}))
    
    print(f"Regenerating for {len(users)} users using {len(products)} real products...")
    
    count = 0
    for user in users:
        email = user.get('email')
        if not email: continue

        # Give each user 3 random notifications
        random.shuffle(products)
        selected_products = products[:3]

        for p in selected_products:
            p_id = p['_id']
            name = p.get('name', 'Unknown Product')
            image = p.get('image')
            price = p.get('price_val') or p.get('price')
            
            # Safe store extraction
            store_name = "Supermarket"
            if p.get('stores') and isinstance(p['stores'], list) and len(p['stores']) > 0:
                s = p['stores'][0]
                if isinstance(s, dict):
                    store_name = s.get('store', 'Supermarket')
            
            offer_types = ["Price Drop", "New Arrival", "Best Value"]
            offer = random.choice(offer_types)
            
            notif_type = 'deal_alert'
            old_price = None
            
            if offer == "Price Drop":
                notif_type = 'price_drop'
                try:
                    price_f = float(str(price).replace('€','').strip())
                    old_price = price_f * 1.15
                    message = f"Price dropped to €{price_f:.2f}! Was €{old_price:.2f}."
                except:
                    message = f"Price dropped for {name}!"
            else:
                message = f"Great deal on {name} at {store_name}."

            notification = {
                'user_email': email,
                'type': notif_type,
                'title': f"{offer}: {name}",
                'message': message,
                'priority': 'high',
                'read': False,
                'product_id': str(p_id),
                'product_name': name,
                'product_image': image,
                'price': price,
                'old_price': old_price,
                'store_name': store_name,
                'offer_name': offer,
                'created_at': datetime.utcnow()
            }
            
            db.notifications.insert_one(notification)
            count += 1
            
    print(f"Created {count} new notifications.")

if __name__ == "__main__":
    clear_and_regenerate()
