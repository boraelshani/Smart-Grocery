# Mock Data — Replace with real DB later

stores = [
    {"id": 1, "name": "Supermart", "location": "123 Main St", "distance": "2.5 miles", "opening_hours": "9 AM - 9 PM", "url": "https://supermart.com", "deals": ["Free delivery", "50% off milk"]},
    {"id": 2, "name": "Grocery Hub", "location": "456 Oak Ave", "distance": "1.2 miles", "opening_hours": "8 AM - 8 PM", "url": "https://groceryhub.com", "deals": ["Buy 2 get 1", "Free shipping over $25"]},
]

# Mock Product Comparison Data
products = [
    {
        "name": "Milk",
        "unit": "gal",
        "stores": [
            {"store": "Supermart", "price": "$3.99", "discount": "10% off", "deal": "Free delivery"},
            {"store": "Grocery Hub", "price": "$4.49", "discount": "None", "deal": "Buy 2 get 1"},
            {"store": "Fresh & Co", "price": "$3.79", "discount": "20% off", "deal": "Free shipping"}
        ],
        "cheapest": {"store": "Fresh & Co", "price": "$3.79", "discount": "20% off", "deal": "Free shipping"}
    },
    {
        "name": "Bread",
        "unit": "loaf",
        "stores": [
            {"store": "Supermart", "price": "$2.99", "discount": "None", "deal": "Free delivery"},
            {"store": "Grocery Hub", "price": "$3.49", "discount": "Buy 1 get 1", "deal": "Buy 2 get 1"},
            {"store": "Fresh & Co", "price": "$3.29", "discount": "None", "deal": "Free shipping"}
        ],
        "cheapest": {"store": "Supermart", "price": "$2.99", "discount": "None", "deal": "Free delivery"}
    }
]

# Mock User Data (Login)
users = {
    "user1@example.com": {"email": "user1@example.com", "password": "password123", "name": "John Doe", "shopping_list": ["milk", "bread"], "total_cost": 6.98},
    "user2@example.com": {"email": "user2@example.com", "password": "password456", "name": "Jane Smith", "shopping_list": ["bottled water"], "total_cost": 3.99}
}

# Mock Featured Deals
featured_deals = [
    {"title": "Free Delivery on Milk", "store": "Supermart", "price": "$3.99", "image": "https://via.placeholder.com/150x150"},
    {"title": "Buy 2 Get 1", "store": "Grocery Hub", "price": "$3.49", "image": "https://via.placeholder.com/150x150"},
]


# Optional MongoDB integration for user helpers
try:
    from utils.db import mongo
    HAS_DB = True
except Exception:
    mongo = None
    HAS_DB = False

def get_user_by_email(email):
    """Return user document by email. Uses MongoDB when available, otherwise falls back to in-memory `users` dict."""
    if not email:
        return None
    if HAS_DB and mongo is not None and getattr(mongo, 'db', None) is not None:
        doc = mongo.db.users.find_one({'email': email})
        if not doc:
            return None
        # convert ObjectId to string for templates/logic
        doc = dict(doc)
        if '_id' in doc:
            doc['id'] = str(doc['_id'])
        return doc
    return users.get(email)

def create_user(user_doc):
    """Insert a new user. Returns inserted id (str) for DB or email for in-memory fallback."""
    if HAS_DB and mongo is not None and getattr(mongo, 'db', None) is not None:
        res = mongo.db.users.insert_one(user_doc)
        return str(res.inserted_id)
    # fallback: add to in-memory dict
    users[user_doc['email']] = user_doc
    return user_doc['email']

