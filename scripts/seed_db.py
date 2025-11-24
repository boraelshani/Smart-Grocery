"""Seed script to insert or upsert mock data into MongoDB.

Behavior:
- If `data/<collection>.json` exists (e.g. `data/stores.json`) it will be used as the source.
- Otherwise the script falls back to `models/models.py` variables.
- Documents are upserted using sensible unique keys so running multiple times won't wipe your Compass data.

Usage (PowerShell):
  . ./.venv/Scripts/Activate.ps1
  $env:MONGO_URI = 'mongodb://localhost:27017/smart_grocery'   # optional; defaults to local
  python ./scripts/seed_db.py
"""

import os
import sys
import json
from pymongo import MongoClient

# Ensure project root is on sys.path so `from models import models` works
proj_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if proj_root not in sys.path:
    sys.path.insert(0, proj_root)

try:
    from models import models as mock
except Exception as e:
    print('Error importing mock data from models.models:', e)
    mock = None

MONGO_URI = os.environ.get('MONGO_URI', os.environ.get('MONGODB_URI', 'mongodb://localhost:27017/smart_grocery'))
print('Using MONGO_URI:', MONGO_URI)

client = MongoClient(MONGO_URI)

# Determine DB: if URI provides a database name use it, otherwise default to 'smart_grocery'
db_name = None
if '/' in MONGO_URI and MONGO_URI.rsplit('/', 1)[-1]:
    db_name = MONGO_URI.rsplit('/', 1)[-1]

db = client.get_database(db_name) if db_name else client['smart_grocery']


def load_data_file(name):
    """Load data/<name>.json if it exists and return parsed JSON or None."""
    data_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data')
    path = os.path.join(data_dir, f'{name}.json')
    if os.path.exists(path):
        try:
            with open(path, 'r', encoding='utf-8') as fh:
                return json.load(fh)
        except Exception as e:
            print(f'Error loading {path}:', e)
    return None


def seed_collection(name, docs_source):
    """Upsert documents into collection `name` using docs_source which can be a list or dict."""
    coll = db[name]

    # Determine documents list
    if docs_source is None:
        print(f'No source for collection {name}; skipping')
        return
    if isinstance(docs_source, dict):
        docs_list = list(docs_source.values())
    else:
        docs_list = docs_source

    if not docs_list:
        print(f'No documents to insert for {name}.')
        return

    print(f'Upserting {len(docs_list)} documents into "{name}"...')
    changed = 0
    for doc in docs_list:
        # choose unique key per collection
        if name == 'users':
            key = {'email': doc.get('email')}
        elif name in ('stores', 'products'):
            key = {'name': doc.get('name')}
        elif name == 'featured_deals':
            key = {'title': doc.get('title')}
        else:
            key = {'_id': doc.get('_id')} if '_id' in doc else doc

        doc_to_set = {k: v for k, v in doc.items() if k != '_id'}
        res = coll.update_one(key, {'$set': doc_to_set}, upsert=True)
        if getattr(res, 'upserted_id', None) or getattr(res, 'modified_count', 0) > 0:
            changed += 1

    print(f'Upsert complete for "{name}" (changed or created: {changed}).')


def main():
    collections = ['stores', 'products', 'featured_deals', 'users']

    for name in collections:
        # Try JSON file first
        data = load_data_file(name)
        if data is not None:
            seed_collection(name, data)
            continue

        # Fallback to models mock data
        if mock is not None and hasattr(mock, name):
            seed_collection(name, getattr(mock, name))
        else:
            print(f'No data found for {name} (no data/{name}.json and no mock.{name})')

    print('Seeding finished.')


if __name__ == '__main__':
    main()
