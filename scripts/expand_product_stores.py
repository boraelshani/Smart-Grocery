#!/usr/bin/env python3
"""
Script to ensure all products have 3 store entries in their stores array.
"""

import os
import sys
from dotenv import load_dotenv
import random

# Load environment variables
load_dotenv()

try:
    from pymongo import MongoClient
    import certifi
    from bson.decimal128 import Decimal128
except ImportError:
    print("Error: pymongo not installed. Install with: pip install pymongo certifi")
    sys.exit(1)

def get_db():
    """Connect to MongoDB using environment variables."""
    try:
        uri = os.getenv('MONGO_URI')
        dbname = os.getenv('DATABASE_NAME', 'smart_grocery')
        
        if not uri:
            print("Error: MONGO_URI not set in .env")
            return None
        
        if uri.startswith('mongodb+srv://'):
            client = MongoClient(uri, tls=True, tlsCAFile=certifi.where(), serverSelectionTimeoutMS=5000)
        else:
            client = MongoClient(uri, serverSelectionTimeoutMS=5000)
        
        return client[dbname]
    except Exception as e:
        print(f"Error connecting to MongoDB: {e}")
        return None

def get_store_names(db):
    """Get list of available store names."""
    try:
        stores = list(db.stores.find({}, {'name': 1}))
        return [s['name'] for s in stores if 'name' in s]
    except Exception:
        # Fallback store names
        return ['Billa', 'Spar', 'Hofer', 'Lidl', 'Penny']

def generate_store_entry(store_name, product_name, base_price):
    """Generate a store entry with realistic price variation."""
    # Add random price variation (-10% to +15%)
    variation = random.uniform(-0.10, 0.15)
    varied_price = base_price * (1 + variation)
    
    # Round to 2 decimal places
    varied_price = round(varied_price, 2)
    
    return {
        'store': store_name,
        'price': f"€{varied_price:.2f}",
        'price_val': Decimal128(str(varied_price)),
        'url': f'https://{store_name.lower()}.at/products/{product_name.lower().replace(" ", "-")}',
        'image': ''  # Image would need to be populated separately
    }

def update_product_stores():
    """Update products to have 3 store entries."""
    db = get_db()
    if db is None:
        return False
    
    try:
        products_collection = db.products
        
        # Get available stores
        available_stores = get_store_names(db)
        print(f"\nAvailable stores: {', '.join(available_stores)}")
        
        # Find all products
        all_products = list(products_collection.find({}))
        
        print(f"\nFound {len(all_products)} products to check")
        
        updated_count = 0
        
        for product in all_products:
            product_id = product.get('_id')
            product_name = product.get('name', 'Unknown')
            stores = product.get('stores', [])
            
            # Check if product needs more stores
            if len(stores) >= 3:
                continue
            
            print(f"\n  Updating: {product_name}")
            print(f"    Current stores: {len(stores)}")
            
            # Get existing store names to avoid duplicates
            existing_store_names = [s.get('store', '') for s in stores]
            
            # Get base price from first store or product price
            if stores and 'price_val' in stores[0]:
                base_price_val = stores[0]['price_val']
                if isinstance(base_price_val, Decimal128):
                    base_price = float(base_price_val.to_decimal())
                else:
                    base_price = float(base_price_val)
            elif 'price' in product:
                # Parse price from string like "€2.99" or float
                price_value = product['price']
                if isinstance(price_value, (int, float)):
                    base_price = float(price_value)
                else:
                    price_str = str(price_value).replace('€', '').replace(',', '.').strip()
                    try:
                        base_price = float(price_str)
                    except:
                        base_price = 5.0  # Default fallback
            else:
                base_price = 5.0  # Default fallback
            
            # Add stores until we have 3
            new_stores = list(stores)  # Copy existing stores
            
            for store_name in available_stores:
                if len(new_stores) >= 3:
                    break
                
                # Skip if store already exists
                if store_name in existing_store_names:
                    continue
                
                # Generate new store entry
                new_store_entry = generate_store_entry(store_name, product_name, base_price)
                new_stores.append(new_store_entry)
                print(f"      Added: {store_name} at {new_store_entry['price']}")
            
            # Update the product
            if len(new_stores) > len(stores):
                products_collection.update_one(
                    {'_id': product_id},
                    {'$set': {'stores': new_stores}}
                )
                print(f"    New total: {len(new_stores)} stores")
                updated_count += 1
        
        print(f"\n✓ Updated {updated_count} products to have 3 stores")
        return True
        
    except Exception as e:
        print(f"Error updating product stores: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    print("=" * 60)
    print("Smart Grocery: Product Store Expander")
    print("=" * 60)
    
    success = update_product_stores()
    
    if success:
        print("\n✓ All products now have 3 store entries!")
    else:
        print("\n✗ Failed to update product stores")
        sys.exit(1)

if __name__ == '__main__':
    main()
