import re
import math
from utils.db import mongo
from utils.helpers import sanitize_mongo_doc

def clean_ingredient_term(ingredient):
    """
    Cleans up a raw AI ingredient strings (e.g., '500g ripe tomatoes' -> 'tomatoes')
    by removing common quantities, numbers, and measurement units.
    """
    # Remove number prefixes (e.g., 500g, 1, 2.5, 1/2)
    cleaned = re.sub(r'^\s*[\d\.\/]+\s*', '', ingredient)
    
    # Remove common measurement units
    units = [
        "g", "kg", "ml", "l", "oz", "lb", "cup", "cups", 
        "tbsp", "tsp", "tablespoon", "teaspoon", "clove", "cloves",
        "slice", "slices", "piece", "pieces", "can", "cans", "tin", "tins",
        "dash", "pinch"
    ]
    # Use word boundaries so we don't accidentally remove 'g' from 'garlic'
    units_pattern = r'\b(?:' + '|'.join(units) + r')\b'
    cleaned = re.sub(units_pattern, '', cleaned, flags=re.IGNORECASE)
    
    # Clean up random leftover words like "of", "ripe", "fresh", "large", "small"
    fillers = ["of", "ripe", "fresh", "large", "small", "medium", "chopped", "diced", "sliced"]
    fillers_pattern = r'\b(?:' + '|'.join(fillers) + r')\b'
    cleaned = re.sub(fillers_pattern, '', cleaned, flags=re.IGNORECASE)
    
    # Remove extra whitespace
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    return cleaned

def match_ingredients_to_products(ingredients):
    """
    Takes a list of generic ingredients, cleans them, and queries the database
    for the top 3 cheapest actual store items for each ingredient.
    """
    results = []
    
    for raw_ing in ingredients:
        search_term = clean_ingredient_term(raw_ing)
        
        # We need a search term otherwise we might find everything.
        if not search_term:
            search_term = raw_ing

        # Query MongoDB for products containing this text
        # Using a regex on name or name_lower
        # NOTE: If we get zero matches, we could try falling back to just the first word
        pipeline = [
            {
                "$match": {
                    "name": {"$regex": search_term, "$options": "i"}
                }
            },
            # Sort cheapest first
            {"$sort": {"price_val": 1}},
            {"$limit": 3}
        ]
        
        matches = list(mongo.db.products.aggregate(pipeline))
        
        # If no strict match, fallback to the last main word of the ingredient
        # (e.g., if 'yellow onion' didn't match, maybe just 'onion' will)
        if not matches and ' ' in search_term:
            last_word = search_term.split()[-1]
            if len(last_word) >= 3:
                pipeline_fallback = [
                    {
                        "$match": {
                            "name": {"$regex": last_word, "$options": "i"}
                        }
                    },
                    {"$sort": {"price_val": 1}},
                    {"$limit": 3}
                ]
                matches = list(mongo.db.products.aggregate(pipeline_fallback))
        
        # Sanitize matches for frontend
        sanitized_matches = [sanitize_mongo_doc(m) for m in matches]
        
        results.append({
            "original_request": raw_ing,
            "search_term": search_term,
            "matches": sanitized_matches
        })
        
    return results

if __name__ == "__main__":
    from app import app # just to load the app and connect to Mongo
    test_ig = ["500g tomatoes", "1 yellow onion", "2 cloves garlic", "500ml vegetable broth", "olive oil"]
    print("Testing Matcher...")
    
    # We must push app context so mongo extension knows what app to connect to
    with app.app_context():
        results = match_ingredients_to_products(test_ig)
        for r in results:
            print(f"\\n--- {r['original_request']} --> searching '{r['search_term']}' ---")
            for m in r['matches']:
                price = m.get('price_val') or m.get('price')
                print(f"   [€{price}] {m.get('name')} (Store: {m.get('store', 'Unknown')})")
