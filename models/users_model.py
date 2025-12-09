from pymongo import MongoClient
from bson import ObjectId
from bson.decimal128 import Decimal128
import os
import re
from dotenv import load_dotenv
from typing import List, Optional
import certifi

load_dotenv()

# Backwards-compatible user helpers expected by routes/auth_routes.py
try:
    from utils.db import mongo as flask_mongo
except Exception:
    flask_mongo = None

try:
    from models import models as mock_models
except Exception:
    mock_models = None


def get_user_by_email(email: str):
    if not email:
        return None
    if flask_mongo is not None and getattr(flask_mongo, 'db', None) is not None:
        doc = flask_mongo.db.users.find_one({'email': email})
        if not doc:
            return None
        doc = dict(doc)
        if '_id' in doc:
            doc['id'] = str(doc['_id'])
        return doc
    # fallback to in-memory mock data
    if getattr(mock_models, 'users', None) is None:
        return None
    return mock_models.users.get(email)


def create_user(user_doc: dict):
    if flask_mongo is not None and getattr(flask_mongo, 'db', None) is not None:
        res = flask_mongo.db.users.insert_one(user_doc)
        return str(res.inserted_id)
    if getattr(mock_models, 'users', None) is None:
        return None
    mock_models.users[user_doc['email']] = user_doc
    return user_doc['email']


def authenticate(email: str, password: str) -> bool:
    user = get_user_by_email(email)
    if not user:
        print(f'[AUTH] user {email} not found')
        return False
    stored = user.get('password')
    if stored is None:
        print(f'[AUTH] user {email} has no password field')
        return False
    # Basic check — if you store hashed passwords, replace with hashing check
    print(f'[AUTH] comparing: stored={repr(stored)} (type={type(stored).__name__}) vs entered={repr(password)} (type={type(password).__name__})')
    match = str(stored).strip() == str(password).strip()
    print(f'[AUTH] result={match}')
    return match


def update_shopping_list(email: str, new_list: list) -> bool:
    if not email:
        return False
    if flask_mongo is not None and getattr(flask_mongo, 'db', None) is not None:
        try:
            flask_mongo.db.users.update_one({'email': email}, {'$set': {'shopping_list': new_list}}, upsert=True)
            return True
        except Exception:
            return False
    if getattr(mock_models, 'users', None) is None:
        return False
    u = mock_models.users.get(email)
    if not u:
        mock_models.users[email] = {'email': email, 'password': '', 'name': email, 'shopping_list': new_list, 'total_cost': 0.0}
        return True
    u['shopping_list'] = list(new_list)
    return True


def add_to_shopping_list(email: str, item) -> bool:
    if not email or not item:
        return False
    if flask_mongo is not None and getattr(flask_mongo, 'db', None) is not None:
        try:
            res = flask_mongo.db.users.update_one({'email': email}, {'$push': {'shopping_list': item}}, upsert=True)
            return (getattr(res, 'modified_count', 0) > 0) or (getattr(res, 'upserted_id', None) is not None)
        except Exception:
            return False
    if getattr(mock_models, 'users', None) is None:
        return False
    u = mock_models.users.get(email)
    if not u:
        mock_models.users[email] = {'email': email, 'password': '', 'name': email, 'shopping_list': [item], 'total_cost': 0.0}
        return True
    u.setdefault('shopping_list', []).append(item)
    return True


def remove_from_shopping_list(email: str, item) -> bool:
    if not email or not item:
        return False
    if flask_mongo is not None and getattr(flask_mongo, 'db', None) is not None:
        try:
            res = flask_mongo.db.users.update_one({'email': email}, {'$pull': {'shopping_list': item}})
            if getattr(res, 'modified_count', 0) > 0:
                return True
            res2 = flask_mongo.db.users.update_one({'email': email}, {'$pull': {'shopping_list': {'name': item}}})
            return getattr(res2, 'modified_count', 0) > 0
        except Exception:
            return False
    if getattr(mock_models, 'users', None) is None:
        return False
    u = mock_models.users.get(email)
    if not u:
        return False
    lst = u.get('shopping_list', [])
    try:
        # remove string matches
        while item in lst:
            lst.remove(item)
        # remove objects with name field
        lst[:] = [it for it in lst if not (isinstance(it, dict) and it.get('name') == item)]
        u['shopping_list'] = lst
        return True
    except Exception:
        return False


# Multi-List Shopping List Functions
try:
    from utils.db import mongo as flask_mongo
except:
    flask_mongo = None

def get_user_lists(email: str) -> dict:
    """Get all shopping lists for a user. Returns dict with lists array and active_list_id."""
    if not email:
        return {'lists': [], 'active_list_id': None}
    
    if flask_mongo is not None and getattr(flask_mongo, 'db', None) is not None:
        try:
            user = flask_mongo.db.users.find_one({'email': email})
            if not user:
                return {'lists': [], 'active_list_id': None}
            
            lists = user.get('shopping_lists', [])
            active_id = user.get('active_list_id')
            
            # Migrate old shopping_list to new format if needed
            if not lists and user.get('shopping_list'):
                from bson import ObjectId
                from datetime import datetime
                default_id = str(ObjectId())
                lists = [{
                    'id': default_id,
                    'name': 'My List',
                    'items': user.get('shopping_list', []),
                    'created_at': datetime.utcnow().isoformat()
                }]
                flask_mongo.db.users.update_one(
                    {'email': email},
                    {'$set': {'shopping_lists': lists, 'active_list_id': default_id}}
                )
                active_id = default_id
            
            return {'lists': lists, 'active_list_id': active_id}
        except Exception as e:
            print(f'Error getting user lists: {e}')
            return {'lists': [], 'active_list_id': None}
    
    # Mock data fallback
    u = mock_models.users.get(email, {})
    return {'lists': u.get('shopping_lists', []), 'active_list_id': u.get('active_list_id')}


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
    
    if flask_mongo is not None and getattr(flask_mongo, 'db', None) is not None:
        try:
            result = flask_mongo.db.users.update_one(
                {'email': email},
                {'$push': {'shopping_lists': new_list}}
            )
            if result.modified_count > 0 or result.upserted_id:
                return new_list['id']
        except Exception as e:
            print(f'Error creating list: {e}')
            return None
    
    # Mock fallback
    u = mock_models.users.get(email)
    if u:
        u.setdefault('shopping_lists', []).append(new_list)
        return new_list['id']
    return None


def rename_shopping_list(email: str, list_id: str, new_name: str) -> bool:
    """Rename a shopping list."""
    if not email or not list_id or not new_name:
        return False
    
    if flask_mongo is not None and getattr(flask_mongo, 'db', None) is not None:
        try:
            result = flask_mongo.db.users.update_one(
                {'email': email, 'shopping_lists.id': list_id},
                {'$set': {'shopping_lists.$.name': new_name.strip()}}
            )
            return result.modified_count > 0
        except Exception as e:
            print(f'Error renaming list: {e}')
            return False
    
    # Mock fallback
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
    
    if flask_mongo is not None and getattr(flask_mongo, 'db', None) is not None:
        try:
            result = flask_mongo.db.users.update_one(
                {'email': email},
                {'$pull': {'shopping_lists': {'id': list_id}}}
            )
            # If deleted list was active, set active to first remaining list
            user = flask_mongo.db.users.find_one({'email': email})
            if user and user.get('active_list_id') == list_id:
                remaining_lists = user.get('shopping_lists', [])
                new_active = remaining_lists[0]['id'] if remaining_lists else None
                flask_mongo.db.users.update_one(
                    {'email': email},
                    {'$set': {'active_list_id': new_active}}
                )
            return result.modified_count > 0
        except Exception as e:
            print(f'Error deleting list: {e}')
            return False
    
    # Mock fallback
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
    
    if flask_mongo is not None and getattr(flask_mongo, 'db', None) is not None:
        try:
            result = flask_mongo.db.users.update_one(
                {'email': email},
                {'$set': {'active_list_id': list_id}}
            )
            return result.modified_count > 0
        except Exception as e:
            print(f'Error setting active list: {e}')
            return False
    
    # Mock fallback
    u = mock_models.users.get(email)
    if u:
        u['active_list_id'] = list_id
        return True
    return False


def update_list_items(email: str, list_id: str, items: list) -> bool:
    """Update items in a specific shopping list."""
    if not email or not list_id:
        return False
    
    if flask_mongo is not None and getattr(flask_mongo, 'db', None) is not None:
        try:
            result = flask_mongo.db.users.update_one(
                {'email': email, 'shopping_lists.id': list_id},
                {'$set': {'shopping_lists.$.items': items}}
            )
            return result.modified_count > 0
        except Exception as e:
            print(f'Error updating list items: {e}')
            return False
    
    # Mock fallback
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
    
    if flask_mongo is not None and getattr(flask_mongo, 'db', None) is not None:
        try:
            # Get current list to check for duplicates
            user = flask_mongo.db.users.find_one({'email': email})
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
                if not merged_item.get('store') and item_obj.get('store'):
                    merged_item['store'] = item_obj.get('store')
                if price_val is not None:
                    if merged_item.get('price_val') in (None, '', 0):
                        merged_item['price_val'] = price_val
                    if merged_item.get('price') in (None, '', 0):
                        merged_item['price'] = price_val
                items[existing_idx] = merged_item
            else:
                items.append(item_obj)

            result = flask_mongo.db.users.update_one(
                {'email': email, 'shopping_lists.id': list_id},
                {'$set': {'shopping_lists.$.items': items}}
            )
            return result.modified_count > 0
        except Exception as e:
            print(f'Error adding item to list: {e}')
            return False
    
    # Mock fallback
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
                    if not merged_item.get('store') and item_obj.get('store'):
                        merged_item['store'] = item_obj.get('store')
                    if price_val is not None:
                        if merged_item.get('price_val') in (None, '', 0):
                            merged_item['price_val'] = price_val
                        if merged_item.get('price') in (None, '', 0):
                            merged_item['price'] = price_val
                    items[existing_idx] = merged_item
                    return True

                # Item doesn't exist - add it or multibuy should stay separate
                items.append(item_obj)
                return True
    return False


def remove_item_from_list(email: str, list_id: str, item_name: str) -> bool:
    """Remove an item from a specific shopping list."""
    if not email or not list_id or not item_name:
        return False
    
    if flask_mongo is not None and getattr(flask_mongo, 'db', None) is not None:
        try:
            # Try removing by name string
            result = flask_mongo.db.users.update_one(
                {'email': email, 'shopping_lists.id': list_id},
                {'$pull': {'shopping_lists.$.items': item_name}}
            )
            if result.modified_count > 0:
                return True
            # Try removing by name field in object
            result = flask_mongo.db.users.update_one(
                {'email': email, 'shopping_lists.id': list_id},
                {'$pull': {'shopping_lists.$.items': {'name': item_name}}}
            )
            return result.modified_count > 0
        except Exception as e:
            print(f'Error removing item from list: {e}')
            return False
    
    # Mock fallback
    u = mock_models.users.get(email)
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