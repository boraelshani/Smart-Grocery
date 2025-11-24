"""Seed script to insert mock data from `models/models.py` into MongoDB.

Usage (PowerShell):
  . ./.venv/Scripts/Activate.ps1
  $env:MONGO_URI = 'mongodb://localhost:27017/smart_grocery'   # optional; defaults to local
  python ./scripts/seed_db.py

The script will create collections: products, stores, featured_deals, users
"""
import os
import sys
from pymongo import MongoClient

# Ensure project root is on sys.path so `from models import models` works
proj_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if proj_root not in sys.path:
    sys.path.insert(0, proj_root)

try:
    from models import models as mock
except Exception as e:
    print('Error importing mock data from models.models:', e)
    raise

MONGO_URI = os.environ.get('MONGO_URI', 'mongodb://localhost:27017/smart_grocery')
print('Using MONGO_URI:', MONGO_URI)

client = MongoClient(MONGO_URI)

# Determine DB: use DB in URI if present, otherwise default to 'smart_grocery'
db_name = None
if '/' in MONGO_URI and MONGO_URI.rsplit('/', 1)[-1]:
    db_name = MONGO_URI.rsplit('/', 1)[-1]

db = client.get_database(db_name) if db_name else client['smart_grocery']

def seed_collection(name, docs):
    coll = db[name]
    print(f'Clearing collection "{name}"...')
    coll.delete_many({})
    if isinstance(docs, dict):
        docs_list = list(docs.values())
    else:
        docs_list = docs
    if not docs_list:
        print(f'No documents to insert for {name}.')
        return
    print(f'Inserting {len(docs_list)} documents into "{name}"...')
    res = coll.insert_many(docs_list)
    print('Inserted ids sample:', res.inserted_ids[:3])

def main():
    seed_collection('stores', mock.stores)
    seed_collection('products', mock.products)
    seed_collection('featured_deals', mock.featured_deals)
    seed_collection('users', mock.users)
    print('Seeding finished.')

if __name__ == '__main__':
    main()
