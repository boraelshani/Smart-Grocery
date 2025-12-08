#!/usr/bin/env python3
"""
Script to fix product category paths to proper hierarchical structure.
Creates appropriate hierarchical paths based on actual product categories.
Paths end with specific product subcategories (e.g., ['Dairy', 'Milk & Cream']).
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



def get_category_path(product_name, category):
    """Determine the appropriate category path for a product based on category and name.
    Format: ['Products', 'Category', 'Subcategory', 'Specific Type' (optional)]
    """
    name_lower = product_name.lower()
    
    # Dairy products
    if category == 'Dairy':
        if 'egg' in name_lower:
            return ['Products', 'Dairy', 'Eggs']
        elif any(x in name_lower for x in ['milk', 'cream']) and not any(x in name_lower for x in ['almond', 'oat', 'soy']):
            return ['Products', 'Dairy', 'Milk']
        elif any(x in name_lower for x in ['almond', 'oat', 'soy']) and 'milk' in name_lower:
            return ['Products', 'Dairy', 'Alternatives']
        elif 'yogurt' in name_lower or 'yoghurt' in name_lower:
            return ['Products', 'Dairy', 'Yogurt']
        elif 'cheese' in name_lower:
            # Check for specific cheese types for 4-level paths
            if 'cheddar' in name_lower:
                return ['Products', 'Dairy', 'Cheese', 'Cheddar']
            elif 'mozzarella' in name_lower:
                return ['Products', 'Dairy', 'Cheese', 'Mozzarella']
            else:
                return ['Products', 'Dairy', 'Cheese']
        elif 'butter' in name_lower and 'peanut' not in name_lower:
            return ['Products', 'Dairy', 'Butter']
        else:
            return ['Products', 'Dairy']
    
    # Produce
    elif category == 'Produce':
        # Specific fruits
        if 'banana' in name_lower:
            return ['Products', 'Produce', 'Fruits', 'Bananas']
        elif 'apple' in name_lower:
            return ['Products', 'Produce', 'Fruits', 'Apples']
        elif 'orange' in name_lower:
            return ['Products', 'Produce', 'Fruits', 'Oranges']
        elif 'strawberr' in name_lower:
            return ['Products', 'Produce', 'Fruits', 'Berries']
        elif 'blueberr' in name_lower or 'raspberr' in name_lower or 'blackberr' in name_lower:
            return ['Products', 'Produce', 'Fruits', 'Berries']
        elif 'grape' in name_lower:
            return ['Products', 'Produce', 'Fruits', 'Grapes']
        elif any(x in name_lower for x in ['avocado', 'pear', 'peach', 'mango', 'pineapple', 
                                            'watermelon', 'lemon', 'lime', 'kiwi', 'plum']):
            return ['Products', 'Produce', 'Fruits']
        # Vegetables
        elif 'tomato' in name_lower:
            return ['Products', 'Produce', 'Vegetables', 'Tomatoes']
        elif any(x in name_lower for x in ['lettuce', 'spinach', 'kale', 'cabbage']):
            return ['Products', 'Produce', 'Vegetables', 'Leafy Greens']
        elif 'potato' in name_lower:
            return ['Products', 'Produce', 'Vegetables', 'Potatoes']
        elif 'onion' in name_lower:
            return ['Products', 'Produce', 'Vegetables', 'Onions']
        elif any(x in name_lower for x in ['pepper', 'bell']):
            return ['Products', 'Produce', 'Vegetables', 'Peppers']
        else:
            return ['Products', 'Produce', 'Vegetables']
    
    # Meat (was "Sausage, meat, eggs & fish")
    elif category == 'Meat':
        if 'chicken' in name_lower:
            if 'breast' in name_lower:
                return ['Products', 'Meat', 'Poultry', 'Chicken Breast']
            elif 'nugget' in name_lower:
                return ['Products', 'Meat', 'Poultry', 'Chicken Nuggets']
            else:
                return ['Products', 'Meat', 'Poultry']
        elif 'beef' in name_lower or 'ground' in name_lower:
            return ['Products', 'Meat', 'Beef']
        elif 'pork' in name_lower or 'bacon' in name_lower or 'ham' in name_lower:
            return ['Products', 'Meat', 'Pork']
        elif 'sausage' in name_lower:
            return ['Products', 'Meat', 'Sausage']
        elif 'salmon' in name_lower:
            return ['Products', 'Meat', 'Fish', 'Salmon']
        elif 'shrimp' in name_lower:
            return ['Products', 'Meat', 'Seafood', 'Shrimp']
        elif any(x in name_lower for x in ['fish', 'tuna', 'cod']):
            return ['Products', 'Meat', 'Fish']
        elif any(x in name_lower for x in ['seafood', 'crab', 'lobster']):
            return ['Products', 'Meat', 'Seafood']
        else:
            return ['Products', 'Meat']
    
    # Bakery
    elif category == 'Bakery':
        if any(x in name_lower for x in ['bread', 'baguette']) and 'roll' not in name_lower:
            return ['Products', 'Bakery', 'Bread']
        elif 'roll' in name_lower:
            return ['Products', 'Bakery', 'Rolls']
        elif any(x in name_lower for x in ['croissant', 'cinnamon', 'pastry', 'danish']):
            return ['Products', 'Bakery', 'Pastries']
        elif any(x in name_lower for x in ['cake', 'muffin', 'donut']):
            return ['Products', 'Bakery', 'Sweets']
        else:
            return ['Products', 'Bakery']
    
    # Pantry
    elif category == 'Pantry':
        if 'oil' in name_lower:
            if 'olive' in name_lower:
                return ['Products', 'Pantry', 'Oils', 'Olive Oil']
            else:
                return ['Products', 'Pantry', 'Oils']
        elif 'rice' in name_lower:
            return ['Products', 'Pantry', 'Grains', 'Rice']
        elif 'pasta' in name_lower:
            return ['Products', 'Pantry', 'Grains', 'Pasta']
        elif any(x in name_lower for x in ['sauce', 'ketchup', 'mustard']):
            return ['Products', 'Pantry', 'Condiments']
        elif any(x in name_lower for x in ['peanut butter', 'tapenade', 'jam', 'spread']):
            return ['Products', 'Pantry', 'Spreads']
        else:
            return ['Products', 'Pantry']
    
    # Frozen
    elif category == 'Frozen':
        if 'pizza' in name_lower:
            return ['Products', 'Frozen', 'Meals', 'Pizza']
        elif 'nugget' in name_lower:
            return ['Products', 'Frozen', 'Meals']
        elif any(x in name_lower for x in ['berry', 'berries']):
            return ['Products', 'Frozen', 'Fruits']
        elif 'fries' in name_lower or 'french fries' in name_lower:
            return ['Products', 'Frozen', 'Sides', 'Fries']
        elif any(x in name_lower for x in ['vegetable', 'veggie']):
            return ['Products', 'Frozen', 'Vegetables']
        else:
            return ['Products', 'Frozen']
    
    # Beverages
    elif category == 'Beverages':
        if 'juice' in name_lower:
            if 'orange' in name_lower:
                return ['Products', 'Beverages', 'Juices', 'Orange Juice']
            else:
                return ['Products', 'Beverages', 'Juices']
        elif 'soda' in name_lower or 'cola' in name_lower:
            return ['Products', 'Beverages', 'Soft Drinks']
        elif 'tea' in name_lower:
            return ['Products', 'Beverages', 'Tea']
        elif 'energy' in name_lower:
            return ['Products', 'Beverages', 'Energy Drinks']
        elif any(x in name_lower for x in ['water', 'sparkling']):
            return ['Products', 'Beverages', 'Water']
        else:
            return ['Products', 'Beverages']
    
    # Snacks
    elif category == 'Snacks':
        if any(x in name_lower for x in ['chocolate', 'candy', 'reese']):
            return ['Products', 'Snacks', 'Chocolate & Candy']
        elif 'chip' in name_lower or 'crisp' in name_lower:
            return ['Products', 'Snacks', 'Chips']
        elif 'granola' in name_lower or 'bar' in name_lower:
            return ['Products', 'Snacks', 'Bars']
        elif any(x in name_lower for x in ['cookie', 'biscuit']):
            return ['Products', 'Snacks', 'Cookies']
        else:
            return ['Products', 'Snacks']
    
    # Household
    elif category == 'Household':
        if 'paper' in name_lower or 'toilet' in name_lower:
            return ['Products', 'Household', 'Paper Products']
        elif 'clean' in name_lower or 'detergent' in name_lower:
            return ['Products', 'Household', 'Cleaning']
        else:
            return ['Products', 'Household']
    
    # Baby food
    elif category == 'Baby food':
        if 'puree' in name_lower or 'food' in name_lower:
            return ['Products', 'Baby food', 'Food']
        elif 'diaper' in name_lower:
            return ['Products', 'Baby food', 'Diapers']
        elif 'wipe' in name_lower:
            return ['Products', 'Baby food', 'Wipes']
        elif 'formula' in name_lower:
            return ['Products', 'Baby food', 'Formula']
        else:
            return ['Products', 'Baby food']
    
    # Fast Food & To Go
    elif category == 'Fast Food & To Go':
        if 'wrap' in name_lower:
            return ['Products', 'Fast Food & To Go', 'Wraps']
        elif 'sandwich' in name_lower:
            return ['Products', 'Fast Food & To Go', 'Sandwiches']
        else:
            return ['Products', 'Fast Food & To Go']
    
    # Fallback
    return ['Products', category] if category else ['Products']

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
    """Fix product category paths to proper hierarchical structure."""
    db = get_db()
    if db is None:
        return False
    
    try:
        products_collection = db.products
        
        # Find all products
        all_products = list(products_collection.find({}))
        
        print(f"\nFound {len(all_products)} products total")
        
        fixed_count = 0
        
        for product in all_products:
            product_id = product.get('_id')
            product_name = product.get('name', 'Unknown')
            category = product.get('category', '')
            old_path = product.get('category_path', [])
            
            # Determine the new path based on category and product name
            new_path = get_category_path(product_name, category)
            
            # Only update if path is different
            if new_path != old_path:
                if old_path:
                    print(f"\n  Updating: {product_name}")
                    print(f"    Category: {category}")
                    print(f"    Old path: {old_path}")
                    print(f"    New path: {new_path}")
                else:
                    print(f"\n  Adding path: {product_name}")
                    print(f"    Category: {category}")
                    print(f"    New path: {new_path}")
                
                if new_path:
                    products_collection.update_one(
                        {'_id': product_id},
                        {'$set': {'category_path': new_path}}
                    )
                    fixed_count += 1
                else:
                    # Remove path if no category
                    products_collection.update_one(
                        {'_id': product_id},
                        {'$unset': {'category_path': ''}}
                    )
                    fixed_count += 1
        
        print(f"\n✓ Fixed {fixed_count} products with proper category paths")
        return True
        
    except Exception as e:
        print(f"Error fixing product paths: {e}")
        return False

def main():
    print("=" * 60)
    print("Smart Grocery: Product Path Fixer (Updated)")
    print("=" * 60)
    
    success = fix_product_paths()
    
    if success:
        print("\n✓ All product paths have been updated with correct categories!")
    else:
        print("\n✗ Failed to update product paths")
        sys.exit(1)

if __name__ == '__main__':
    main()

