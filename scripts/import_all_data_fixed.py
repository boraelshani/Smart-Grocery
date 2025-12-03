#!/usr/bin/env python3
"""One-time importer (fixed) that loads JSON files from `data/` and upserts into MongoDB.
This version uses python-dotenv and prefers MONGO_URI from .env with a local fallback.
"""
import os
import sys
import json
from dotenv import load_dotenv
from pymongo import MongoClient, errors
from werkzeug.security import generate_password_hash

# Load .env if present
load_dotenv()

MONGO_URI = os.getenv('MONGO_URI') or os.getenv('MONGODB_URI') or 'mongodb://localhost:27017/smart_grocery'
print('Using MONGO_URI:', MONGO_URI)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(ROOT, 'data')


def detect_db_name_from_uri(uri):
    if '/' in uri and uri.rsplit('/', 1)[-1]:
        return uri.rsplit('/', 1)[-1]
    return None


def load_json_file(path):
    with open(path, 'r', encoding='utf-8') as fh:
        return json.load(fh)


def choose_key_for_collection(name, doc):
    if name == 'users' and doc.get('email'):
        return {'email': doc.get('email')}
    if name in ('stores', 'products') and doc.get('name'):
        return {'name': doc.get('name')}
    if name in ('featured_deals', 'deals') and doc.get('title'):
        return {'title': doc.get('title')}
    if '_id' in doc:
        return {'_id': doc.get('_id')}
    return None


def upsert_collection(db, name, docs):
    coll = db[name]
    if not isinstance(docs, list):
        if isinstance(docs, dict):
            docs = list(docs.values())
        else:
            print(f'Skipping {name}: unexpected JSON structure')
            return

    print(f'Processing {len(docs)} documents for collection "{name}"')
    changed = 0
    for doc in docs:
        if not isinstance(doc, dict):
            continue
        if name == 'users' and doc.get('password'):
            try:
                doc['password'] = generate_password_hash(doc['password'])
            except Exception:
                pass

        key = choose_key_for_collection(name, doc)
        doc_to_set = {k: v for k, v in doc.items() if k != '_id'}
        try:
            if key is not None:
                res = coll.update_one(key, {'$set': doc_to_set}, upsert=True)
                if getattr(res, 'upserted_id', None) or getattr(res, 'modified_count', 0) > 0:
                    changed += 1
            else:
                try:
                    coll.insert_one(doc_to_set)
                    changed += 1
                except errors.DuplicateKeyError:
                    pass
        except Exception as e:
            print(f'Error inserting/updating doc in {name}:', e)
    print(f'Finished collection "{name}" (changed/inserted: {changed})')


def main():
    if not os.path.isdir(DATA_DIR):
        print('Data directory not found:', DATA_DIR)
        sys.exit(1)

    print('Connecting to MongoDB:', MONGO_URI)
    client = MongoClient(MONGO_URI)
    db_name = detect_db_name_from_uri(MONGO_URI)
    db = client.get_database(db_name) if db_name else client['smart_grocery']

    files = [f for f in os.listdir(DATA_DIR) if f.lower().endswith('.json')]
    if not files:
        print('No JSON files found in data directory')
        return

    for fname in files:
        col_name = os.path.splitext(fname)[0]
        path = os.path.join(DATA_DIR, fname)
        try:
            data = load_json_file(path)
        except Exception as e:
            print(f'Failed to load {path}:', e)
            continue

        upsert_collection(db, col_name, data)

    print('Import complete.')


if __name__ == '__main__':
    main()
