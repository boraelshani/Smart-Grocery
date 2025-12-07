from pymongo import MongoClient
from bson import ObjectId
import os
from dotenv import load_dotenv
from typing import List, Optional
import certifi

load_dotenv()

class CountryModel:
    def __init__(self):
        mongo_uri = os.getenv('MONGO_URI') or 'mongodb://localhost:27017/smart_grocery'
        # sanitize common mistake: remove angle-brackets if user pasted URI with <...>
        if '<' in mongo_uri or '>' in mongo_uri:
            mongo_uri = mongo_uri.replace('<', '').replace('>', '')
            try:
                os.environ['MONGO_URI'] = mongo_uri
            except Exception:
                pass
        database_name = os.getenv('DATABASE_NAME', None)

        # Prefer Flask-PyMongo `mongo` if available
        try:
            from utils.db import mongo as flask_mongo
        except Exception:
            flask_mongo = None

        if flask_mongo is not None and getattr(flask_mongo, 'db', None) is not None:
            self.db = flask_mongo.db
            self.client = None
        else:
            try:
                self.client = MongoClient(mongo_uri, tlsCAFile=certifi.where())
            except TypeError:
                self.client = MongoClient(mongo_uri)
            if database_name:
                self.db = self.client[database_name]
            else:
                try:
                    self.db = self.client.get_default_database()
                    if self.db is None:
                        self.db = self.client['smart_grocery']
                except Exception:
                    self.db = self.client['smart_grocery']
        self.collection = self.db['countries']
    
    def create_country(self, country_data):
        """Create a new country"""
        result = self.collection.insert_one(country_data)
        return str(result.inserted_id)
    
    def get_all_countries(self):
        """Get all countries"""
        countries = list(self.collection.find({}))
        # Convert ObjectId to string for JSON serialization
        for country in countries:
            country['_id'] = str(country['_id'])
        return countries
    
    def get_country_by_id(self, country_id):
        """Get a country by ID"""
        try:
            country = self.collection.find_one({'_id': ObjectId(country_id)})
            if country:
                country['_id'] = str(country['_id'])
            return country
        except:
            return None
    
    def update_country(self, country_id, country_data):
        """Update a country by ID"""
        try:
            # Remove _id from update data if present
            country_data.pop('_id', None)
            result = self.collection.update_one(
                {'_id': ObjectId(country_id)},
                {'$set': country_data}
            )
            return result.modified_count > 0
        except:
            return False
    
    def delete_country(self, country_id):
        """Delete a country by ID"""
        try:
            result = self.collection.delete_one({'_id': ObjectId(country_id)})
            return result.deleted_count > 0
        except:
            return False
    
    def get_countries_starting_with_a(self):
        """Get all countries that start with the letter 'a' (case-insensitive)"""
        countries = list(self.collection.find({
            'name': {'$regex': '^a', '$options': 'i'}
        }))
        # Convert ObjectId to string for JSON serialization
        for country in countries:
            country['_id'] = str(country['_id'])
        return countries
    
    def close_connection(self):
        """Close MongoDB connection"""
        self.client.close()


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
                default_id = str(ObjectId())
                lists = [{
                    'id': default_id,
                    'name': 'My List',
                    'items': user.get('shopping_list', []),
                    'created_at': None
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
            
            # Extract item name for matching
            item_name = item.get('name') if isinstance(item, dict) else str(item)
            item_name_lower = item_name.lower().strip()
            
            # Check if item already exists
            items = target_list.get('items', [])
            existing_item = None
            existing_idx = None
            
            for idx, existing in enumerate(items):
                existing_name = existing.get('name') if isinstance(existing, dict) else str(existing)
                existing_name_lower = existing_name.lower().strip()
                
                if existing_name_lower == item_name_lower:
                    existing_item = existing
                    existing_idx = idx
                    break
            
            if existing_item is not None and existing_idx is not None:
                # Item exists - merge by incrementing quantity
                if isinstance(existing_item, dict):
                    existing_qty = existing_item.get('qty', 1)
                    add_qty = item.get('qty', 1) if isinstance(item, dict) else 1
                    merged_item = existing_item.copy()
                    merged_item['qty'] = existing_qty + add_qty
                    
                    # Update the item in the array
                    items[existing_idx] = merged_item
                    
                    result = flask_mongo.db.users.update_one(
                        {'email': email, 'shopping_lists.id': list_id},
                        {'$set': {'shopping_lists.$.items': items}}
                    )
                    return result.modified_count > 0
            
            # Item doesn't exist - add it normally
            result = flask_mongo.db.users.update_one(
                {'email': email, 'shopping_lists.id': list_id},
                {'$push': {'shopping_lists.$.items': item}}
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
                item_name = item.get('name') if isinstance(item, dict) else str(item)
                item_name_lower = item_name.lower().strip()
                
                # Check for existing item
                for idx, existing in enumerate(items):
                    existing_name = existing.get('name') if isinstance(existing, dict) else str(existing)
                    existing_name_lower = existing_name.lower().strip()
                    
                    if existing_name_lower == item_name_lower:
                        # Merge quantities
                        if isinstance(existing, dict):
                            existing_qty = existing.get('qty', 1)
                            add_qty = item.get('qty', 1) if isinstance(item, dict) else 1
                            existing['qty'] = existing_qty + add_qty
                        return True
                
                # Item doesn't exist - add it
                items.append(item)
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