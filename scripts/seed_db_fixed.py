#!/usr/bin/env python3
"""Seed script (fixed) to insert or upsert mock data into MongoDB.
This version loads .env and uses MONGO_URI from it with local fallback.
"""
import os
import sys
import json
from dotenv import load_dotenv
from pymongo import MongoClient
from werkzeug.security import generate_password_hash

# Load .env
load_dotenv()

MONGO_URI = os.getenv('MONGO_URI') or os.getenv('MONGODB_URI') or 'mongodb://localhost:27017/smart_grocery'
print('Using MONGO_URI:', MONGO_URI)

# Ensure project root is on sys.path so `from models import models` works
proj_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if proj_root not in sys.path:
    sys.path.insert(0, proj_root)

try:
    from models import models as mock
except Exception as e:
    print('Error importing mock data from models.models:', e)
    mock = None

client = MongoClient(MONGO_URI)
# Determine DB: if URI provides a database name use it, otherwise default to 'smart_grocery'
db_name = None
if '/' in MONGO_URI and MONGO_URI.rsplit('/', 1)[-1]:
    db_name = MONGO_URI.rsplit('/', 1)[-1]

db = client.get_database(db_name) if db_name else client['smart_grocery']


def load_data_file(name):
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
        if name == 'users':
            key = {'email': doc.get('email')}
        elif name in ('stores', 'products'):
            key = {'name': doc.get('name')}
        elif name == 'featured_deals':
            key = {'title': doc.get('title')}
        else:
            key = {'_id': doc.get('_id')} if '_id' in doc else doc

        doc_to_set = {k: v for k, v in doc.items() if k != '_id'}
        if name == 'users' and doc_to_set.get('password'):
            try:
                doc_to_set['password'] = generate_password_hash(doc_to_set['password'])
            except Exception:
                pass
        res = coll.update_one(key, {'$set': doc_to_set}, upsert=True)
        if getattr(res, 'upserted_id', None) or getattr(res, 'modified_count', 0) > 0:
            changed += 1

    print(f'Upsert complete for "{name}" (changed or created: {changed}).')


def main():
    collections = ['stores', 'products', 'featured_deals', 'users']

    for name in collections:
        data = load_data_file(name)
        if data is not None:
            seed_collection(name, data)
            continue
        if mock is not None and hasattr(mock, name):
            seed_collection(name, getattr(mock, name))
        else:
            print(f'No data found for {name} (no data/{name}.json and no mock.{name})')

    print('Seeding finished.')


if __name__ == '__main__':
    main()
