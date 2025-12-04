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
        return False
    stored = user.get('password')
    if stored is None:
        return False
    # Basic check — if you store hashed passwords, replace with hashing check
    return str(stored) == str(password)


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