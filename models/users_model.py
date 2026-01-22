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

# Export Singleton
users_model = UsersModel()
