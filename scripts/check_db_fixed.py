#!/usr/bin/env python3
"""Minimal DB check script (fixed) that prints document counts for key collections.
Loads .env and prefers MONGO_URI from it (falls back to local).
"""
from dotenv import load_dotenv
import os
from pymongo import MongoClient

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
for coll in ['products', 'stores', 'featured_deals', 'users']:
    exists = coll in db.list_collection_names()
    cnt = db[coll].count_documents({}) if exists else 0
    print(f'{coll}: exists={exists}, count={cnt}')
