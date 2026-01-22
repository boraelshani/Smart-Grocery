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
# IMPORT DATABASE & MOCK DATA SOURCES
# ═══════════════════════════════════════════════════════════════════════════

# Try to import Flask-PyMongo instance `mongodb` wrapper for database access.
# This prevents circular import errors if we did it at top level in some architectures.
from utils.db import get_db

# Try to import mock/fallback data for development mode
try:
    from models import models as mock_models
except Exception:
    mock_models = None


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
    # If explicitly passed None or empty string, there's nothing to find.
    if not email:
        return None
    
    # 1. DATABASE CHECK (Production Mode)
    # get_db() returns the active database connection or None if offline
    if get_db() is not None:
        # Search the 'users' collection for a document where field 'email' matches the input
        doc = get_db().users.find_one({'email': email})
        
        # If no document found, return None immediately
        if not doc:
            return None
        
        # Convert BSON document (Binary JSON) to standard Python dict
        # This makes it easier to use in the rest of the app without pymongo dependencies
        doc = dict(doc)
        
        # Convert MongoDB's internal ObjectId (which is an object) to a simple string
        # This is CRITICAL for JSON serialization (e.g. sending to frontend)
        if '_id' in doc:
            doc['id'] = str(doc['_id'])
            
        return doc
        
    # 2. FALLBACK CHECK (Development/Mock Mode)
    # This runs if get_db() returned None (DB offline)
    
    # 'getattr' safely checks if the 'mock_models' module was successfully imported
    # and if it contains a 'users' dictionary.
    if getattr(mock_models, 'users', None) is None:
        # No DB and no mock data available? We can't find the user.
        return None
        
    # Look up the user in the in-memory Python dictionary
    return mock_models.users.get(email)


def get_all_users():
    """
    Retrieve all user accounts.
    Useful for Admin dashboards or broadcasting notifications.
    """
    if get_db() is not None:
        # Return list because cursor is an iterator
        return list(get_db().users.find({}))
        
    if getattr(mock_models, 'users', None) is not None:
        return [data for email, data in mock_models.users.items()]
    return []


def hash_password(password: str) -> str:
    """
    Hash a password using bcrypt.
    
    Why Bcrypt:
    - It's slow by design (resists brute force).
    - It handles salting automatically (prevents rainbow table attacks).
    
    Args:
        password: Plain text password.
        
    Returns:
        str: Secure hash string.
    """
    if password is None:
        return ''
    if isinstance(password, bytes):
        password = password.decode('utf-8', 'ignore')
    trimmed = str(password).strip()
    if not trimmed:
        return ''
        
    # Generate salt and hash
    # .decode('utf-8') converts the resulting bytes back to a string for DB storage
    return bcrypt.hashpw(trimmed.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')


def verify_password(plain: str, hashed: str) -> bool:
    """Verify a plain password against a stored bcrypt hash."""
    if not plain or not hashed:
        return False
    try:
        # checkpw recalculates hash of 'plain' using salt from 'hashed' 
        # and compares them efficiently
        return bcrypt.checkpw(plain.encode('utf-8'), str(hashed).encode('utf-8'))
    except Exception:
        # Fail safe on encoding errors
        return False


def create_user(user_doc: dict):
    """
    Create a new user account.
    
    Args:
        user_doc: Dictionary containing user data (email, name, password_hash, etc.)
    
    Returns:
        User ID (MongoDB ObjectId as string) or email (if using mock data)
    """
    try:
        pwd = user_doc.get('password')
        # If the password is provided and not already a bcrypt hash (starts with $2), hash it.
        if pwd and not (isinstance(pwd, str) and pwd.startswith('$2')):
            user_doc['password'] = hash_password(pwd)
    except Exception:
        pass

    # PRODUCTION: Insert into MongoDB
    if get_db() is not None:
        if 'created_at' not in user_doc:
            from datetime import datetime
            user_doc['created_at'] = datetime.utcnow()
        res = get_db().users.insert_one(user_doc)
        return str(res.inserted_id) # Return the auto-generated ID
        
    # DEVELOPMENT: Insert into memory
    if getattr(mock_models, 'users', None) is None:
        return None
    if 'created_at' not in user_doc:
        from datetime import datetime
        user_doc['created_at'] = datetime.utcnow()
    mock_models.users[user_doc['email']] = user_doc
    return user_doc['email']


def authenticate(email: str, password: str) -> bool:
    """
    Authenticate a user by email and password.
    Supports both bcrypt hashes (new users) and plain text (legacy/mock users).
    
    Logic Flow:
    1. Retrieve the user document by email.
    2. Check if a password exists in the record.
    3. Determine if the stored password is encrypted (starts with '$2') or plain text.
    4. Verify accordingly.
    
    Args:
        email: User email.
        password: User input password.
        
    Returns:
        True if valid, False otherwise.
    """
    # 1. RETRIEVE USER
    user = get_user_by_email(email)
    
    # If user not found, return False immediately
    if not user:
        print(f'[AUTH] user {email} not found')
        return False
    
    # 2. GET STORED PASSWORD
    # This comes from the DB (or mock)
    stored = user.get('password')
    if stored is None:
        # User exists but has no password (maybe social login account? or bad data)
        print(f'[AUTH] user {email} has no password field')
        return False
        
    # Ensure compatible string format to avoid bytes vs string mix-ups
    stored_str = stored.decode('utf-8', 'ignore') if isinstance(stored, (bytes, bytearray)) else str(stored)

    # 3. VERIFY CREDENTIALS
    
    # CASE A: ENCRYPTED PASSWORD (BCRYPT)
    # The '$2' prefix is the standard identifier for bcrypt hashes.
    if stored_str.startswith('$2'):
        try:
            # delegated to helper function
            ok = verify_password(password, stored_str)
            print(f'[AUTH] bcrypt verify result={ok}')
            return ok
        except Exception as e:
            # If verification logic crashes, deny access securely.
            print(f'[AUTH] bcrypt verify failed: {e}')

    # CASE B: LEGACY/MOCK PASSWORD (PLAINTEXT)
    # This falls back to direct string comparison.
    # Should only happen for dummy users in development.
    print(f'[AUTH] legacy compare: stored={repr(stored_str)} vs entered={repr(password)}')
    match = stored_str.strip() == str(password).strip()
    print(f'[AUTH] legacy result={match}')
    return match


def update_shopping_list(email: str, new_list: list) -> bool:
    """Overwrite the entire shopping list for a user."""
    if not email:
        return False
        
    if get_db() is not None:
        try:
            # $set replaces the entire array
            get_db().users.update_one({'email': email}, {'$set': {'shopping_list': new_list}}, upsert=True)
            return True
        except Exception:
            return False
            
    # Mock fallback
    if getattr(mock_models, 'users', None) is None:
        return False
    u = mock_models.users.get(email)
    if not u:
        mock_models.users[email] = {'email': email, 'password': '', 'name': email, 'shopping_list': new_list, 'total_cost': 0.0}
        return True
    u['shopping_list'] = list(new_list)
    return True


def add_to_shopping_list(email: str, item) -> bool:
    """Add a single item to the user's shopping list."""
    if not email or not item:
        return False
        
    if get_db() is not None:
        try:
            # $push adds to the array. upsert=True creates user if missing.
            res = get_db().users.update_one({'email': email}, {'$push': {'shopping_list': item}}, upsert=True)
            return (getattr(res, 'modified_count', 0) > 0) or (getattr(res, 'upserted_id', None) is not None)
        except Exception:
            return False
            
    # Mock fallback
    if getattr(mock_models, 'users', None) is None:
        return False
    u = mock_models.users.get(email)
    if not u:
        mock_models.users[email] = {'email': email, 'password': '', 'name': email, 'shopping_list': [item], 'total_cost': 0.0}
        return True
    u.setdefault('shopping_list', []).append(item)
    return True


def remove_from_shopping_list(email: str, item) -> bool:
    """Remove an item from the shopping list."""
    if not email or not item:
        return False
        
    if get_db() is not None:
        try:
            # $pull removes all instances matching the value
            # Attempt 1: Remove simple string item
            res = get_db().users.update_one({'email': email}, {'$pull': {'shopping_list': item}})
            if getattr(res, 'modified_count', 0) > 0:
                return True
                
            # Attempt 2: Remove object item by name match (if shopping list contains update objects)
            res2 = get_db().users.update_one({'email': email}, {'$pull': {'shopping_list': {'name': item}}})
            return getattr(res2, 'modified_count', 0) > 0
        except Exception:
            return False
            
    # Mock fallback
    if getattr(mock_models, 'users', None) is None:
        return False
    u = mock_models.users.get(email)
    if not u:
        return False
    
    # Simple list filtering for in-memory
    new_list = [i for i in u.get('shopping_list', []) if i != item and not (isinstance(i, dict) and i.get('name') == item)]
    u['shopping_list'] = new_list
    return True


def update_user_profile(email: str, update_data: dict) -> bool:
    """
    Update user profile information.
    
    Args:
        email: User email address
        update_data: Dictionary of fields to update (name, phone, address, avatar, etc.)
    
    Returns:
        Boolean indicating success
    """
    if not email or not update_data:
        return False
        
    if get_db() is not None:
        try:
            get_db().users.update_one({'email': email}, {'$set': update_data}, upsert=True)
            return True
        except Exception as e:
            print(f"[DB ERROR] Failed to update user profile: {e}")
            return False
            
    # Mock fallback
    u = (mock_models.users.get(email)) if mock_models else None
    if u:
        u.update(update_data)
        return True
    return False


def update_user(email: str, update_data: dict) -> bool:
    """Generic update for user document. Same as update_user_profile but generic name."""
    return update_user_profile(email, update_data)


# Multi-List Shopping List Functions
try:
    from utils.db import mongo as flask_mongo
except:
    flask_mongo = None

def get_user_lists(email: str) -> dict:
    """
    Get all shopping lists for a user. 
    Handles migration from single 'shopping_list' to multiple 'shopping_lists'.
    
    Returns:
        dict: {'lists': [...], 'active_list_id': ...}
    """
    if not email:
        return {'lists': [], 'active_list_id': None}
    
    if get_db() is not None:
        try:
            user = get_db().users.find_one({'email': email})
            if not user:
                return {'lists': [], 'active_list_id': None}
            
            lists = user.get('shopping_lists', [])
            active_id = user.get('active_list_id')
            
            # Migration Logic: If old list exists but no new lists, assume default list
            if not lists and user.get('shopping_list'):
                from bson import ObjectId
                default_list = {
                     'id': str(ObjectId()),
                     'name': 'My List',
                     'items': user.get('shopping_list', []),
                     'created_at': datetime.utcnow()
                }
                # Update DB with new structure
                get_db().users.update_one(
                    {'email': email},
                    {'$set': {'shopping_lists': [default_list], 'active_list_id': default_list['id']}}
                )
                return {'lists': [default_list], 'active_list_id': default_list['id']}
                
            return {'lists': lists, 'active_list_id': active_id}
        except Exception:
            return {'lists': [], 'active_list_id': None}
            
    # Mock data fallback (Used if MongoDB is unavailable)
    if mock_models:
        u = mock_models.users.get(email, {})
        return {'lists': u.get('shopping_lists', []), 'active_list_id': u.get('active_list_id')}
        
    return {'lists': [], 'active_list_id': None}


def create_shopping_list(email: str, list_name: str) -> Optional[str]:
    """Create a new shopping list. Returns the new list ID."""
    if not email or not list_name:
        return None
    
    from bson import ObjectId
    from datetime import datetime
    
    new_list = {
        'id': str(ObjectId()),
        'name': list_name.strip(),
        'items': [],
        'created_at': datetime.utcnow().isoformat()
    }
    
    if get_db() is not None:
        try:
            result = get_db().users.update_one(
                {'email': email},
                {'$push': {'shopping_lists': new_list}}
            )
            if result.modified_count > 0 or result.upserted_id:
                return new_list['id']
            # If user doesn't exist in DB, create them
            if result.matched_count == 0:
                 get_db().users.insert_one({
                     'email': email,
                     'shopping_lists': [new_list],
                     'active_list_id': new_list['id']
                 })
                 return new_list['id']
        except Exception as e:
            print(f'Error creating list: {e}')
            return None
    
    # Mock fallback
    if mock_models:
        if email not in mock_models.users:
            mock_models.users[email] = {'email': email, 'shopping_lists': []}
        u = mock_models.users[email]
        u.setdefault('shopping_lists', []).append(new_list)
        return new_list['id']
    return None


def rename_shopping_list(email: str, list_id: str, new_name: str) -> bool:
    """Rename a shopping list."""
    if not email or not list_id or not new_name:
        return False
    
    if get_db() is not None:
        try:
            result = get_db().users.update_one(
                {'email': email, 'shopping_lists.id': list_id},
                {'$set': {'shopping_lists.$.name': new_name.strip()}}
            )
            return result.modified_count > 0
        except Exception as e:
            print(f'Error renaming list: {e}')
            return False
    
    # Mock fallback
    if mock_models and hasattr(mock_models, 'users'):
        u = mock_models.users.get(email)
        if u:
            for lst in u.get('shopping_lists', []):
                if lst.get('id') == list_id:
                    lst['name'] = new_name.strip()
                    return True
    return False


def delete_shopping_list(email: str, list_id: str) -> bool:
    """Delete a shopping list."""
    if not email or not list_id:
        return False
    
    if get_db() is not None:
        try:
            result = get_db().users.update_one(
                {'email': email},
                {'$pull': {'shopping_lists': {'id': list_id}}}
            )
            # If deleted list was active, set active to first remaining list
            user = get_db().users.find_one({'email': email})
            # Since we just pulled the list, it won't be in shopping_lists.
            # But active_list_id might still point to it.
            if user and user.get('active_list_id') == list_id:
                remaining_lists = user.get('shopping_lists', [])
                new_active = remaining_lists[0]['id'] if remaining_lists else None
                get_db().users.update_one(
                    {'email': email},
                    {'$set': {'active_list_id': new_active}}
                )
            return result.modified_count > 0
        except Exception as e:
            import traceback
            traceback.print_exc()
            print(f'Error deleting list: {e}')
            return False
    
    # Mock fallback
    if mock_models and hasattr(mock_models, 'users'):
        u = mock_models.users.get(email)
        if u:
            lists = u.get('shopping_lists', [])
            u['shopping_lists'] = [lst for lst in lists if lst.get('id') != list_id]
            if u.get('active_list_id') == list_id:
                u['active_list_id'] = u['shopping_lists'][0]['id'] if u['shopping_lists'] else None
            return True
    return False


def set_active_list(email: str, list_id: str) -> bool:
    """Set the active shopping list for a user."""
    if not email or not list_id:
        return False
    
    if get_db() is not None:
        try:
            result = get_db().users.update_one(
                {'email': email},
                {'$set': {'active_list_id': list_id}}
            )
            return result.modified_count > 0
        except Exception as e:
            print(f'Error setting active list: {e}')
            return False
    
    # Mock fallback
    if mock_models and hasattr(mock_models, 'users'):
        u = mock_models.users.get(email)
        if u:
            u['active_list_id'] = list_id
            return True
    return False


def update_list_items(email: str, list_id: str, items: list) -> bool:
    """Update items in a specific shopping list."""
    if not email or not list_id:
        return False
    
    if get_db() is not None:
        try:
            result = get_db().users.update_one(
                {'email': email, 'shopping_lists.id': list_id},
                {'$set': {'shopping_lists.$.items': items}}
            )
            return result.modified_count > 0
        except Exception as e:
            import traceback
            traceback.print_exc()
            print(f'Error updating list items: {e}')
            return False
    
    # Mock fallback
    if mock_models and hasattr(mock_models, 'users'):
        u = mock_models.users.get(email)
        if u:
            for lst in u.get('shopping_lists', []):
                if lst.get('id') == list_id:
                    lst['items'] = items
                    return True
    return False


def add_item_to_list(email: str, list_id: str, item) -> bool:
    """Add an item to a specific shopping list. Merges duplicates by incrementing quantity."""
    if not email or not list_id or not item:
        return False

    def _normalize_name_store(entry):
        if isinstance(entry, dict):
            name_val = entry.get('name') if entry.get('name') is not None else entry.get('title')
            store_val = entry.get('store') or entry.get('store_name') or ''
        else:
            name_val = str(entry)
            store_val = ''
        return (str(name_val or '').strip().lower(), str(store_val or '').strip().lower())

    def _coerce_qty(entry):
        try:
            if isinstance(entry, dict):
                q = entry.get('qty', entry.get('quantity', 1))
            else:
                q = 1
            q_int = int(q)
            return q_int if q_int > 0 else 1
        except Exception:
            return 1

    def _normalize_price_val(entry):
        if not isinstance(entry, dict):
            return None
        raw = entry.get('price_val', entry.get('price'))
        try:
            if isinstance(raw, Decimal128):
                return float(raw.to_decimal())
            if isinstance(raw, (int, float)):
                return float(raw)
            if isinstance(raw, str):
                cleaned = re.sub(r"[^0-9.]+", "", raw)
                return float(cleaned) if cleaned else None
        except Exception:
            return None
        return None

    # Ensure item is a dict so we keep metadata like store and price
    item_obj = dict(item) if isinstance(item, dict) else {'name': str(item)}
    if 'qty' not in item_obj and 'quantity' not in item_obj:
        item_obj['qty'] = 1
    price_val = _normalize_price_val(item_obj)
    if price_val is not None:
        item_obj.setdefault('price_val', price_val)
        # keep a plain price field for legacy consumers
        item_obj.setdefault('price', price_val)
    target_key = _normalize_name_store(item_obj)
    
    if get_db() is not None:
        try:
            # Get current list to check for duplicates
            user = get_db().users.find_one({'email': email})
            if not user:
                return False
            
            # Find the target list
            target_list = None
            list_index = None
            for idx, lst in enumerate(user.get('shopping_lists', [])):
                if lst.get('id') == list_id:
                    target_list = lst
                    list_index = idx
                    break
            
            if target_list is None:
                return False
            
            # Check if item already exists (name + store match)
            # BUT: if item has a multi-buy offer, don't merge - add as separate entry
            items = target_list.get('items', [])
            existing_idx = None
            
            has_multibuy_offer = False  # buyXgetY handled via effective pricing; allow merge

            if not has_multibuy_offer:
                # Only merge if no multi-buy offer (currently always merge)
                for idx, existing in enumerate(items):
                    if _normalize_name_store(existing) == target_key:
                        existing_idx = idx
                        break

            if existing_idx is not None:
                existing_item = items[existing_idx]
                merged_item = existing_item.copy() if isinstance(existing_item, dict) else {'name': str(existing_item)}
                merged_item['qty'] = _coerce_qty(existing_item) + _coerce_qty(item_obj)
                merged_item['is_new'] = True  # Mark as new even if merged
                if not merged_item.get('store') and item_obj.get('store'):
                    merged_item['store'] = item_obj.get('store')
                if not merged_item.get('image') and item_obj.get('image'):
                    merged_item['image'] = item_obj.get('image')
                # Ensure discount offers/tiers are attached to the merged item
                if item_obj.get('discount_tiers'):
                    merged_item['discount_tiers'] = item_obj.get('discount_tiers')
                if item_obj.get('discount_label'):
                    merged_item['discount_label'] = item_obj.get('discount_label')
                if item_obj.get('offer'):
                    merged_item['offer'] = item_obj.get('offer')
                if price_val is not None:
                    if merged_item.get('price_val') in (None, '', 0):
                        merged_item['price_val'] = price_val
                    if merged_item.get('price') in (None, '', 0):
                        merged_item['price'] = price_val
                items[existing_idx] = merged_item
            else:
                item_obj['is_new'] = True  # New item added
                items.append(item_obj)

            result = get_db().users.update_one(
                {'email': email, 'shopping_lists.id': list_id},
                {'$set': {'shopping_lists.$.items': items}}
            )
            return result.modified_count > 0
        except Exception as e:
            print(f'Error adding item to list: {e}')
            return False
    
    # Mock fallback
    if mock_models and hasattr(mock_models, 'users'):
        u = mock_models.users.get(email)
        if u:
            for lst in u.get('shopping_lists', []):
                if lst.get('id') == list_id:
                    items = lst.setdefault('items', [])
                    existing_idx = None

                    has_multibuy_offer = False  # buyXgetY handled via effective pricing; allow merge

                    if not has_multibuy_offer:
                        for idx, existing in enumerate(items):
                            if _normalize_name_store(existing) == target_key:
                                existing_idx = idx
                                break

                    if existing_idx is not None:
                        existing_item = items[existing_idx]
                        merged_item = existing_item.copy() if isinstance(existing_item, dict) else {'name': str(existing_item)}
                        merged_item['qty'] = _coerce_qty(existing_item) + _coerce_qty(item_obj)
                        merged_item['is_new'] = True
                        if not merged_item.get('store') and item_obj.get('store'):
                            merged_item['store'] = item_obj.get('store')
                        if not merged_item.get('image') and item_obj.get('image'):
                            merged_item['image'] = item_obj.get('image')
                        if price_val is not None:
                            if merged_item.get('price_val') in (None, '', 0):
                                merged_item['price_val'] = price_val
                            if merged_item.get('price') in (None, '', 0):
                                merged_item['price'] = price_val
                        items[existing_idx] = merged_item
                        return True

                    # Item doesn't exist - add it or multibuy should stay separate
                    item_obj['is_new'] = True
                    items.append(item_obj)
                    return True
    return False


def mark_items_as_seen(email: str, list_id: str) -> bool:
    """Clear the 'is_new' flag from all items in a specific list."""
    if not email or not list_id:
        return False
    
    if get_db() is not None:
        try:
            user = get_db().users.find_one({'email': email})
            if not user:
                return False
            
            for lst in user.get('shopping_lists', []):
                if lst.get('id') == list_id:
                    items = lst.get('items', [])
                    changed = False
                    for item in items:
                        if isinstance(item, dict) and item.get('is_new'):
                            item['is_new'] = False
                            changed = True
                    
                    if changed:
                        get_db().users.update_one(
                            {'email': email, 'shopping_lists.id': list_id},
                            {'$set': {'shopping_lists.$.items': items}}
                        )
                    return True
            return False
        except Exception as e:
            print(f"Error marking items as seen: {e}")
            return False
    
    # Mock fallback
    u = mock_models.users.get(email) if (mock_models and email) else None
    if u:
        for lst in u.get('shopping_lists', []):
            if lst.get('id') == list_id:
                for item in lst.get('items', []):
                    if isinstance(item, dict):
                        item['is_new'] = False
                return True
    return False

def remove_item_from_list(email: str, list_id: str, item_name: str) -> bool:
    """Remove an item from a specific shopping list."""
    if not email or not list_id or not item_name:
        return False
    
    if get_db() is not None:
        try:
            # Try removing by name string
            result = get_db().users.update_one(
                {'email': email, 'shopping_lists.id': list_id},
                {'$pull': {'shopping_lists.$.items': item_name}}
            )
            if result.modified_count > 0:
                return True
            # Try removing by name field in object
            result = get_db().users.update_one(
                {'email': email, 'shopping_lists.id': list_id},
                {'$pull': {'shopping_lists.$.items': {'name': item_name}}}
            )
            return result.modified_count > 0
        except Exception as e:
            print(f'Error removing item from list: {e}')
            return False
    
    # Mock fallback
    u = mock_models.users.get(email) if mock_models else None
    if u:
        for lst in u.get('shopping_lists', []):
            if lst.get('id') == list_id:
                items = lst.get('items', [])
                # Remove string matches
                while item_name in items:
                    items.remove(item_name)
                # Remove objects with matching name
                lst['items'] = [it for it in items if not (isinstance(it, dict) and it.get('name') == item_name)]
                return True
    return False

def mark_dynamic_notifications_read(email: str, notification_ids: List[str]):
    """
    Mark dynamic notifications (suggestions) as read for a user.
    """
    if not email or not notification_ids:
        return False
        
    try:
        if flask_mongo:
            get_db().users.update_one(
                {'email': email},
                {'$addToSet': {'read_dynamic_notifications': {'$each': notification_ids}}}
            )
            return True
            
        # Mock fallback could go here
        return True
    except Exception as e:
        print(f"Error marking dynamic notifications read: {e}")
        return False

class UsersModel:
    """Wrapper class for user functions."""
    def get_user_by_email(self, email): return get_user_by_email(email)
    def update_user(self, email, update_data): return update_user(email, update_data)
    def update_user_profile(self, email, update_data): return update_user_profile(email, update_data)
    def create_user(self, user_doc): return create_user(user_doc)
    def authenticate(self, email, password): return authenticate(email, password)
    def get_user_lists(self, email): return get_user_lists(email)
    def create_shopping_list(self, email, list_name): return create_shopping_list(email, list_name)
    def rename_shopping_list(self, email, list_id, new_name): return rename_shopping_list(email, list_id, new_name)
    def delete_shopping_list(self, email, list_id): return delete_shopping_list(email, list_id)
    def set_active_list(self, email, list_id): return set_active_list(email, list_id)
    def add_item_to_list(self, email, list_id, item): return add_item_to_list(email, list_id, item)
    def remove_item_from_list(self, email, list_id, item_name): return remove_item_from_list(email, list_id, item_name)
    def update_list_items(self, email, list_id, items): return update_list_items(email, list_id, items)
    def mark_items_as_seen(self, email, list_id): return mark_items_as_seen(email, list_id)
    def mark_dynamic_notifications_read(self, email, ids): return mark_dynamic_notifications_read(email, ids)

users_model = UsersModel()
