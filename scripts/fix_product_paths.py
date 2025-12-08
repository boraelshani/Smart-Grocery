#!/usr/bin/env python3
"""
Script to fix/clean up old product category paths in MongoDB.
Removes the old "meat,eggs and fish" path and updates products to use just "category".
"""

import os
import sys
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

try:
    from pymongo import MongoClient
    import certifi
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

def fix_product_paths():
    """Fix old category paths in products."""
    db = get_db()
    if db is None:
        return False
    
    try:
        products_collection = db.products
        
        # Find products with the old category_path containing "meat,eggs and fish"
        old_products = list(products_collection.find({
            'category_path': {'$exists': True, '$type': 'array'}
        }))
        
        print(f"\nFound {len(old_products)} products with category_path")
        
        # For each product, normalize the path
        fixed_count = 0
        updated_count = 0
        
        for product in old_products:
            old_path = product.get('category_path', [])
            category = product.get('category', '')
            product_id = product.get('_id', product.get('id', 'Unknown'))
            product_name = product.get('name', 'Unknown')
            
            # If category_path contains the old category, rebuild it cleanly
            if any('meat' in str(part).lower() or 'eggs' in str(part).lower() or 'fish' in str(part).lower() 
                   for part in old_path):
                print(f"\n  Fixing: {product_name}")
                print(f"    Old path: {old_path}")
                print(f"    Category: {category}")
                
                # Create a clean path from just the category
                if category:
                    new_path = [category]
                    products_collection.update_one(
                        {'_id': product_id},
                        {'$set': {'category_path': new_path}}
                    )
                    print(f"    New path: {new_path}")
                    fixed_count += 1
                else:
                    # If no category, remove the path entirely
                    products_collection.update_one(
                        {'_id': product_id},
                        {'$unset': {'category_path': ''}}
                    )
                    print(f"    Removed category_path (no category found)")
                    fixed_count += 1
            else:
                # Path looks OK, but verify it matches category
                if category and (not old_path or old_path != [category]):
                    print(f"\n  Updating: {product_name}")
                    print(f"    Old path: {old_path}")
                    new_path = [category]
                    products_collection.update_one(
                        {'_id': product_id},
                        {'$set': {'category_path': new_path}}
                    )
                    print(f"    New path: {new_path}")
                    updated_count += 1
        
        print(f"\n✓ Fixed {fixed_count} products with old paths")
        print(f"✓ Updated {updated_count} products to match category")
        return True
        
    except Exception as e:
        print(f"Error fixing product paths: {e}")
        return False

def main():
    print("=" * 60)
    print("Smart Grocery: Product Path Fixer")
    print("=" * 60)
    
    success = fix_product_paths()
    
    if success:
        print("\n✓ All product paths have been updated!")
        return 0
    else:
        print("\n✗ Error updating product paths")
        return 1

if __name__ == '__main__':
    sys.exit(main())
