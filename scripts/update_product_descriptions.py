#!/usr/bin/env python3
"""
Script to update product descriptions in MongoDB with better, more detailed descriptions.
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

def generate_description(product_name, category):
    """Generate a detailed 2-sentence description for a product."""
    name_lower = product_name.lower()
    
    # Dairy products
    if category == 'Dairy':
        if 'egg' in name_lower:
            return "Fresh farm eggs packed with protein and essential nutrients for your daily meals. Perfect for breakfast, baking, or adding to your favorite recipes."
        elif 'milk' in name_lower and '3.5' in name_lower:
            return "Full-fat fresh milk with 3.5% fat content, offering rich taste and creamy texture. Excellent source of calcium and vitamin D for strong bones and overall health."
        elif 'almond milk' in name_lower:
            return "Plant-based dairy alternative made from premium almonds, naturally lactose-free and vegan-friendly. Perfect for those with dietary restrictions or seeking a lighter milk option."
        elif 'oat milk' in name_lower:
            return "Creamy oat-based milk alternative with a naturally sweet flavor and smooth consistency. Great for coffee, smoothies, and cereal while being environmentally sustainable."
        elif 'yogurt' in name_lower and 'greek' in name_lower:
            return "Thick and creamy Greek yogurt with high protein content and rich, tangy flavor. Perfect for breakfast bowls, smoothies, or as a healthy snack throughout the day."
        elif 'yogurt drink' in name_lower:
            return "Refreshing drinkable yogurt packed with probiotics and nutrients for digestive health. Convenient on-the-go option for a quick and healthy snack."
        elif 'cheddar cheese' in name_lower:
            return "Sharp and flavorful cheddar cheese aged to perfection with a firm texture. Ideal for sandwiches, burgers, cheese boards, or melting over your favorite dishes."
        elif 'mozzarella cheese' in name_lower:
            return "Soft and creamy mozzarella cheese with mild flavor and excellent melting properties. Essential for pizzas, caprese salads, and Italian-inspired dishes."
    
    # Produce - Fruits
    elif category == 'Produce':
        if 'banana' in name_lower:
            return "Sweet and naturally creamy bananas rich in potassium and natural energy. Perfect for snacking, smoothies, or adding to your morning cereal and oatmeal."
        elif 'apple' in name_lower:
            return "Crisp and juicy apples with a perfect balance of sweetness and tartness. Great for snacking, baking pies, or adding crunch to salads."
        elif 'orange' in name_lower:
            return "Fresh and juicy oranges bursting with vitamin C and natural sweetness. Perfect for fresh juice, snacking, or adding zest to your recipes."
        elif 'strawberr' in name_lower:
            return "Sweet and fragrant strawberries packed with antioxidants and vitamin C. Delicious fresh, in desserts, or blended into smoothies and yogurt."
        elif 'blueberr' in name_lower:
            return "Plump and sweet blueberries loaded with antioxidants and nutrients. Perfect for breakfast bowls, baking, or enjoying as a healthy snack."
        elif 'raspberr' in name_lower:
            return "Delicate and tart raspberries with vibrant flavor and high fiber content. Excellent for desserts, breakfast toppings, or fresh snacking."
        elif 'blackberr' in name_lower:
            return "Juicy and slightly tart blackberries rich in vitamins and antioxidants. Great for jams, pies, smoothies, or eating fresh."
        elif 'grape' in name_lower:
            return "Sweet and refreshing grapes perfect for snacking or adding to fruit salads. Naturally hydrating and packed with vitamins and minerals."
        elif 'avocado' in name_lower:
            return "Creamy and nutritious avocados rich in healthy fats and fiber. Perfect for guacamole, toast, salads, or adding creaminess to smoothies."
        elif 'pear' in name_lower:
            return "Sweet and juicy pears with smooth texture and delicate flavor. Excellent for fresh eating, baking, or pairing with cheese."
        elif 'peach' in name_lower:
            return "Succulent and fragrant peaches with natural sweetness and velvety skin. Perfect for eating fresh, grilling, or baking into cobblers and pies."
        elif 'mango' in name_lower:
            return "Tropical and sweet mangoes with vibrant flavor and smooth flesh. Delicious fresh, in smoothies, salsas, or desserts."
        elif 'pineapple' in name_lower:
            return "Sweet and tangy pineapple with tropical flavor and juicy texture. Great for grilling, smoothies, or adding to savory dishes."
        elif 'watermelon' in name_lower:
            return "Refreshing and sweet watermelon perfect for hot summer days. Hydrating and naturally sweet, ideal for snacking or fruit salads."
        elif 'lemon' in name_lower:
            return "Bright and zesty lemons packed with vitamin C and fresh citrus flavor. Essential for cooking, baking, drinks, and adding tang to dishes."
        elif 'lime' in name_lower:
            return "Tart and aromatic limes with bold citrus flavor. Perfect for marinades, cocktails, Mexican cuisine, and adding brightness to recipes."
        elif 'kiwi' in name_lower:
            return "Tangy and sweet kiwis with vibrant green flesh and unique flavor. Rich in vitamin C and perfect for fresh eating or smoothies."
        elif 'plum' in name_lower:
            return "Sweet and juicy plums with smooth skin and rich flavor. Delicious fresh, in jams, or baked into tarts and desserts."
        # Vegetables
        elif 'tomato' in name_lower:
            return "Ripe and flavorful tomatoes perfect for salads, sauces, and sandwiches. Rich in vitamins and antioxidants with versatile culinary uses."
        elif 'spinach' in name_lower:
            return "Fresh and nutritious spinach leaves packed with iron and vitamins. Perfect for salads, smoothies, sautéing, or adding to pasta dishes."
        elif 'lettuce' in name_lower:
            return "Crisp and fresh lettuce leaves ideal for salads and sandwiches. Light and refreshing with a mild flavor that pairs well with any dressing."
        elif 'kale' in name_lower:
            return "Nutrient-dense kale with hearty texture and earthy flavor. Excellent for salads, smoothies, or sautéing as a healthy side dish."
        elif 'cabbage' in name_lower:
            return "Crunchy and versatile cabbage perfect for slaws, stir-fries, and fermentation. Long-lasting vegetable with high vitamin C content."
        elif 'cucumber' in name_lower:
            return "Cool and refreshing cucumbers with crisp texture and mild flavor. Perfect for salads, pickles, or infusing water."
        elif 'carrot' in name_lower:
            return "Sweet and crunchy carrots rich in beta-carotene and fiber. Great for snacking, roasting, or adding to soups and stews."
        elif 'potato' in name_lower:
            return "Versatile and hearty potatoes perfect for countless cooking methods. Comfort food staple that's filling and pairs well with any meal."
        elif 'onion' in name_lower:
            return "Flavorful and aromatic onions essential for cooking and adding depth to dishes. Versatile vegetable that forms the base of countless recipes."
        elif 'garlic' in name_lower:
            return "Pungent and aromatic garlic bulbs that add bold flavor to any dish. Health-boosting ingredient essential in cuisines worldwide."
        elif 'broccoli' in name_lower:
            return "Nutritious broccoli florets packed with vitamins and fiber. Delicious steamed, roasted, or stir-fried as a healthy side dish."
        elif 'cauliflower' in name_lower:
            return "Mild and versatile cauliflower perfect for roasting, mashing, or rice alternatives. Nutrient-rich vegetable with endless culinary possibilities."
        elif 'mushroom' in name_lower:
            return "Earthy and savory mushrooms that add umami flavor to dishes. Perfect for sautéing, grilling, or adding to pasta and risotto."
        elif 'zucchini' in name_lower:
            return "Tender and mild zucchini ideal for grilling, sautéing, or spiralizing into noodles. Light and healthy vegetable perfect for summer dishes."
        elif 'pepper' in name_lower or 'bell' in name_lower:
            return "Crisp and colorful bell peppers with sweet flavor and crunchy texture. Perfect for stuffing, grilling, or adding to stir-fries and salads."
        elif 'corn' in name_lower:
            return "Sweet and tender corn with natural sugars and satisfying crunch. Delicious grilled, boiled, or added to salads and salsas."
        elif 'green beans' in name_lower:
            return "Fresh and crisp green beans perfect for steaming or sautéing. Classic side dish that's nutritious and pairs well with any main course."
    
    # Meat & Seafood
    elif category == 'Meat':
        if 'chicken breast' in name_lower:
            return "Lean and tender chicken breast perfect for grilling, baking, or stir-frying. High-protein, low-fat option ideal for healthy meal preparation."
        elif 'ground beef' in name_lower:
            return "Versatile ground beef perfect for burgers, tacos, meatballs, and pasta sauces. Essential ingredient for countless comfort food recipes."
        elif 'salmon' in name_lower:
            return "Fresh salmon fillet rich in omega-3 fatty acids and premium quality protein. Delicious grilled, baked, or pan-seared with a crispy skin."
        elif 'shrimp' in name_lower:
            return "Sweet and succulent shrimp perfect for quick-cooking dishes and seafood favorites. Versatile protein that pairs well with pastas, stir-fries, and grilling."
    
    # Bakery
    elif category == 'Bakery':
        if 'bread roll' in name_lower or 'roll' in name_lower:
            return "Soft and fluffy bread rolls perfect for sandwiches, burgers, or dinner accompaniment. Freshly baked with a golden crust and tender interior."
        elif 'baguette' in name_lower:
            return "Classic French baguette with crispy crust and soft, airy interior. Perfect for sandwiches, bruschetta, or serving alongside soups and cheeses."
        elif 'croissant' in name_lower:
            return "Buttery and flaky croissants with delicate layers and rich flavor. Perfect for breakfast, brunch, or as an elegant pastry treat."
        elif 'cinnamon' in name_lower:
            return "Sweet and aromatic cinnamon rolls with gooey icing and warm spices. Irresistible breakfast pastry perfect for special mornings or dessert."
    
    # Pantry
    elif category == 'Pantry':
        if 'olive oil' in name_lower:
            return "Extra virgin olive oil cold-pressed from premium olives for superior flavor and quality. Perfect for cooking, drizzling, and salad dressings with heart-healthy benefits."
        elif 'rice' in name_lower and 'basmati' in name_lower:
            return "Aromatic basmati rice with long grains and delicate fragrance. Perfect for Indian cuisine, pilafs, and as a side for curries and stir-fries."
        elif 'pasta' in name_lower and 'penne' in name_lower:
            return "Classic penne pasta with tube shape perfect for holding sauces. Versatile base for Italian dishes, baked pastas, and quick weeknight meals."
        elif 'sauce' in name_lower and 'tomato' in name_lower:
            return "Rich tomato basil sauce made with ripe tomatoes and fragrant herbs. Quick and convenient base for pasta, pizza, or Italian-inspired dishes."
        elif 'peanut butter' in name_lower:
            return "Creamy peanut butter packed with protein and natural peanut flavor. Perfect for sandwiches, smoothies, baking, or eating straight from the jar."
        elif 'ketchup' in name_lower:
            return "Classic tomato ketchup with sweet and tangy flavor. Essential condiment for burgers, fries, and countless American favorites."
        elif 'mustard' in name_lower:
            return "Tangy yellow mustard with bold flavor and smooth consistency. Classic condiment perfect for hot dogs, sandwiches, and marinades."
        elif 'tapenade' in name_lower:
            return "Rich olive tapenade with bold Mediterranean flavors and savory notes. Perfect spread for crackers, sandwiches, or as a pasta accompaniment."
    
    # Frozen
    elif category == 'Frozen':
        if 'pizza' in name_lower:
            return "Frozen Margherita pizza with authentic Italian flavors and quality ingredients. Quick and convenient meal ready in minutes straight from your oven."
        elif 'berries' in name_lower:
            return "Frozen mixed berries picked at peak ripeness and flash-frozen for freshness. Perfect for smoothies, baking, or breakfast bowls year-round."
        elif 'fries' in name_lower or 'french fries' in name_lower:
            return "Crispy frozen French fries that bake to golden perfection. Classic side dish that's convenient and always satisfying."
        elif 'nugget' in name_lower:
            return "Breaded chicken nuggets with crispy coating and tender interior. Kid-friendly favorite that's quick to prepare for any meal."
    
    # Beverages
    elif category == 'Beverages':
        if 'juice' in name_lower and 'orange' in name_lower:
            return "Fresh-tasting orange juice packed with vitamin C and natural citrus flavor. Refreshing breakfast beverage or anytime pick-me-up."
        elif 'soda' in name_lower or 'cola' in name_lower:
            return "Classic cola soda with refreshing carbonation and iconic flavor. Perfect for parties, meals, or enjoying as a cold beverage."
        elif 'tea' in name_lower and 'lemon' in name_lower:
            return "Refreshing lemon iced tea with perfect balance of tea and citrus. Thirst-quenching beverage ideal for hot days or meals."
        elif 'energy' in name_lower:
            return "Energy drink formulated to boost alertness and provide quick energy. Perfect for active lifestyles, studying, or overcoming afternoon slumps."
    
    # Snacks
    elif category == 'Snacks':
        if 'chocolate' in name_lower or 'reese' in name_lower:
            return "Delicious chocolate bar with rich cocoa flavor and satisfying sweetness. Perfect treat for chocolate lovers or sharing with friends."
        elif 'chip' in name_lower:
            return "Crispy salted potato chips with satisfying crunch and savory flavor. Classic snack perfect for parties, lunches, or anytime cravings."
        elif 'granola' in name_lower:
            return "Nutritious granola bars packed with whole grains, nuts, and natural sweetness. Convenient and healthy snack for busy lifestyles and on-the-go energy."
    
    # Household
    elif category == 'Household':
        if 'toilet paper' in name_lower:
            return "Soft and absorbent toilet paper for everyday household use. Essential bathroom staple with reliable quality and comfort."
    
    # Baby food
    elif category == 'Baby food':
        if 'puree' in name_lower:
            return "Nutritious baby fruit puree made with natural ingredients and no added sugars. Perfect first food for introducing fruits to your little one."
        elif 'diaper' in name_lower:
            return "Soft and absorbent baby diapers designed for comfort and leak protection. Reliable choice for keeping your baby dry and happy throughout the day."
        elif 'formula' in name_lower:
            return "Complete infant formula with essential nutrients for healthy growth and development. Carefully formulated to support your baby's nutritional needs."
        elif 'wipes' in name_lower:
            return "Gentle baby wipes perfect for diaper changes and cleaning sensitive skin. Soft and moisturizing for delicate baby care."
    
    # Fast Food & To Go
    elif category == 'Fast Food & To Go':
        if 'wrap' in name_lower:
            return "Delicious chicken Caesar wrap with fresh greens, parmesan, and creamy dressing. Quick and satisfying meal perfect for lunch on the go."
    
    # Generic fallback
    return f"High-quality {product_name} perfect for your everyday needs. Fresh and carefully selected to ensure the best taste and value for your family."

def update_descriptions():
    """Update all product descriptions in the database."""
    db = get_db()
    if db is None:
        return False
    
    try:
        products_collection = db.products
        
        # Find all products
        all_products = list(products_collection.find({}))
        
        print(f"\nFound {len(all_products)} products to update")
        
        updated_count = 0
        
        for product in all_products:
            product_id = product.get('_id')
            product_name = product.get('name', 'Unknown')
            category = product.get('category', '')
            old_desc = product.get('description', '')
            
            # Generate new description
            new_desc = generate_description(product_name, category)
            
            # Only update if description is different
            if new_desc != old_desc:
                print(f"\n  Updating: {product_name}")
                print(f"    Old: {old_desc}")
                print(f"    New: {new_desc}")
                
                products_collection.update_one(
                    {'_id': product_id},
                    {'$set': {'description': new_desc}}
                )
                updated_count += 1
        
        print(f"\n✓ Updated {updated_count} product descriptions")
        return True
        
    except Exception as e:
        print(f"Error updating descriptions: {e}")
        return False

def main():
    print("=" * 60)
    print("Smart Grocery: Product Description Updater")
    print("=" * 60)
    
    success = update_descriptions()
    
    if success:
        print("\n✓ All product descriptions have been updated!")
    else:
        print("\n✗ Failed to update product descriptions")
        sys.exit(1)

if __name__ == '__main__':
    main()
