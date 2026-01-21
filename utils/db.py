"""
═══════════════════════════════════════════════════════════════════════════
DATABASE UTILITY MODULE
═══════════════════════════════════════════════════════════════════════════
Initializes and exports the PyMongo instance for database connectivity.

Usage throughout the app:
    from utils.db import mongo
    users = mongo.db.users.find()
    mongo.db.products.insert_one(product_doc)
═══════════════════════════════════════════════════════════════════════════
"""

from flask_pymongo import PyMongo
from pymongo import MongoClient
import os
import certifi

# ═══════════════════════════════════════════════════════════════════════════
# MONGODB CONNECTOR
# ═══════════════════════════════════════════════════════════════════════════
# PyMongo wrapper that connects to MongoDB Atlas
# Initialized in app.py with: mongo.init_app(app)
# 
# Collections available: users, products, stores, featured_deals, shopping_lists
# Usage: mongo.db.<collection_name>.<operation>()
mongo = PyMongo()

def sanitize_uri(uri):
    """
    Clean MongoDB URI of common copy-paste errors (angle brackets).
    
    Args:
        uri (str): The raw MongoDB URI which might contain <password> tags.
        
    Returns:
        str: The sanitized URI.
    """
    if not uri:
        return uri
    # Users often copy strings like "mongodb://user:<password>@..."
    # This helper defensively removes the brackets.
    if '<' in uri or '>' in uri:
        return uri.replace('<', '').replace('>', '')
    return uri

def get_db():
    """
    Get the MongoDB database instance reference.
    
    Strategy:
    1. Try to use the Flask-PyMongo instance initialized with the current App Context.
    2. If that fails (e.g. running a script outside Flask), create a standalone connection.
    
    Returns:
        pymongo.database.Database: The database object ready for queries.
    """
    # 1. Try Flask-PyMongo (if configured and app context active)
    try:
        # Check if extension is initialized
        if mongo.db is not None:
            return mongo.db
    except Exception:
        # We are likely outside of a Flask request context
        pass
        
    # 2. Standalone Connection (Fallback for Scripts/CLI)
    mongo_uri = os.environ.get('MONGO_URI') or 'mongodb://localhost:27017/smart_grocery'
    mongo_uri = sanitize_uri(mongo_uri)

    
    database_name = os.environ.get('DATABASE_NAME')
    
    # Create client
    try:
        # standard connection with TLS (security requirement for Atlas)
        client = MongoClient(mongo_uri, tlsCAFile=certifi.where(), serverSelectionTimeoutMS=5000)
    except Exception:
        try:
            # fallback without TLS config (for local DBs)
            client = MongoClient(mongo_uri, serverSelectionTimeoutMS=5000)
        except Exception as e:
            print(f"ERROR: Could not create standalone MongoDB client: {e}")
            return None
            
    # Select database
    if database_name:
        return client[database_name]
    
    try:
        # Try getting the default database from the connection string
        db = client.get_default_database()
        if db: return db
    except Exception:
        pass
        
    # Final fallback if no DB specified in URI
    return client['smart_grocery']


