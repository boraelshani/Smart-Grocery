from pymongo import MongoClient
import os
from datetime import datetime, timedelta
from dotenv import load_dotenv

def seed_new_data():
    load_dotenv()
    uri = os.getenv('MONGO_URI', 'mongodb://localhost:27017/smart_grocery')
    client = MongoClient(uri)
    db = client.get_default_database()
    
    # We want these dates to be JUST NOW or in the future compared to the user join date
    now = datetime.utcnow()
    
    # Update some existing deals to be "New"
    deals_updated = db.featured_deals.update_many(
        {}, 
        {'$set': {'created_at': now}}
    )
    print(f"Updated {deals_updated.modified_count} featured deals with current timestamp.")
    
    # Update some products to be "New"
    products_updated = db.products.update_many(
        {}, 
        {'$set': {'created_at': now}}
    )
    print(f"Updated {products_updated.modified_count} products with current timestamp.")
    
    # Add a super-special "Demo Deal" that is undeniably new
    db.featured_deals.insert_one({
        'title': 'HOT UI v2.0 DEMO DEAL',
        'name': 'Premium Champagne Special',
        'price': '19.99',
        'original_price': '49.99',
        'discount_label': '60% OFF',
        'store': 'Premium Market',
        'image': 'https://images.unsplash.com/photo-1594492683522-83440733ca32?auto=format&fit=crop&q=80&w=400',
        'created_at': now + timedelta(seconds=1)
    })
    print("Added a guaranteed NEW demo deal.")

if __name__ == '__main__':
    seed_new_data()
