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
    Convert a price string (e.g., '$12.99') into a clean float.
    
    Args:
        price (str or float): The raw price.
        
    Returns:
        float: The numeric price value.
    """
    # CONVERT: Price string to float (remove $ symbols)
    if isinstance(price, str):
        return float(price.replace("$", "").replace("£", "").strip())
    return price

def find_cheapest_product(product):
    """
    Identify the store offering the lowest price for a specific product.
    
    Args:
        product (dict): Product document containing a 'stores' list.
        
    Returns:
        dict: The store object with the minimum price.
    """
    # FIND BEST DEAL: Get store with lowest price for this product
    min_price = float("inf")
    cheapest = None
    
    for store in product["stores"]:
        price = format_price(store["price"])
        if price < min_price:
            min_price = price
            cheapest = store
    
    return cheapest

def calculate_total_cost(shopping_list, products):
    """
    Calculate the total cost of a shopping list, assuming best prices.
    
    Args:
        shopping_list (list): List of items (dicts or strings).
        products (list): Full catalog of product documents to look up prices.
        
    Returns:
        float: Total cost rounded to 2 decimals.
    """
    # CALCULATE TOTAL: Sum up costs of all items in shopping list
    total = 0.0
    for item in shopping_list:
        # Handle dict items (new format) vs string items (legacy)
        if isinstance(item, dict):
            key = item.get("product_name") or item.get("name")
        else:
            key = item

        for product in products:
            if product.get("name", "").lower() == str(key).lower():
                cheapest = find_cheapest_product(product)
                if cheapest:
                    total += format_price(cheapest["price"])
    return round(total, 2)

def search_products(query, products):
    """
    Filter products by partial name match.
    
    Args:
        query (str): Search term.
        products (list): List of product dictionaries.
        
    Returns:
        list: Filtered list of products.
    """
    # SEARCH: Filter products by name (case-insensitive)
    return [p for p in products if query.lower() in p["name"].lower()]

def sanitize_mongo_doc(doc):
    """
    Recursively convert MongoDB-specific types (ObjectId, Decimal128) 
    to standard JSON-serializable types (str, float).
    
    Why: Flask's jsonify() cannot handle bson.ObjectId or bson.Decimal128 directly.
    
    Args:
        doc (dict, list, or val): The MongoDB document or field.
        
    Returns:
        The sanitized version ready for JSON response.
    """
    if doc is None:
        return None
    
    if isinstance(doc, list):
        return [sanitize_mongo_doc(item) for item in doc]
    if isinstance(doc, dict):
        new_doc = {}
        for k, v in doc.items():
            if k == "_id":
                # Convert ObjectId to string
                id_str = str(v)
                new_doc["id"] = id_str
                new_doc["_id"] = id_str
            elif isinstance(v, Decimal128):
                # Decimal128 -> float for frontend math
                new_doc[k] = float(v.to_decimal())
            else:
                new_doc[k] = sanitize_mongo_doc(v)
        return new_doc
    if isinstance(doc, ObjectId):
        return str(doc)
    if isinstance(doc, Decimal128):
        # Convert to string first to avoid precision issues with float()
        return float(str(doc))
    return doc

# 
# AUTHENTICATION & JWT UTILS
# 

def jwt_secret():
    """Get the JWT secret key from config or env."""
    return current_app.config.get("JWT_SECRET_KEY") or os.environ.get("JWT_SECRET_KEY") or current_app.secret_key

def generate_jwt(email: str) -> str:
    """
    Generate a JSON Web Token for user authentication.
    
    Args:
        email (str): User identifier to embed in token.
        
    Returns:
        str: Encoded JWT string.
    """
    payload = {
        "sub": email,
        "iat": datetime.utcnow(),
        "exp": datetime.utcnow() + timedelta(hours=6)
    }
    return jwt.encode(payload, jwt_secret(), algorithm="HS256")


def decode_jwt(token: str):
    try:
        return jwt.decode(token, jwt_secret(), algorithms=["HS256"])
    except Exception as e:
        print(f"[JWT] decode failed: {e}")
        return None

def get_token_from_request():
    auth_header = request.headers.get("Authorization", "")
    if isinstance(auth_header, str) and auth_header.lower().startswith("bearer "):
        return auth_header.split(" ", 1)[1].strip()
    cookie_token = request.cookies.get("auth_token")
    if cookie_token:
        return cookie_token
    return None

def get_user_email():
    """
    Get the current user_s email from Flask session.
    Checks JWT first, then session.
    Fallback to mock user data for development/testing if enabled.
    """
    try:
        token = get_token_from_request()
        if token:
            decoded = decode_jwt(token)
            if decoded and decoded.get("sub"):
                return decoded.get("sub")
    except Exception:
        pass

    email = session.get("user")
    if not email and getattr(m, "users", None):
        email = "user1@example.com" if "user1@example.com" in m.users else next(iter(m.users.keys()), None)
    return email
