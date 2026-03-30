import sys
import os
import random

# Add parent directory to path to import app and utils
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, parent_dir)

from utils.db import mongo
from app import app

# A large list of realistic grocery products and their base prices
REAL_PRODUCTS = [
    # Dairy
    {"name": "Vollmilch 3.5%", "unit": "1L", "price": 1.45, "category": "Dairy", "image": "https://img.freepik.com/premium-photo/milk-carton-bottle-isolated-white_47055-680.jpg"},
    {"name": "Naturjoghurt", "unit": "500g", "price": 1.19, "category": "Dairy", "image": "https://img.freepik.com/free-photo/fresh-yogurt-bowl-with-blueberries-almonds-top-view_1150-44943.jpg"},
    {"name": "Gouda in Scheiben", "unit": "200g", "price": 2.49, "category": "Dairy", "image": "https://img.freepik.com/free-photo/pieces-delicious-cheese_144627-24701.jpg"},
    {"name": "Markenbutter", "unit": "250g", "price": 2.59, "category": "Dairy", "image": "https://img.freepik.com/free-photo/butter-isolated-white-background_144627-29369.jpg"},
    
    # Bakery
    {"name": "Kaisersemmel", "unit": "1 pc", "price": 0.39, "category": "Bakery", "image": "https://img.freepik.com/free-photo/vienna-roll-isolated_114579-22262.jpg"},
    {"name": "Toastbrot", "unit": "500g", "price": 1.89, "category": "Bakery", "image": "https://img.freepik.com/free-photo/sliced-bread-white-background_144627-22731.jpg"},
    {"name": "Schwarzbrot", "unit": "1kg", "price": 3.79, "category": "Bakery", "image": "https://img.freepik.com/free-photo/fresh-bread-loaf-isolated-white_114579-2041.jpg"},
    
    # Produce (Fruit & Veg)
    {"name": "Bio Bananen", "unit": "1kg", "price": 1.99, "category": "Produce", "image": "https://img.freepik.com/free-photo/banana-isolated-white_144627-12822.jpg"},
    {"name": "Äpfel", "unit": "1kg", "price": 2.29, "category": "Produce", "image": "https://img.freepik.com/free-photo/fresh-red-apples_144627-14256.jpg"},
    {"name": "Gurke", "unit": "1 pc", "price": 1.19, "category": "Produce", "image": "https://img.freepik.com/free-photo/fresh-cucumber-isolated-white-background_144627-14732.jpg"},
    {"name": "Tomaten", "unit": "500g", "price": 2.49, "category": "Produce", "image": "https://img.freepik.com/free-photo/tomatoes-isolated-white_144627-9097.jpg"},
    {"name": "Kartoffeln", "unit": "2kg", "price": 2.99, "category": "Produce", "image": "https://img.freepik.com/free-photo/potatoes-isolated-white_144627-26960.jpg"}, 
    
    # Meat & Pantry
    {"name": "Hühnerbrust", "unit": "500g", "price": 6.99, "category": "Meat", "image": "https://img.freepik.com/free-photo/raw-chicken-fillet-isolated-white-background_144627-41864.jpg"},
    {"name": "Faschiertes (Rind)", "unit": "500g", "price": 5.49, "category": "Meat", "image": "https://img.freepik.com/free-photo/raw-minced-meat-isolated-white-background_144627-26801.jpg"},
    {"name": "Spaghetti", "unit": "500g", "price": 1.39, "category": "Pantry", "image": "https://img.freepik.com/free-photo/raw-spaghetti-isolated-white-background_144627-17282.jpg"},
    {"name": "Olivenöl extra", "unit": "500ml", "price": 7.99, "category": "Pantry", "image": "https://img.freepik.com/free-photo/olive-oil-bottle-isolated_144627-42283.jpg"},
    
    # Drinks
    {"name": "Mineralwasser (Prickelnd)", "unit": "1.5L", "price": 0.69, "category": "Drinks", "image": "https://img.freepik.com/free-photo/water-bottle-isolated-white_144627-31569.jpg"},
    {"name": "Coca-Cola", "unit": "1.5L", "price": 1.99, "category": "Drinks", "image": "https://img.freepik.com/free-photo/coca-cola-bottle-white-background_144627-30790.jpg"},
    {"name": "Orangensaft 100%", "unit": "1L", "price": 2.19, "category": "Drinks", "image": "https://img.freepik.com/free-photo/glass-orange-juice-with-fresh-fruits_144627-27083.jpg"},
]

def populate():
    with app.app_context():
        # Clean up existing items added by this script to avoid duplicates
        mongo.db.products.delete_many({"is_demo": {"$exists": True}})
        
        insert_records = []
        for p in REAL_PRODUCTS:
            base_price = p["price"]
            
            # Form store variations based on base price
            stores = []
            
            # Core store 1: Billa (e.g. scraped)
            billa_price = base_price * 1.05
            stores.append({
                "store": "BILLA",
                "price": round(billa_price, 2)
            })
            
            # Core store 2: Spar
            spar_price = base_price * 1.02
            stores.append({
                "store": "SPAR",
                "price": round(spar_price, 2)
            })
            
            # Form full product structure
            doc = {
                "name": p["name"],
                "unit": p["unit"],
                "image": p["image"],
                "category": p["category"],
                "price": base_price, # internal reference average
                "stores": stores,
                "is_demo": True # Marked so we can easily clean it up later
            }
            insert_records.append(doc)
            
        print(f"Inserting {len(insert_records)} realistic grocery items into MongoDB...")
        if insert_records:
            mongo.db.products.insert_many(insert_records)
        print("Done! You can now view these completely new products on your website.")

if __name__ == "__main__":
    populate()
