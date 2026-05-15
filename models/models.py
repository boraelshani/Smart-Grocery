"""
═══════════════════════════════════════════════════════════════════════════
FALLBACK DATA MODELS & HELPER FUNCTIONS
═══════════════════════════════════════════════════════════════════════════
In-memory data storage for development/testing when PostgreSQL is unavailable.
Also provides helper functions that work with both DB and fallback data.
"""

# ═══════════════════════════════════════════════════════════════════════════
# FALLBACK DATA STRUCTURES (In-Memory Storage)
# ═══════════════════════════════════════════════════════════════════════════
# These are used when DB connection is unavailable or during development

stores = []  # List of store documents
products = []  # List of product documents
users = {}  # Dictionary mapping email -> user document
featured_deals = []  # List of featured deal documents

# ═══════════════════════════════════════════════════════════════════════════
# DATABASE CONNECTION CHECK
# ═══════════════════════════════════════════════════════════════════════════
try:
    from models.postgres_models import db as sa_db
    HAS_DB = True
except Exception:
    sa_db = None
    HAS_DB = False

# ═══════════════════════════════════════════════════════════════════════════
# USER HELPER FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════

def get_db_info():
    """Retrieve database info and table counts."""
    if HAS_DB and sa_db is not None:
        try:
            from models.postgres_models import Product, Store, User, Promotion
            return {
                'db_name': 'postgresql',
                'collections': {
                    'products': Product.query.count(),
                    'stores': Store.query.count(),
                    'promotions': Promotion.query.count(),
                    'users': User.query.count(),
                },
            }
        except Exception:
            pass

    # Fallback info
    return {
        'db_name': 'in-memory-fallback',
        'collections': {
            'products': len(products),
            'stores': len(stores),
            'featured_deals': len(featured_deals),
            'users': len(users)
        }
    }


def get_user_by_email(email):
    """
    Retrieve user account by email address.
    
    Dual-mode: Uses PostgreSQL when available, falls back to in-memory dict.
    """
    if not email:
        return None
    if HAS_DB:
        try:
            from models.postgres_models import User
            user = User.query.filter_by(email=email).first()
            if user:
                return user.to_dict()
        except Exception:
            pass
    # Fallback: use in-memory dictionary
    return users.get(email)


def create_user(user_doc):
    """
    Create a new user account.
    
    Dual-mode: Inserts into PostgreSQL when available, otherwise stores in-memory.
    """
    if HAS_DB:
        try:
            from models.users_model import users_model
            uid = users_model.create_user(user_doc)
            return uid
        except Exception:
            pass
    # Fallback: add to in-memory dictionary
    users[user_doc['email']] = user_doc
    return user_doc['email']


def add_deal_to_user_shopping_list(email, deal):
    """
    Add a deal/product to the user's shopping list.
    """
    if not email or not deal:
        return False
    # Prepare a simple representation to store in the shopping_list
    item = None
    if isinstance(deal, dict):
        item = {
            'name': deal.get('title') or deal.get('name'),
            'price': deal.get('price'),
            'source': deal.get('store'),
            'image': deal.get('image') or (deal.get('images') and deal.get('images')[0])
        }
    else:
        item = str(deal)

    if HAS_DB:
        try:
            from models.users_model import get_user_lists, add_item_to_list, create_shopping_list, set_active_list
            lists_data = get_user_lists(email)
            active_id = lists_data.get('active_list_id')
            if not active_id:
                active_id = create_shopping_list(email, 'My List')
                set_active_list(email, active_id)
            return add_item_to_list(email, active_id, item)
        except Exception:
            return False

    # fallback: in-memory users dict
    u = users.get(email)
    if not u:
        users[email] = {'email': email, 'password': '', 'name': email, 'shopping_list': [], 'total_cost': 0.0}
        u = users[email]
    try:
        u.setdefault('shopping_list', []).append(item)
        return True
    except Exception:
        return False


def claim_featured_deal_by_id(deal_id_or_title, email=None):
    """Mark a featured deal as claimed."""
    if not deal_id_or_title:
        return False
    # DB path - featured_deals table removed, promotions don't have claims
    # This functionality is deprecated
    if HAS_DB:
        return False

    # fallback: update in-memory featured_deals list by matching title
    for d in featured_deals:
        if str(d.get('title')) == str(deal_id_or_title) or str(d.get('id')) == str(deal_id_or_title):
            d['claims'] = d.get('claims', 0) + 1
            if email:
                d.setdefault('claimed_by', []).append(email)
            return True
    return False
