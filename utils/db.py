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

# ═══════════════════════════════════════════════════════════════════════════
# MONGODB CONNECTOR
# ═══════════════════════════════════════════════════════════════════════════
# PyMongo wrapper that connects to MongoDB Atlas
# Initialized in app.py with: mongo.init_app(app)
# 
# Collections available: users, products, stores, featured_deals, shopping_lists
# Usage: mongo.db.<collection_name>.<operation>()
mongo = PyMongo()
