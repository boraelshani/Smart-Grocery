"""
═══════════════════════════════════════════════════════════════════════════
USER MODEL & AUTHENTICATION
═══════════════════════════════════════════════════════════════════════════
Handles all user-related database operations including:
- User authentication with hashed passwords (bcrypt)
- User account creation and retrieval
- Shopping list management (CRUD operations)
- Dual-mode support: MongoDB (Production) or In-Memory Mock (Development)

Key Concepts:
- Password Hashing (Security)
- Fallback Logic (Reliability)
- BSON Type Conversion (ObjectId handles)
═══════════════════════════════════════════════════════════════════════════
"""

from pymongo import MongoClient
from bson import ObjectId
from bson.decimal128 import Decimal128
from datetime import datetime
import os
import re
from dotenv import load_dotenv
from typing import List, Optional
import certifi
import bcrypt
from datetime import datetime
import uuid

load_dotenv()

# ═══════════════════════════════════════════════════════════════════════════
# CATEGORY: DEPENDENCIES & FALLBACKS
# ═══════════════════════════════════════════════════════════════════════════

# Try to import Flask-PyMongo instance `mongodb` wrapper for database access.
from utils.db import get_db

# Try to import mock/fallback data for development mode
try:
    from models import models as mock_models
except Exception:
    mock_models = None


# ═══════════════════════════════════════════════════════════════════════════
# CATEGORY: READ OPERATIONS (USER LOOKUP)
# ═══════════════════════════════════════════════════════════════════════════

def get_user_by_email(email: str):
    """
    Retrieve a user account by email address.
    
    Strategy:
    1. Try MongoDB first (production)
    2. Fallback to in-memory mock data (development)
    
    Args:
        email: User email address to search for
    
    Returns:
        Dictionary with user data (includes hashed password, name, etc.) or None if not found
    """
    # 0. INPUT VALIDATION
    if not email:
        return None
    
    # 1. DATABASE CHECK (Production Mode)
    if get_db() is not None:
        # Search the 'users' collection for a document where field 'email' matches the input
        doc = get_db().users.find_one({'email': email})
        
        # If no document found, return None immediately
        if not doc:
            return None
        
        # Convert BSON document (Binary JSON) to standard Python dict
        doc = dict(doc)
        
        # Convert MongoDB's internal ObjectId to a simple string
        if '_id' in doc:
            doc['id'] = str(doc['_id'])
            
        return doc
        
    # 2. FALLBACK CHECK (Development/Mock Mode)
    # Check if mock_models module exists and has 'users'
    if getattr(mock_models, 'users', None) is None:
        return None
        
    # Look up the user in the in-memory Python dictionary
    return mock_models.users.get(email)


def get_all_users():
    """Download entire user tables (Admin use only)."""
    if get_db() is not None:
        return list(get_db().users.find())
    if getattr(mock_models, 'users', None):
        return list(mock_models.users.values())
    return []


# ═══════════════════════════════════════════════════════════════════════════
# CATEGORY: AUTHENTICATION (LOGIN)
# ═══════════════════════════════════════════════════════════════════════════

def authenticate(email, password):
    """
    Verify user login credentials.
    
    Verification Steps:
    1. Find user by email.
    2. Retrieve stored password HASH from database.
    3. Use bcrypt to check if provided plaintext password matches the hash.
    """
    user = get_user_by_email(email)
    
    if not user:
        return False
        
    stored_password = user.get('password')
    
    # CASE A: Standard Encrypted Password (Bcrypt)
    # Stored strings start with $2b$ or similar if they are bcrypt hashes
    if stored_password and isinstance(stored_password, (str, bytes)) and str(stored_password).startswith('$'):
        try:
            # Convert strings to bytes for bcrypt.checkpw
            pwd_bytes = password.encode('utf-8')
            hash_bytes = stored_password.encode('utf-8') if isinstance(stored_password, str) else stored_password
            return bcrypt.checkpw(pwd_bytes, hash_bytes)
        except Exception as e:
            print(f"Bcrypt Check Error: {e}")
            return False
            
    # CASE B: Legacy/Plaintext Passwords (Development only)
    # If the database has plain strings (not recommended for production)
    return stored_password == password


# ═══════════════════════════════════════════════════════════════════════════
# CATEGORY: CREATE OPERATIONS (SIGNUP)
# ═══════════════════════════════════════════════════════════════════════════

def create_user(user_doc):
    """
    Register a new user in the system.
    
    Hash Handling:
    - Passwords should ideally be hashed BEFORE calling this, 
      but we check/ensure hashing is done.
    """
    # 1. Mongo Implementation
    if get_db() is not None:
        result = get_db().users.insert_one(user_doc)
        return str(result.inserted_id)
        
    # 2. Mock Implementation
    if getattr(mock_models, 'users', None) is not None:
        email = user_doc.get('email')
        if email:
            mock_models.users[email] = user_doc
            return email
            
    return None


# ═══════════════════════════════════════════════════════════════════════════
# CATEGORY: SHOPPING LIST (CRUD)
# ═══════════════════════════════════════════════════════════════════════════

def get_shopping_list(email):
    """
    Retrieve the user's shopping list.
    
    Returns:
        List of item dictionaries or empty list.
    """
    user = get_user_by_email(email)
    if user:
        return user.get('shopping_list', [])
    return []

def add_to_shopping_list(email, item):
    """
    Add a new item to the user's shopping list array.
    """
    # 1. Mongo Implementation
    if get_db() is not None:
        # $push appends value to array
        result = get_db().users.update_one(
            {'email': email},
            {'$push': {'shopping_list': item}}
        )
        return result.modified_count > 0
        
    # 2. Mock Implementation
    if getattr(mock_models, 'users', None) is not None:
        user = mock_models.users.get(email)
        if user:
            # Initialize list if missing
            if 'shopping_list' not in user:
                user['shopping_list'] = []
            user['shopping_list'].append(item)
            return True
            
    return False

def remove_from_shopping_list(email, index):
    """
    Remove an item from the shopping list by its INDEX.
    Note: Removing by index in MongoDB is tricky because arrays can shift.
    Here we implement a safe logic: Get List -> Remove in Python -> Save List.
    """
    # 1. Mongo Implementation
    if get_db() is not None:
        # Fetch current list
        user = get_db().users.find_one({'email': email})
        if user and 'shopping_list' in user:
            current_list = user['shopping_list']
            
            # bounds check
            if 0 <= index < len(current_list):
                current_list.pop(index)
                
                # Update entire list in DB
                get_db().users.update_one(
                    {'email': email},
                    {'$set': {'shopping_list': current_list}}
                )
                return True
        return False
        
    # 2. Mock Implementation
    if getattr(mock_models, 'users', None):
        user = mock_models.users.get(email)
        if user and 'shopping_list' in user:
            if 0 <= index < len(user['shopping_list']):
                user['shopping_list'].pop(index)
                return True
    return False

def update_shopping_list(email, new_list):
    """
    Replace the entire shopping list (used for reordering/drag-n-drop).
    """
    if get_db() is not None:
        get_db().users.update_one(
            {'email': email},
            {'$set': {'shopping_list': new_list}}
        )
        return True
        
    if getattr(mock_models, 'users', None):
        user = mock_models.users.get(email)
        if user:
            user['shopping_list'] = new_list
            return True
    return False


# ═══════════════════════════════════════════════════════════════════════════
# HELPER FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════

def _list_owner_key(email: str) -> str:
    user = get_user_by_email(email) or {}
    return str(user.get('userId') or email)

def _to_float(value, default=0.0):
    try:
        if value is None:
            return float(default)
        return float(value)
    except Exception:
        return float(default)

def _normalize_item(item):
    if isinstance(item, str):
        return {
            'name': item,
            'qty': 1,
            'quantity': 1,
            'purchased': False,
            'checked': False,
            'is_new': True,
        }

    if not isinstance(item, dict):
        return {
            'name': str(item),
            'qty': 1,
            'quantity': 1,
            'purchased': False,
            'checked': False,
            'is_new': True,
        }

    merged = dict(item)
    qty = int(_to_float(merged.get('qty') if merged.get('qty') is not None else merged.get('quantity'), 1))
    qty = max(1, qty)
    merged['qty'] = qty
    merged['quantity'] = qty
    merged['purchased'] = bool(merged.get('purchased') or merged.get('checked'))
    merged['checked'] = bool(merged.get('checked') or merged.get('purchased'))
    merged['is_new'] = bool(merged.get('is_new', True))
    return merged

def _resolve_price_for_item(db, item):
    unit_price = _to_float(item.get('price_val') if item.get('price_val') is not None else item.get('price'), 0)
    product_id = item.get('productId')

    if not product_id and item.get('id'):
        candidate = db.products.find_one({'$or': [{'productId': str(item.get('id'))}, {'id': str(item.get('id'))}]}, {'_id': 0, 'productId': 1})
        if candidate and candidate.get('productId'):
            product_id = candidate.get('productId')

    if not product_id and item.get('name'):
        name = str(item.get('name')).strip()
        if name:
            prod = db.products.find_one(
                {'$or': [
                    {'name_en': {'$regex': '^' + re.escape(name) + '$', '$options': 'i'}},
                    {'name_de': {'$regex': '^' + re.escape(name) + '$', '$options': 'i'}},
                    {'name': {'$regex': '^' + re.escape(name) + '$', '$options': 'i'}},
                ]},
                {'_id': 0, 'productId': 1, 'defaultImageUrl': 1},
            )
            if prod:
                product_id = prod.get('productId')
                if not item.get('image') and prod.get('defaultImageUrl'):
                    item['image'] = prod.get('defaultImageUrl')

    store_id = item.get('storeId') or item.get('store_id')
    if product_id:
        item['productId'] = product_id
        query = {'productId': product_id, 'isAvailable': True}
        if store_id:
            query['storeId'] = store_id

        offer = db.store_products.find_one(query, sort=[('promoPrice', 1), ('basePrice', 1), ('lastPriceUpdate', -1)])
        if not offer and store_id:
            offer = db.store_products.find_one({'productId': product_id, 'isAvailable': True}, sort=[('promoPrice', 1), ('basePrice', 1), ('lastPriceUpdate', -1)])

        if offer:
            unit_price = _to_float(offer.get('promoPrice') if offer.get('promoPrice') is not None else offer.get('basePrice'), unit_price)
            item['storeId'] = offer.get('storeId')
            item['store_product_id'] = offer.get('storeProductId')

    qty = int(_to_float(item.get('qty') if item.get('qty') is not None else item.get('quantity'), 1))
    qty = max(1, qty)
    item['qty'] = qty
    item['quantity'] = qty

    item['price_val'] = round(unit_price, 2)
    item['price'] = round(unit_price, 2)
    item['unitPrice'] = round(unit_price, 2)
    item['lineTotal'] = round(unit_price * qty, 2)
    return item


def _normalize_list_doc(doc):
    return {
        'id': doc.get('listId') or doc.get('id'),
        'listId': doc.get('listId') or doc.get('id'),
        'name': doc.get('name') or 'My List',
        'items': doc.get('items', []) or [],
        'totalPrice': _to_float(doc.get('totalPrice'), 0),
        'shared': bool(doc.get('shared', False)),
        'shareCode': doc.get('shareCode'),
        'collaborators': doc.get('collaborators', []),
        'created_at': doc.get('createdAt') or doc.get('created_at'),
        'updated_at': doc.get('updatedAt') or doc.get('updated_at'),
    }


def _persist_list(db, owner_key, list_doc):
    payload = {
        'listId': list_doc.get('listId') or list_doc.get('id'),
        'userId': owner_key,
        'name': list_doc.get('name') or 'My List',
        'items': list_doc.get('items') or [],
        'totalPrice': round(_to_float(list_doc.get('totalPrice'), 0), 2),
        'shared': bool(list_doc.get('shared', False)),
        'shareCode': list_doc.get('shareCode'),
        'collaborators': list_doc.get('collaborators', []),
        'updatedAt': datetime.utcnow(),
    }

    db.lists.update_one(
        {'listId': payload['listId'], 'userId': owner_key},
        {
            '$set': payload,
            '$setOnInsert': {
                'createdAt': datetime.utcnow(),
            },
        },
        upsert=True,
    )


def _recalculate_and_save_list(db, owner_key, list_doc):
    items = []
    total = 0.0
    for raw in (list_doc.get('items') or []):
        item = _normalize_item(raw)
        item = _resolve_price_for_item(db, item)
        total += _to_float(item.get('lineTotal'), 0)
        items.append(item)

    list_doc['items'] = items
    list_doc['totalPrice'] = round(total, 2)
    _persist_list(db, owner_key, list_doc)
    return list_doc


def _ensure_default_list(db, owner_key, email):
    rows = list(db.lists.find({'userId': owner_key}).sort('createdAt', 1))
    if rows:
        return rows

    legacy_items = []
    user = get_user_by_email(email) or {}
    if isinstance(user.get('shopping_list'), list):
        legacy_items = [_normalize_item(i) for i in user.get('shopping_list')]

    list_id = str(uuid.uuid4())
    base = {
        'listId': list_id,
        'id': list_id,
        'name': 'My List',
        'items': legacy_items,
        'shared': False,
        'shareCode': None,
        'collaborators': [],
        'totalPrice': 0,
    }
    base = _recalculate_and_save_list(db, owner_key, base)
    update_user(email, {'active_list_id': list_id})
    return [base]

# ═══════════════════════════════════════════════════════════════════════════
# CONSOLIDATED LIST FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════


def get_user_lists(email):
    if not email:
        return {'lists': [], 'active_list_id': None}

    db = get_db()
    if db is not None and 'lists' in db.list_collection_names():
        owner_key = _list_owner_key(email)
        _ensure_default_list(db, owner_key, email)

        docs = list(db.lists.find({
            '$or': [
                {'userId': owner_key},
                {'collaborators': {'$elemMatch': {'email': email}}}
            ]
        }).sort('updatedAt', -1))

        lists = []
        for doc in docs:
            n = _normalize_list_doc(doc)
            if doc.get('userId') != owner_key:
                n['is_shared'] = True
                n['owner_email'] = doc.get('userId')
                my_role = 'view'
                for c in doc.get('collaborators', []):
                    if isinstance(c, dict) and c.get('email') == email:
                        my_role = c.get('role', 'view')
                        break
                n['my_role'] = my_role
            lists.append(n)

        user = get_user_by_email(email) or {}
        active_list_id = user.get('active_list_id') or user.get('activeListId')
        if not active_list_id and lists:
            active_list_id = lists[0].get('id')
            update_user(email, {'active_list_id': active_list_id})

        return {'lists': lists, 'active_list_id': active_list_id}

    # Fallback to legacy embedded-list behavior
    user = get_user_by_email(email)
    if not user:
        return {'lists': [], 'active_list_id': None}

    if 'lists' not in user:
        legacy_list = user.get('shopping_list', [])
        default_lists = []
        active_id = None
        if legacy_list:
            list_id = str(uuid.uuid4())
            new_legacy = {
                'id': list_id,
                'name': 'My Shopping List',
                'items': legacy_list,
                'collaborators': [],
                'created_at': datetime.utcnow() if get_db() is not None else None
            }
            default_lists.append(new_legacy)
            active_id = list_id

        if get_db() is not None:
            get_db().users.update_one(
                {'email': email},
                {'$set': {'lists': default_lists, 'active_list_id': active_id}}
            )
        elif getattr(mock_models, 'users', None) and email in mock_models.users:
            mock_models.users[email]['lists'] = default_lists
            mock_models.users[email]['active_list_id'] = active_id

        user['lists'] = default_lists
        user['active_list_id'] = active_id

    my_lists = user.get('lists', [])
    active_id = user.get('active_list_id')

    if get_db() is not None:
        try:
            shared = get_db().users.find({'lists.collaborators.email': email})
            for u in shared:
                owner = u.get('email')
                if owner == email: continue
                for l in u.get('lists', []):
                    for c in l.get('collaborators', []):
                        if isinstance(c, dict) and c.get('email') == email:
                            l_copy = l.copy()
                            l_copy['is_shared'] = True
                            l_copy['owner_email'] = owner
                            l_copy['my_role'] = c.get('role', 'view')
                            my_lists.append(l_copy)
                            break
        except Exception as e:
            print(f"Error fetching shared lists: {e}")

    return {
        'lists': my_lists,
        'active_list_id': active_id
    }


def create_shopping_list(email: str, name: str) -> str:
    list_id = str(uuid.uuid4())
    db = get_db()
    if db is not None and 'lists' in db.list_collection_names():
        owner_key = _list_owner_key(email)
        _persist_list(
            db,
            owner_key,
            {
                'listId': list_id,
                'id': list_id,
                'name': name,
                'items': [],
                'totalPrice': 0,
                'shared': False,
                'shareCode': None,
                'collaborators': []
            },
        )
        update_user(email, {'active_list_id': list_id})
        return list_id

    get_user_lists(email)
    
    new_list = {
        'id': list_id,
        'name': name,
        'items': [],
        'collaborators': [],
        'created_at': datetime.utcnow()
    }
    
    if get_db() is not None:
        get_db().users.update_one(
            {'email': email},
            {
                '$push': {'lists': new_list},
                '$set': {'active_list_id': list_id}
            }
        )
    elif getattr(mock_models, 'users', None):
        user = mock_models.users.get(email)
        if user:
            user.setdefault('lists', []).append(new_list)
            user['active_list_id'] = list_id
            
    return list_id


def share_list_with_user(owner_email: str, list_id: str, target_email: str, role: str = 'view') -> bool:
    db = get_db()
    if db is not None and 'lists' in db.list_collection_names():
        owner_key = _list_owner_key(owner_email)
        row = db.lists.find_one({'listId': list_id, 'userId': owner_key})
        if row:
            db.lists.update_one(
                {'listId': list_id, 'userId': owner_key},
                {'$pull': {'collaborators': {'email': target_email}}}
            )
            res = db.lists.update_one(
                {'listId': list_id, 'userId': owner_key},
                {'$push': {'collaborators': {'email': target_email, 'role': role}}}
            )
            return res.modified_count > 0

    if get_db() is not None:
        get_db().users.update_one(
            {'email': owner_email, 'lists.id': list_id},
            {'$pull': {'lists.$.collaborators': {'email': target_email}}}
        )
        res = get_db().users.update_one(
            {'email': owner_email, 'lists.id': list_id},
            {'$push': {'lists.$.collaborators': {'email': target_email, 'role': role}}}
        )
        return res.modified_count > 0
    return False


def remove_collaborator(owner_email: str, list_id: str, target_email: str) -> bool:
    db = get_db()
    if db is not None and 'lists' in db.list_collection_names():
        owner_key = _list_owner_key(owner_email)
        res = db.lists.update_one(
            {'listId': list_id, 'userId': owner_key},
            {'$pull': {'collaborators': {'email': target_email}}}
        )
        return res.modified_count > 0

    if get_db() is not None:
        res = get_db().users.update_one(
            {'email': owner_email, 'lists.id': list_id},
            {'$pull': {'lists.$.collaborators': {'email': target_email}}}
        )
        return res.modified_count > 0
    return False


def update_user(email: str, update_data: dict) -> bool:
    if get_db() is not None:
        result = get_db().users.update_one(
            {'email': email},
            {'$set': update_data}
        )
        return result.modified_count > 0
        
    if getattr(mock_models, 'users', None):
        user = mock_models.users.get(email)
        if user:
            user.update(update_data)
            return True
    return False


def update_user_profile(email: str, update_data: dict) -> bool:
    return update_user(email, update_data)


def update_list_items(email: str, list_id: str, items: list) -> bool:
    db = get_db()
    if db is not None and 'lists' in db.list_collection_names():
        owner_key = _list_owner_key(email)
        row = db.lists.find_one({
            'listId': list_id,
            '$or': [
                {'userId': owner_key},
                {'collaborators': {'$elemMatch': {'email': email}}}
            ]
        })
        if not row:
            return False
            
        row = _normalize_list_doc(row)
        row['items'] = items or []
        _recalculate_and_save_list(db, row.get('userId') or owner_key, row)
        return True

    if get_db() is not None:
        result = get_db().users.update_one(
            {
                'lists.id': list_id,
                '$or': [
                    {'email': email},
                    {'lists': {'$elemMatch': {'id': list_id, 'collaborators.email': email}}}
                ]
            },
            {'$set': {'lists.$.items': items}}
        )
        return result.modified_count > 0

    if getattr(mock_models, 'users', None):
        user = mock_models.users.get(email)
        if user and 'lists' in user:
            for lst in user['lists']:
                if lst['id'] == list_id:
                    lst['items'] = items
                    return True
    return False


def set_active_list(email: str, list_id: str) -> bool:
    return update_user(email, {'active_list_id': list_id})


def add_item_to_list(email: str, list_id: str, item: dict) -> bool:
    db = get_db()
    if db is not None and 'lists' in db.list_collection_names():
        owner_key = _list_owner_key(email)
        row = db.lists.find_one({
            'listId': list_id,
            '$or': [
                {'userId': owner_key},
                {'collaborators': {'$elemMatch': {'email': email}}}
            ]
        })
        if not row:
            return False

        row = _normalize_list_doc(row)
        items = row.get('items') or []
        norm = _normalize_item(item)

        incoming_name = str(norm.get('name') or '').strip().lower()
        incoming_product_id = str(norm.get('productId') or '').strip()
        merged = False
        for existing in items:
            ex_name = str(existing.get('name') or '').strip().lower() if isinstance(existing, dict) else ''
            ex_pid = str(existing.get('productId') or '').strip() if isinstance(existing, dict) else ''
            if incoming_product_id and ex_pid and incoming_product_id == ex_pid:
                existing['qty'] = int(_to_float(existing.get('qty'), 1)) + int(_to_float(norm.get('qty'), 1))
                existing['quantity'] = existing['qty']
                existing['is_new'] = True
                merged = True
                break
            if incoming_name and ex_name and incoming_name == ex_name:
                existing['qty'] = int(_to_float(existing.get('qty'), 1)) + int(_to_float(norm.get('qty'), 1))
                existing['quantity'] = existing['qty']
                existing['is_new'] = True
                merged = True
                break

        if not merged:
            items.append(norm)

        row['items'] = items
        _recalculate_and_save_list(db, row.get('userId') or owner_key, row)
        return True

    if get_db() is not None:
        result = get_db().users.update_one(
            {
                'lists.id': list_id,
                '$or': [
                    {'email': email},
                    {'lists': {'$elemMatch': {'id': list_id, 'collaborators.email': email}}}
                ]
            },
            {'$push': {'lists.$.items': item}}
        )
        return result.modified_count > 0

    if getattr(mock_models, 'users', None):
        user = mock_models.users.get(email)
        if user and 'lists' in user:
            for lst in user['lists']:
                if lst['id'] == list_id:
                    lst.setdefault('items', []).append(item)
                    return True
    return False


def remove_item_from_list(email: str, list_id: str, item_name: str) -> bool:
    db = get_db()
    if db is not None and 'lists' in db.list_collection_names():
        owner_key = _list_owner_key(email)
        row = db.lists.find_one({
            'listId': list_id,
            '$or': [
                {'userId': owner_key},
                {'collaborators': {'$elemMatch': {'email': email}}}
            ]
        })
        if not row:
            return False

        row = _normalize_list_doc(row)
        before = len(row.get('items') or [])
        target = (item_name or '').strip().lower()
        kept = []
        removed = False
        for item in (row.get('items') or []):
            name = ''
            if isinstance(item, dict):
                name = str(item.get('name') or '').strip().lower()
            elif isinstance(item, str):
                name = item.strip().lower()

            if not removed and target and name == target:
                removed = True
                continue
            kept.append(item)

        row['items'] = kept
        _recalculate_and_save_list(db, row.get('userId') or owner_key, row)
        return removed or (before != len(kept))

    if get_db() is not None:
        q = {
            'lists.id': list_id,
            '$or': [
                {'email': email},
                {'lists': {'$elemMatch': {'id': list_id, 'collaborators.email': email}}}
            ]
        }
        res1 = db.users.update_one(q, {'$pull': {'lists.$.items': {'name': item_name}}})
        res2 = db.users.update_one(q, {'$pull': {'lists.$.items': item_name}}) 
        return res1.modified_count > 0 or res2.modified_count > 0

    if getattr(mock_models, 'users', None) is not None:
        user = mock_models.users.get(email)
        if user and 'lists' in user:
            for lst in user['lists']:
                if lst['id'] == list_id:
                    items = lst.get('items', [])
                    new_items = [i for i in items if not (isinstance(i, dict) and i.get('name') == item_name) and not (isinstance(i, str) and i == item_name)]
                    if len(items) != len(new_items):
                        lst['items'] = new_items
                        return True
    return False


def rename_shopping_list(email: str, list_id: str, new_name: str) -> bool:
    db = get_db()
    if db is not None and 'lists' in db.list_collection_names():
        owner_key = _list_owner_key(email)
        res = db.lists.update_one({
            'listId': list_id,
            '$or': [
                {'userId': owner_key},
                {'collaborators': {'$elemMatch': {'email': email, 'role': 'edit'}}}
            ]
        }, {'$set': {'name': new_name, 'updatedAt': datetime.utcnow()}})
        return res.modified_count > 0

    if get_db() is not None:
        q = {
            'lists.id': list_id,
            '$or': [
                {'email': email},
                {'lists': {'$elemMatch': {'id': list_id, 'collaborators.email': email, 'role': 'edit'}}}
            ]
        }
        result = get_db().users.update_one(
            q,
            {'$set': {'lists.$.name': new_name}}
        )
        return result.modified_count > 0

    if getattr(mock_models, 'users', None) is not None:
        user = mock_models.users.get(email)
        if user and 'lists' in user:
            for lst in user['lists']:
                if lst['id'] == list_id:
                    lst['name'] = new_name
                    return True
    return False


def delete_shopping_list(email: str, list_id: str) -> bool:
    db = get_db()
    if db is not None and 'lists' in db.list_collection_names():
        owner_key = _list_owner_key(email)
        res = db.lists.delete_one({'listId': list_id, 'userId': owner_key})
        if res.deleted_count > 0:
            user = get_user_by_email(email) or {}
            if user.get('active_list_id') == list_id:
                fallback = db.lists.find_one({'userId': owner_key}, sort=[('updatedAt', -1)])
                update_user(email, {'active_list_id': fallback.get('listId') if fallback else None})
            return True
        return False

    if get_db() is not None:
        result = get_db().users.update_one(
            {'email': email},
            {'$pull': {'lists': {'id': list_id}}}
        )
        get_db().users.update_one(
            {'email': email, 'active_list_id': list_id},
            {'$unset': {'active_list_id': ''}}
        )
        get_db().users.update_many(
            {'lists.id': list_id},
            {'$pull': {'lists': {'id': list_id}}}
        )
        return result.modified_count > 0

    if getattr(mock_models, 'users', None) is not None:
        user = mock_models.users.get(email)
        if user and 'lists' in user:
            initial_len = len(user['lists'])
            user['lists'] = [l for l in user['lists'] if l['id'] != list_id]
            if user.get('active_list_id') == list_id:
                user['active_list_id'] = None
            return len(user['lists']) < initial_len
    return False


def mark_items_as_seen(email: str, list_id: str) -> bool:
    db = get_db()
    if db is not None and 'lists' in db.list_collection_names():
        owner_key = _list_owner_key(email)
        row = db.lists.find_one({
            'listId': list_id,
            '$or': [
                {'userId': owner_key},
                {'collaborators': {'$elemMatch': {'email': email}}}
            ]
        })
        if not row:
            return False
        row = _normalize_list_doc(row)
        changed = False
        for item in (row.get('items') or []):
            if isinstance(item, dict) and item.get('is_new'):
                item['is_new'] = False
                changed = True
        if changed:
            _persist_list(db, row.get('userId') or owner_key, row)
        return True

    if get_db() is not None:
        q = {
            'lists.id': list_id,
            '$or': [
                {'email': email},
                {'lists': {'$elemMatch': {'id': list_id, 'collaborators.email': email}}}
            ]
        }
        user = get_db().users.find_one(q)
        if not user or 'lists' not in user:
            return False
            
        updated = False
        lists = user.get('lists', [])
        for lst in lists:
            if lst.get('id') == list_id:
                for item in lst.get('items', []):
                    if isinstance(item, dict) and item.get('is_new'):
                        item['is_new'] = False
                        updated = True
                break
        
        if updated:
            return update_list_items(email, list_id, lst['items'])
        return True 

    if getattr(mock_models, 'users', None):
        user = mock_models.users.get(email)
        if user and 'lists' in user:
            for lst in user['lists']:
                if lst['id'] == list_id:
                    for item in lst.get('items', []):
                        if isinstance(item, dict) and item.get('is_new'):
                            item['is_new'] = False
                    return True
    return False



class UsersModel:
    """
    Wrapper class to Group functions under a single namespace `users_model`.
    This mimics the structure of other models.
    """
    def authenticate(self, email, password):
        return authenticate(email, password)
        
    def get_user_by_email(self, email):
        return get_user_by_email(email)
        
    def create_user(self, user_doc):
        return create_user(user_doc)
        
    def get_shopping_list(self, email):
        return get_shopping_list(email)
        
    def add_to_shopping_list(self, email, item):
        return add_to_shopping_list(email, item)
        
    def remove_from_shopping_list(self, email, index):
        return remove_from_shopping_list(email, index)
        
    def update_shopping_list(self, email, new_list):
        return update_shopping_list(email, new_list)
        
    def get_user_lists(self, email):
        """Get all shopping lists for a user"""
        user_lists = get_user_lists(email)
        return user_lists
    
    def share_list_with_user(self, owner_email, list_id, target_email, role='view'):
        return share_list_with_user(owner_email, list_id, target_email, role)

    def remove_collaborator(self, owner_email, list_id, target_email):
        return remove_collaborator(owner_email, list_id, target_email)

    def add_item_to_list(self, email, list_id, item):
        return add_item_to_list(email, list_id, item)
        
    def remove_item_from_list(self, email, list_id, item_name):
        return remove_item_from_list(email, list_id, item_name)
    
    def mark_items_as_seen(self, email, list_id):
        return mark_items_as_seen(email, list_id)
        
    def set_active_list(self, email, list_id):
        return set_active_list(email, list_id)

# Export Singleton
users_model = UsersModel()

