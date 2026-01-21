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
# Collections used by this app:
# - users: Authentication and shopping lists
# - products: Core grocery item catalog
# - featured_deals: Scraped special offers
# - mb_offers: Multibuy discount rules
# 
# Usage: mongo.db.<collection_name>.<operation>()
mongo = PyMongo()

def sanitize_uri(uri):
    """
    Clean MongoDB URI of common copy-paste errors, specifically checking for
    leftover placeholders like <password> which are common user mistakes.
    
    Args:
        uri (str): The raw MongoDB URI which might contain <password> tags.
        
    Returns:
        str: The sanitized URI compatible with MongoClient.
    """
    if not uri:
        return uri
    # Check if the user accidentally left the angle brackets from the documentation
    # e.g., mongodb+srv://user:<password>@cluster...
    if '<' in uri or '>' in uri:
        # Simple string replacement to fix the malformed URI
        return uri.replace('<', '').replace('>', '')
    return uri

def get_db():
    """
    Get the active MongoDB database instance reference.
    
    Architecture Note:
    This function implements a "best effort" strategy to retrieve a DB connection
    in different runtime contexts (Flask app context vs. Standalone scripts).
    
    Strategy:
    1. FLASK CONTEXT: Try to use the shared `mongo` instance initialized by Flask.
       This is efficient because it reuses the connection pool managed by the web server.
    2. SCRIPT CONTEXT: If we are running a migration script (no Flask), creating a new
       standalone MongoClient connection.
    
    Returns:
        pymongo.database.Database: The database object ready for queries, or None on failure.
    """
    # 1. Try Flask-PyMongo (Preferred)
    # This works when we are inside a request (e.g. visiting a webpage)
    try:
        # Check if the 'db' attribute is present (it's added by init_app)
        if mongo.db is not None:
            return mongo.db
    except Exception:
        # If we access mongo.db outside a request context, it might raise an error
        # or be None. We catch this and proceed to fallback.
        pass
        
    # 2. Standalone Connection (Fallback)
    # This path is taken when running scripts like `python scripts/import.py`
    
    # Retrieve configuration from environment manually since Flask config isn't available
    mongo_uri = os.environ.get('MONGO_URI') or 'mongodb://localhost:27017/smart_grocery'
    mongo_uri = sanitize_uri(mongo_uri)
    
    database_name = os.environ.get('DATABASE_NAME')
    
    # Create a new MongoClient instance
    try:
        # PRODUCTION: Use TLS/SSL (certifi provides the Certificate Authority bundle)
        # Atlas requires TLS, so this is critical for cloud connectivity.
        client = MongoClient(mongo_uri, tlsCAFile=certifi.where(), serverSelectionTimeoutMS=5000)
    except Exception:
        try:
            # DEVELOPMENT: Retry without TLS configuration
            # This handles local MongoDB instances which often don't have SSL set up.
            client = MongoClient(mongo_uri, serverSelectionTimeoutMS=5000)
        except Exception as e:
            # If both fail, we can't talk to the database at all.
            print(f"ERROR: Could not create standalone MongoDB client: {e}")
            return None
            
    # Select the specific database from the client
    if database_name:
        return client[database_name]
    
    try:
        # 'get_default_database' uses the DB name from the connection string
        # e.g. mongodb://.../smart_grocery -> smart_grocery
        db = client.get_default_database()
        if db: return db
    except Exception:
        pass
        
    # Final fallback: Hardcoded default name
    return client['smart_grocery']


