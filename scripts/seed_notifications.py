"""
SEED NOTIFICATIONS SCRIPT
Generates rich, realistic notifications based on actual products in the database.
Also creates a system "Welcome" message for all users.
"""

import os
import sys
import random
from datetime import datetime
from bson import ObjectId
from dotenv import load_dotenv

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.db import get_db

load_dotenv()

def seed_notifications():
    db = get_db()
    if not db:
        print("Error: Could not connect to database")
        return

    # 1. OPTIONAL: Migration for legacy data (harmless to run if no old data exists)
    print("Ensuring notification types are consistent...")
    db.notifications.update_many({"type": "deal"}, {"$set": {"type": "deal_alert"}})
    db.notifications.update_many({"type": "new_deal"}, {"$set": {"type": "deal_alert"}})

    # 2. Fetch REAL products from the database
    products = list(db.products.find().limit(20))
    if not products:
        print("No products found in DB. Please run product import first.")
        # Create at least one system message so the user sees something
        products = []

    # 3. Get all users
    users = list(db.users.find({}, {"email": 1}))
    if not users:
        print("No users found. Creating a demo user...")
        # (Optional: create a user logic, but lets just skip)
        return

    print(f"Generating notifications for {len(users)} users...")
    count = 0

    for user in users:
        email = user.get("email")
        if not email: continue

        # A. System Welcome Message (idempotent-ish: check if exists or just add)
        # We just add it. User can delete it.
        welcome = {
            "user_email": email,
            "type": "system",
            "title": "Welcome to Smart Grocery!",
            "message": "We will notify you here about price drops and new deals.",
            "priority": "normal",
            "read": False,
            "created_at": datetime.utcnow()
        }
        db.notifications.insert_one(welcome)
        count += 1

        # B. Generate Rich Product Notifications
        if products:
            # Shuffle products to make it look interesting
            random.shuffle(products)
            selected_products = products[:3] 

            for p in selected_products:
                # Extract info
                p_id = p["_id"]
                name = p.get("name", "Unknown Product")
                image = p.get("image")
                
                # Handle price safely (could be string or number)
                raw_price = p.get("price_val") or p.get("price")
                try: 
                    price = float(str(raw_price).replace("", "").replace("$", "")) if raw_price else 0
                except: 
                    price = 0
                
                # Find a store name
                store_name = "Supermarket"
                if p.get("stores") and len(p["stores"]) > 0:
                    store_name = p["stores"][0].get("store", store_name)
                
                # Randomize Offer Type
                offer_types = ["20% OFF", "Price Drop", "New Arrival", "Best Value"]
                offer = random.choice(offer_types)
                
                notif_type = "deal_alert"
                old_price = None
                
                if offer == "Price Drop":
                    notif_type = "price_drop"
                    old_price = price * 1.2 if price else 0
                    message = f"Price dropped to {price:.2f}! Was {old_price:.2f}."
                else:
                    message = f"Check out this great deal on {name} at {store_name}."

                notification = {
                    "user_email": email,
                    "type": notif_type,
                    "title": f"{offer}: {name}",
                    "message": message,
                    "priority": "high",
                    "read": False,
                    "product_id": str(p_id), # Link to REAL product
                    
                    # Rich Card Fields
                    "product_name": name,
                    "product_image": image,
                    "price": price,
                    "old_price": old_price,
                    "store_name": store_name,
                    "offer_name": offer,
                    
                    "created_at": datetime.utcnow()
                }
                
                db.notifications.insert_one(notification)
                count += 1

    print(f"Successfully generated {count} notifications.")

if __name__ == "__main__":
    seed_notifications()

