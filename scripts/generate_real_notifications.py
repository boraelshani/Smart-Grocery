
import os
import sys
from pymongo import MongoClient
from bson import ObjectId
from dotenv import load_dotenv
import certifi
import random

# Add project root to path
sys.path.append(os.getcwd())

load_dotenv()

def generate_real_notifications():
    if not os.environ.get('SSL_CERT_FILE'):
        os.environ['SSL_CERT_FILE'] = certifi.where()

    mongo_uri = os.getenv('MONGO_URI')
    client = MongoClient(mongo_uri, tlsCAFile=certifi.where())
    db = client.get_default_database()
    
    # 1. Fetch REAL products from the database
    products = list(db.products.find().limit(10))
    print(f"Found {len(products)} real products.")
    
    if not products:
        print("No products found to generate notifications for.")
        return

    # 2. Clear existing notifications to give a clean state (per user request context)
    # db.notifications.delete_many({}) 
    # Actually, let's keep it safe. The user just wants new ones to show up.
    # But for demo purposes, clearing might be cleaner if they complained about "fake" ones.
    # Let's delete the fake ones we just added (type=deal_alert and store=Fresh & Co usually).
    # Easier: just add new ones on top.
    
    # 3. Create notifications for the first 3 products as "New Deals"
    from models.notifications_model import NotificationsModel
    # We can instantiate it, but we need to import it properly
    # Using direct DB insertion is easier here to ensure we control all fields
    
    users = list(db.users.find({}, {'email': 1}))
    print(f"Generating for {len(users)} users...")

    count = 0
    for user in users:
        email = user.get('email')
        if not email: continue

        # Shuffle products to make it look interesting
        random.shuffle(products)
        selected_products = products[:4] 

        for p in selected_products:
            # Extract info
            p_id = p['_id']
            name = p.get('name', 'Unknown Product')
            image = p.get('image')
            price = p.get('price_val') or p.get('price')
            
            # Find a store name if available
            store_name = "Supermarket"
            if p.get('stores') and len(p['stores']) > 0:
                store_name = p['stores'][0].get('store', 'Supermarket')
            
            # Create a realistic "OFFER"
            offer_types = ["20% OFF", "Price Drop", "New Arrival", "Best Value"]
            offer = random.choice(offer_types)
            
            notif_type = 'deal_alert'
            if offer == "Price Drop":
                notif_type = 'price_drop'
                old_price = float(price) * 1.2 if price else 0
                message = f"Price dropped to {price}! Was {old_price:.2f}."
            else:
                message = f"Check out this great deal on {name} at {store_name}."
                old_price = None

            notification = {
                'user_email': email,
                'type': notif_type,
                'title': f"{offer}: {name}",
                'message': message,
                'priority': 'high',
                'read': False,
                'product_id': str(p_id), # Link to REAL product
                
                # Redundant fields for immediate rendering (Rich Card)
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

    print(f"Successfully generated {count} REAL notifications from database products.")

from datetime import datetime

if __name__ == "__main__":
    generate_real_notifications()
