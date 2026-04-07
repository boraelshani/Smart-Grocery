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

def calculate_proportion_message(req_text, prod_unit, price):
    if not req_text or not prod_unit or price is None:
        return None

    def parse_amt(text):
        if not text: return None, None
        m = re.search(r'([\d\.,]+)\s*([a-zA-Z%]+)', str(text).replace(',', '.'))
        if m: return float(m.group(1)), m.group(2).lower()
        return None, None

    req_q, req_u = parse_amt(req_text)
    prod_q, prod_u = parse_amt(prod_unit)
    
    if not req_q or not prod_q or not req_u or not prod_u: return None
    
    if req_u in ('kg', 'kilo', 'kilos'): req_q *= 1000; req_u = 'g'
    if req_u in ('l', 'liter', 'liters'): req_q *= 1000; req_u = 'ml'
    if prod_u in ('kg', 'kilo', 'kilos'): prod_q *= 1000; prod_u = 'g'
    if prod_u in ('l', 'liter', 'liters'): prod_q *= 1000; prod_u = 'ml'
    
    if req_u != prod_u: return None
    if req_q >= prod_q: return None
    
    prop = req_q / prod_q
    cents = round(price * prop * 100)
    euros = cents / 100.0
    unit_cost = round((price * 100) / prod_q, 2)
    qty_int = int(req_q) if req_q.is_integer() else req_q
    return f"Proportion: using {qty_int}{req_u} costs Approx ~€{euros:.2f} ({unit_cost}¢/{req_u})"

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
        escaped_search = re.escape(search_term).replace(r"\ ", " ")
        pipeline = [
            {
                "$match": {
                    "name": {"$regex": f"\\b{escaped_search}\\b", "$options": "i"},
                    "$or": [
                        {"price": {"$gt": 0}},
                        {"price_val": {"$gt": 0}}
                    ]
                }
            },
            # Sort cheapest first
            {"$sort": {"price": 1, "price_val": 1}},
            {"$limit": 3}
        ]

        matches = list(mongo.db.products.aggregate(pipeline))

        # If no strict match, fallback to the last main word of the ingredient  
        # (e.g., if 'yellow onion' didn't match, maybe just 'onion' will)       
        if not matches and ' ' in search_term:
            last_word = search_term.split()[-1]
            if len(last_word) >= 3:
                escaped_last = re.escape(last_word).replace(r"\ ", " ")
                pipeline_fallback = [
                    {
                        "$match": {
                            "name": {"$regex": f"\\b{escaped_last}\\b", "$options": "i"},
                            "$or": [
                                {"price": {"$gt": 0}},
                                {"price_val": {"$gt": 0}}
                            ]
                        }
                    },
                    {"$sort": {"price": 1, "price_val": 1}},
                    {"$limit": 3}
                ]
                matches = list(mongo.db.products.aggregate(pipeline_fallback))
        
        # Sanitize matches for frontend
        sanitized_matches = []
        for m in matches:
            sm = sanitize_mongo_doc(m)
            price = sm.get('price_val') or sm.get('price')
            unit = sm.get('unit') or sm.get('quantity')
            prop_msg = calculate_proportion_message(raw_ing, unit, price)
            if prop_msg:
                sm['proportional_message'] = prop_msg
            sanitized_matches.append(sm)
        
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
