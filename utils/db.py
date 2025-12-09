from flask_pymongo import PyMongo

# DATABASE CONNECTOR: Wraps PyMongo to talk to MongoDB
# Usage: mongo.db.products.find(), mongo.db.users.insert_one(), etc.
mongo = PyMongo()
