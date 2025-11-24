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


def add_deal_to_user_shopping_list(email, deal):
    """Add a deal (dict or title string) to the user's shopping list. Returns True on success."""
    if not email or not deal:
        return False
    # prepare a simple representation to store in the shopping_list
    item = None
    if isinstance(deal, dict):
        # keep useful fields
        item = {'name': deal.get('title') or deal.get('name'), 'price': deal.get('price'), 'source': deal.get('store')}
    else:
        item = str(deal)

    if HAS_DB and mongo is not None and getattr(mongo, 'db', None) is not None:
        try:
            res = mongo.db.users.update_one({'email': email}, {'$push': {'shopping_list': item}}, upsert=True)
            return (getattr(res, 'modified_count', 0) > 0) or (getattr(res, 'upserted_id', None) is not None)
        except Exception:
            return False

    # fallback: in-memory users dict
    u = users.get(email)
    if not u:
        # create a minimal user doc in-memory
        users[email] = {'email': email, 'password': '', 'name': email, 'shopping_list': [], 'total_cost': 0.0}
        u = users[email]
    try:
        u.setdefault('shopping_list', []).append(item)
        return True
    except Exception:
        return False


def claim_featured_deal_by_id(deal_id_or_title, email=None):
    """Mark a featured deal as claimed. If DB available, increment a 'claims' counter and optionally add claimant email.
    deal_id_or_title may be an ObjectId string or a title string. Returns True on success (or False)."""
    if not deal_id_or_title:
        return False
    # DB path
    if HAS_DB and mongo is not None and getattr(mongo, 'db', None) is not None:
        try:
            # try by _id first
            from bson import ObjectId
            query = {}
            try:
                query = {'_id': ObjectId(str(deal_id_or_title))}
            except Exception:
                query = {'title': str(deal_id_or_title)}

            update = {'$inc': {'claims': 1}}
            if email:
                update['$push'] = {'claimed_by': email}
            res = mongo.db.featured_deals.update_one(query, update, upsert=False)
            return getattr(res, 'modified_count', 0) > 0
        except Exception:
            return False

    # fallback: update in-memory featured_deals list by matching title
    for d in featured_deals:
        if str(d.get('title')) == str(deal_id_or_title) or str(d.get('id')) == str(deal_id_or_title):
            d['claims'] = d.get('claims', 0) + 1
            if email:
                d.setdefault('claimed_by', []).append(email)
            return True
    return False

