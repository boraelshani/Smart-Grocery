from pymongo import MongoClient
from bson import ObjectId
import os
from dotenv import load_dotenv

load_dotenv()

class CountryModel:
    def __init__(self):
        mongo_uri = os.getenv('MONGO_URI', 'mongodb://localhost:27017/smart_grocery')
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