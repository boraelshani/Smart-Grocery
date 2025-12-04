#!/usr/bin/env python3
"""Simple DB check script that prints document counts for key collections.
This minimal version ensures dotenv is loaded and prints the resolved MONGO_URI.
"""
from dotenv import load_dotenv
import os
from pymongo import MongoClient

load_dotenv()

MONGO_URI = os.getenv('MONGO_URI') or os.getenv('MONGODB_URI') or 'mongodb://localhost:27017/smart_grocery'
print('Using MONGO_URI:', MONGO_URI)

client = MongoClient(MONGO_URI)
db_name = None
if '/' in MONGO_URI and MONGO_URI.rsplit('/', 1)[-1]:
    db_name = MONGO_URI.rsplit('/', 1)[-1]
db = client.get_database(db_name) if db_name else client['smart_grocery']

print('DB name:', db.name)
for coll in ['products', 'stores', 'featured_deals', 'users']:
    exists = coll in db.list_collection_names()
    cnt = db[coll].count_documents({}) if exists else 0
    print(f'{coll}: exists={exists}, count={cnt}')
"""Quick DB check script that prints document counts for key collections.

This script will load a `.env` file if present and prefer the `MONGO_URI`
value from environment. It falls back to the local MongoDB URI when
no environment variable is present.
"""
import os
from dotenv import load_dotenv
from pymongo import MongoClient

# Load .env (if present) so MONGO_URI can be provided there
load_dotenv()

# Prefer MONGO_URI, fall back to MONGODB_URI, then to local
MONGO_URI = os.getenv('MONGO_URI') or os.getenv('MONGODB_URI') or 'mongodb://localhost:27017/smart_grocery'
print('Using MONGO_URI:', MONGO_URI)

client = MongoClient(MONGO_URI)

# derive db name if the URI includes one
db_name = None
if '/' in MONGO_URI and MONGO_URI.rsplit('/', 1)[-1]:
    db_name = MONGO_URI.rsplit('/', 1)[-1]
db = client.get_database(db_name) if db_name else client['smart_grocery']

print('DB name:', db.name)
for coll in ['products', 'stores', 'featured_deals', 'users']:
    exists = coll in db.list_collection_names()
    cnt = db[coll].count_documents({}) if exists else 0
    print(f'{coll}: exists={exists}, count={cnt}')
"""Quick DB check script that prints document counts for key collections.

This script will load a `.env` file if present and prefer the `MONGO_URI`
value from environment. It falls back to the local MongoDB URI when
no environment variable is present.
"""
import os
from dotenv import load_dotenv
from pymongo import MongoClient

# Load .env (if present) so MONGO_URI can be provided there
load_dotenv()

MONGO_URI = os.getenv('MONGO_URI') or os.getenv('MONGODB_URI') or 'mongodb://localhost:27017/smart_grocery'
print('Using MONGO_URI:', MONGO_URI)

client = MongoClient(MONGO_URI)
# derive db name if the URI includes one
db_name = None
if '/' in MONGO_URI and MONGO_URI.rsplit('/', 1)[-1]:
    db_name = MONGO_URI.rsplit('/', 1)[-1]
db = client.get_database(db_name) if db_name else client['smart_grocery']

print('DB name:', db.name)
for coll in ['products','stores','featured_deals','users']:
    exists = coll in db.list_collection_names()
    cnt = db[coll].count_documents({}) if exists else 0
    print(f'{coll}: exists={exists}, count={cnt}')
