"""
═══════════════════════════════════════════════════════════════════════════
FALLBACK DATA MODELS & HELPER FUNCTIONS
═══════════════════════════════════════════════════════════════════════════
In-memory data storage for development/testing when MongoDB is unavailable.
Also provides helper functions that work with both MongoDB and fallback data.
"""

# ═══════════════════════════════════════════════════════════════════════════
# FALLBACK DATA STRUCTURES (In-Memory Storage)
# ═══════════════════════════════════════════════════════════════════════════
# These are used when MongoDB connection is unavailable or during development

stores = []  # List of store documents
products = []  # List of product documents
users = {}  # Dictionary mapping email -> user document
featured_deals = []  # List of featured deal documents

# ═══════════════════════════════════════════════════════════════════════════
# DATABASE CONNECTION SETUP
# ═══════════════════════════════════════════════════════════════════════════
# Try to import MongoDB instance, fallback to in-memory mode if unavailable

try:
    from utils.db import mongo
    HAS_DB = True
except Exception:
    mongo = None
    HAS_DB = False

# ═══════════════════════════════════════════════════════════════════════════
# USER HELPER FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════

def get_user_by_email(email):
    """
    Retrieve user account by email address.
    
    Dual-mode: Uses MongoDB when available, falls back to in-memory dict.
    
    Args:
        email: User email address
    
    Returns:
        User document dictionary or None
    """
    if not email:
        return None
    if HAS_DB and mongo is not None and getattr(mongo, 'db', None) is not None:
        doc = mongo.db.users.find_one({'email': email})
        if not doc:
            return None
        # Convert ObjectId to string for templates/logic
        doc = dict(doc)
        if '_id' in doc:
            doc['id'] = str(doc['_id'])
        return doc
    # Fallback: use in-memory dictionary
    return users.get(email)


def create_user(user_doc):
    """
    Create a new user account.
    
    Dual-mode: Inserts into MongoDB when available, otherwise stores in-memory.
    
    Args:
        user_doc: Dictionary with user data (email, name, password_hash, etc.)
    
    Returns:
        User ID (string) - ObjectId from MongoDB or email from fallback storage
    """
    if HAS_DB and mongo is not None and getattr(mongo, 'db', None) is not None:
        res = mongo.db.users.insert_one(user_doc)
        return str(res.inserted_id)
    # Fallback: add to in-memory dictionary
    users[user_doc['email']] = user_doc
    return user_doc['email']


def add_deal_to_user_shopping_list(email, deal):
    """
    Add a deal/product to the user's shopping list.
    
    Args:
        email: User email address
        deal: Deal dictionary or product name string
    
    Returns:
        Boolean indicating success of the operation
    """
    if not email or not deal:
        return False
    # Prepare a simple representation to store in the shopping_list
    item = None
    if isinstance(deal, dict):
        # Keep useful fields from the deal object
        item = {
            'name': deal.get('title') or deal.get('name'),
            'price': deal.get('price'),
            'source': deal.get('store'),
            'image': deal.get('image') or (deal.get('images') and deal.get('images')[0])
        }
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

