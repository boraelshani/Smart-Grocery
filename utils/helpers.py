"""
═══════════════════════════════════════════════════════════════════════════
HELPER FUNCTIONS MODULE
═══════════════════════════════════════════════════════════════════════════
Shared utilities used by routes and models for:
- Price formatting
- Product searching
- MongoDB document sanitization (serialization)
- JWT token generation
═══════════════════════════════════════════════════════════════════════════
"""
import os
import jwt
from flask import session, request, current_app
from datetime import datetime, timedelta
from bson import ObjectId, Decimal128
from models import models as m

# 
# FORMATTING & CALCULATION LOGIC
# 

def format_price(price):
    """
    Convert a price string (e.g., '$12.99', '£5.00') into a clean float.
    
    Robustness:
    - Handles inputs that are already floats.
    - Strips currency symbols like $ and £.
    - Strips surrounding whitespace.
    
    Args:
        price (str or float): The raw price input.
        
    Returns:
        float: The numeric price value (e.g., 12.99).
    """
    # CONVERT: Price string to float
    if isinstance(price, str):
        # Remove common currency symbols and whitespace
        return float(price.replace("$", "").replace("£", "").strip())
    # If it's already a number (int/float), just return it as-is
    return price

def find_cheapest_product(product):
    """
    Identify the store offering the lowest price for a specific product.
    
    Logic:
    Iterates through the 'stores' array nested within the product document
    to find the entry with the minimum numeric price.
    
    Args:
        product (dict): Product document containing a 'stores' list.
        
    Returns:
        dict: The store object (e.g. {'store': 'Aldi', 'price': 1.99}) with the minimum price.
    """
    # Initialize minimum price to Infinity so the first real price will always be lower
    min_price = float("inf")
    cheapest = None
    
    # Iterate through all stores carrying this product
    for store in product["stores"]:
        # Normalize price string to float for comparison
        price = format_price(store["price"])
        if price < min_price:
            min_price = price
            cheapest = store
    
    return cheapest

def calculate_total_cost(shopping_list, products):
    """
    Calculate the estimated total cost of a shopping list.
    
    Assumption:
    It assumes the user will buy each item at the store offering the *best price*.
    
    Args:
        shopping_list (list): List of items the user wants to buy.
            Can be simple strings ["Milk"] or dicts [{"name": "Milk"}].
        products (list): Full catalog of product documents (the 'database') to look up prices.
        
    Returns:
        float: Total estimated cost rounded to 2 decimals.
    """
    # CALCULATE TOTAL: Sum up costs of all items
    total = 0.0
    
    for item in shopping_list:
        # 1. Normalize Item Key
        # Handle dict items (new format) vs string items (legacy)
        if isinstance(item, dict):
            key = item.get("product_name") or item.get("name")
        else:
            key = item

        # 2. Find Product Price
        # Look through the entire product catalog to find a match
        # (Note: In production, this loop-inside-loop is inefficient O(N*M). 
        # Better to query DB directly for prices).
        for product in products:
            if product.get("name", "").lower() == str(key).lower():
                # Find the cheapest price for this specific product
                cheapest = find_cheapest_product(product)
                if cheapest:
                    # Add to running total
                    total += format_price(cheapest["price"])
                    
    # Return formatted money float
    return round(total, 2)

def search_products(query, products):
    """
    Filter in-memory product list by partial name match.
    
    Args:
        query (str): Search term (e.g. "Bread").
        products (list): List of product dictionaries.
        
    Returns:
        list: Subset of products containing the query string.
    """
    # Case-insensitive search using list comprehension
    # Check if query string appears inside product name
    return [p for p in products if query.lower() in p["name"].lower()]

def sanitize_mongo_doc(doc):
    """
    Recursively convert MongoDB-specific data types into standard JSON-friendly types.
    
    Why this is needed:
    MongoDB drivers return data using special BSON types:
    - `ObjectId("...")`: Not valid JSON.
    - `Decimal128("10.99")`: Not valid JSON.
    Flask's `jsonify` serializer will crash if fed these types directly.
    
    Supported Conversions:
    - ObjectId -> str
    - Decimal128 -> float
    - Recursive traversal of nested lists and dicts.
    
    Args:
        doc (dict, list, or val): The MongoDB document or field.
        
    Returns:
        The sanitized structure, safe to send to the frontend.
    """
    if doc is None:
        return None
    
    # 1. Handle Lists (Recursion)
    if isinstance(doc, list):
        return [sanitize_mongo_doc(item) for item in doc]
        
    # 2. Handle Dictionaries (Recursion)
    if isinstance(doc, dict):
        new_doc = {}
        for k, v in doc.items():
            if k == "_id":
                # Special handling: Convert Primary Key to string
                # We also add a pure 'id' field for convenience
                id_str = str(v)
                new_doc["id"] = id_str
                new_doc["_id"] = id_str
            elif isinstance(v, Decimal128):
                # Extract the Python decimal, then convert to float
                new_doc[k] = float(v.to_decimal())
            else:
                # Recurse for nested fields
                new_doc[k] = sanitize_mongo_doc(v)
        return new_doc
        
    # 3. Handle Primitive BSON Types (Leaf Nodes)
    if isinstance(doc, ObjectId):
        return str(doc)
    if isinstance(doc, Decimal128):
        # Convert to string first to avoid precision issues, then float
        return float(str(doc))
    if isinstance(doc, datetime):
        return doc.isoformat()
        
    # 4. Return standard types (str, int, bool) as-is
    return doc

# 
# AUTHENTICATION & JWT UTILS
# 

def jwt_secret():
    """
    Retrieve the secret key used for signing JWTs.
    Checks config -> env var -> flask secret key chain.
    """
    return current_app.config.get("JWT_SECRET_KEY") or os.environ.get("JWT_SECRET_KEY") or current_app.secret_key

def generate_jwt(email: str) -> str:
    """
    Generate a JSON Web Token (JWT) for stateless authentication.
    
    Payload Claims:
    - sub (Subject): The user's email.
    - iat (Issued At): When token was created.
    - exp (Expiration): When token dies (set to 6 hours from now).
    
    Args:
        email (str): User identifier.
        
    Returns:
        str: The encoded token string.
    """
    payload = {
        "sub": email,
        "iat": datetime.utcnow(),
        "exp": datetime.utcnow() + timedelta(hours=6)
    }
    # Encode with HS256 algorithm
    return jwt.encode(payload, jwt_secret(), algorithm="HS256")


def decode_jwt(token: str):
    """
    Verify and decode a JWT.
    Returns the payload dictionary if signature is valid and token not expired.
    Returns None if invalid.
    """
    try:
        return jwt.decode(token, jwt_secret(), algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        # Silent failure for expired tokens - handled by session fallback
        return None
    except Exception as e:
        print(f"[JWT] decode failed: {e}")
        return None

def get_token_from_request():
    """
    Extract JWT from the HTTP request.
    
    Priority:
    1. Authorization Header (Bearer token) - Standard for APIs
    2. 'auth_token' Cookie - Standard for Web Browsers
    """
    # 1. Check Header
    auth_header = request.headers.get("Authorization", "")
    if isinstance(auth_header, str) and auth_header.lower().startswith("bearer "):
        return auth_header.split(" ", 1)[1].strip()
        
    # 2. Check Cookie
    # (Browsers automatically send cookies with every request)
    cookie_token = request.cookies.get("auth_token")
    if cookie_token:
        return cookie_token
    return None

def get_user_email():
    """
    Determine the currently logged-in user.
    
    Strategy:
    1. Check for valid JWT token in headers/cookies.
    2. Check for Flask Session (legacy/simple auth).
    3. Fallback: Return a default mock user if in dev mode with no auth.
    
    Returns:
        str: The user's email address or None.
    """
    # 1. Try JWT
    try:
        token = get_token_from_request()
        if token:
            decoded = decode_jwt(token)
            if decoded and decoded.get("sub"):
                return decoded.get("sub")
    except Exception:
        pass

    # 2. Try Session (Server-side cookie)
    email = session.get("user")
    
    # 3. Last Resort: Dev Mode Mock User
    if not email and getattr(m, "users", None):
        # Pick the first available mock user if one exists
        email = "user1@example.com" if "user1@example.com" in m.users else next(iter(m.users.keys()), None)
    return email


def get_category_options():
    try:
        from utils.db import mongo
        all_cats = list(mongo.db.categories.find({}))
        
        # Build children map
        children_map = {}
        for c in all_cats:
            pid = str(c.get("parentId")) if c.get("parentId") else "None"
            children_map.setdefault(pid, []).append(c)

        db_cats = children_map.get("None", [])
        
        category_options = []
        for parent_cat in db_cats:
            if not parent_cat.get("name_en"): continue
            
            pid_str = str(parent_cat["_id"])
            subcats = children_map.get(pid_str, [])
            
            sub_options = []
            for s in subcats:
                if not s.get("name_en"): continue
                
                s_id_str = str(s["_id"])
                leaves = children_map.get(s_id_str, [])
                leaf_options = [{"name": l.get("name_en"), "image": l.get("imageUrl")} for l in leaves if l.get("name_en")]
                
                sub_options.append({
                    "name": s.get("name_en"),
                    "image": s.get("imageUrl"),
                    "subcategories": leaf_options
                })
            
            category_options.append({
                "name": parent_cat.get("name_en"),
                "image": parent_cat.get("imageUrl"),
                "subcategories": sub_options
            })
            
        return category_options
    except Exception as e:
        import traceback
        traceback.print_exc()
        return []
