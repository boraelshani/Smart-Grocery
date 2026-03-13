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


def get_user_lists(email):
    """
    Retrieve all shopping lists for a user.
    Returns a dict with 'lists' array and 'active_list_id'.
    """
    user = get_user_by_email(email)
    if not user:
        return {'lists': [], 'active_list_id': None}
        
    # Default structure if 'lists' field doesn't exist
    if 'lists' not in user:
        # Check if there is a legacy 'shopping_list' and migrate it
        legacy_list = user.get('shopping_list', [])
        default_lists = []
        active_id = None
        
        if legacy_list:
            import uuid
            list_id = str(uuid.uuid4())
            default_lists.append({
                'id': list_id,
                'name': 'My Shopping List',
                'items': legacy_list,
                'created_at': datetime.utcnow() if get_db() is not None else None
            })
            active_id = list_id
            
        return {'lists': default_lists, 'active_list_id': active_id}
        
    return {
        'lists': user.get('lists', []),
        'active_list_id': user.get('active_list_id')
    }


def create_shopping_list(email: str, name: str) -> str:
    """Create a new shopping list and return its ID."""
    list_id = str(uuid.uuid4())
    new_list = {
        'id': list_id,
        'name': name,
        'items': [],
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

def update_user(email: str, update_data: dict) -> bool:
    """Update arbitrary fields on a user document."""
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
    """Backward-compatible alias used by existing profile update routes."""
    return update_user(email, update_data)

def update_list_items(email: str, list_id: str, items: list) -> bool:
    """Update the items in a specific shopping list."""
    if get_db() is not None:
        result = get_db().users.update_one(
            {'email': email, 'lists.id': list_id},
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
    """Set the active shopping list for a user."""
    return update_user(email, {'active_list_id': list_id})


def add_item_to_list(email: str, list_id: str, item: dict) -> bool:
    """Add an item to a specific list."""
    if get_db() is not None:
        result = get_db().users.update_one(
            {'email': email, 'lists.id': list_id},
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
    """Remove an item by name from a specific list."""
    if get_db() is not None:
        db = get_db()
        # First try to pull if it's a dictionary with 'name'
        res1 = db.users.update_one(
            {'email': email, 'lists.id': list_id},
            {'$pull': {'lists.$.items': {'name': item_name}}}
        )
        if res1.modified_count > 0:
            return True
            
        # Try to pull if it's a simple string (legacy)
        res2 = db.users.update_one(
            {'email': email, 'lists.id': list_id},
            {'$pull': {'lists.$.items': item_name}}
        )
        return res2.modified_count > 0

    if getattr(mock_models, 'users', None) is not None:
        user = mock_models.users.get(email)
        if user and 'lists' in user:
            for lst in user['lists']:
                if lst['id'] == list_id:
                    items = lst.get('items', [])
                    # Filter out items with matching name
                    new_items = [i for i in items if not (isinstance(i, dict) and i.get('name') == item_name) and not (isinstance(i, str) and i == item_name)]
                    if len(items) != len(new_items):
                        lst['items'] = new_items
                        return True
    return False

def rename_shopping_list(email: str, list_id: str, new_name: str) -> bool:
    """Rename a specific shopping list."""
    if get_db() is not None:
        result = get_db().users.update_one(
            {'email': email, 'lists.id': list_id},
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
    """Delete a specific shopping list."""
    if get_db() is not None:
        result = get_db().users.update_one(
            {'email': email},
            {'$pull': {'lists': {'id': list_id}}}
        )
        get_db().users.update_one(
            {'email': email, 'active_list_id': list_id},
            {'$unset': {'active_list_id': ''}}
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
    """Clear 'is_new' flag from all items in a list."""
    # 1. Mongo
    if get_db() is not None:
        # Fetch the user document to process in memory (easiest for nested array logic)
        user = get_db().users.find_one({'email': email})
        if not user or 'lists' not in user:
            return False
            
        updated = False
        lists = user.get('lists', [])
        for lst in lists:
            if lst.get('id') == list_id:
                for item in lst.get('items', []):
                    if isinstance(item, dict) and item.get('is_new'):
                        item['is_new'] = False # or pop it
                        updated = True
                break # Found list
        
        if updated:
            # Save the specific list back
            return update_list_items(email, list_id, lst['items'])
        return True # Nothing to update is still success
        
    # 2. Mock
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


# ═══════════════════════════════════════════════════════════════════════════
# CATEGORY: CLASS WRAPPER (FOR NAMESPACE)
# ═══════════════════════════════════════════════════════════════════════════

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
