"""User model helpers for auth and shopping list management.
Provides MongoDB-backed operations with in-memory fallbacks for development.
"""
from typing import Optional, List
try:
    from utils.db import mongo
    HAS_DB = True
except Exception:
    mongo = None
    HAS_DB = False

from werkzeug.security import generate_password_hash, check_password_hash

from models.models import users as MOCK_USERS


def _convert_id(doc: dict) -> dict:
    if not doc:
        return doc
    if '_id' in doc:
        doc['id'] = str(doc['_id'])
    return doc


def get_user_by_email(email: str) -> Optional[dict]:
    if not email:
        return None
    if HAS_DB and mongo is not None and getattr(mongo, 'db', None) is not None:
        doc = mongo.db.users.find_one({'email': email})
        return _convert_id(doc)
    return MOCK_USERS.get(email)


def create_user(user_doc: dict) -> str:
    """Create a user. Returns inserted id (str) or email when using mock.
    """
    # Ensure password is hashed before storing
    pwd = user_doc.get('password')
    if pwd:
        try:
            # always store a generated hash (idempotent if already hashed)
            user_doc['password'] = generate_password_hash(pwd)
        except Exception:
            pass

    if HAS_DB and mongo is not None and getattr(mongo, 'db', None) is not None:
        res = mongo.db.users.insert_one(user_doc)
        return str(res.inserted_id)
    MOCK_USERS[user_doc['email']] = user_doc
    return user_doc['email']


def authenticate(email: str, password: str) -> bool:
    user = get_user_by_email(email)
    if not user:
        return False
    stored = user.get('password')
    if not stored:
        return False
    try:
        # check against hash
        return check_password_hash(stored, password)
    except Exception:
        # fallback to plain comparison for legacy/mock entries
        return stored == password


def add_to_shopping_list(email: str, item: str) -> bool:
    if not email or not item:
        return False
    if HAS_DB and mongo is not None and getattr(mongo, 'db', None) is not None:
        res = mongo.db.users.update_one({'email': email}, {'$push': {'shopping_list': item}})
        return res.modified_count > 0
    if email in MOCK_USERS:
        MOCK_USERS[email].setdefault('shopping_list', []).append(item)
        return True
    return False


def remove_from_shopping_list(email: str, item: str) -> bool:
    if not email or not item:
        return False
    if HAS_DB and mongo is not None and getattr(mongo, 'db', None) is not None:
        # Try removing plain string entries first
        try:
            res = mongo.db.users.update_one({'email': email}, {'$pull': {'shopping_list': item}})
            if getattr(res, 'modified_count', 0) > 0:
                return True
            # If not removed, attempt to remove objects with a `name` field equal to item
            res2 = mongo.db.users.update_one({'email': email}, {'$pull': {'shopping_list': {'name': item}}})
            return getattr(res2, 'modified_count', 0) > 0
        except Exception:
            return False
    if email in MOCK_USERS and 'shopping_list' in MOCK_USERS[email]:
        try:
            MOCK_USERS[email]['shopping_list'].remove(item)
            return True
        except ValueError:
            return False
    return False


def update_shopping_list(email: str, new_list: List[str]) -> bool:
    if not email:
        return False
    if HAS_DB and mongo is not None and getattr(mongo, 'db', None) is not None:
        res = mongo.db.users.update_one({'email': email}, {'$set': {'shopping_list': new_list}})
        return res.modified_count > 0
    if email in MOCK_USERS:
        MOCK_USERS[email]['shopping_list'] = new_list
        return True
    return False


def update_profile(email: str, updates: dict) -> bool:
    if not email or not updates:
        return False
    if HAS_DB and mongo is not None and getattr(mongo, 'db', None) is not None:
        res = mongo.db.users.update_one({'email': email}, {'$set': updates})
        return res.modified_count > 0
    if email in MOCK_USERS:
        MOCK_USERS[email].update(updates)
        return True
    return False
