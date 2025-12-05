"""Backfill product images into users' shopping_list entries.

This script will:
 - connect to MongoDB using MONGO_URI from .env or env
 - iterate users in `users` collection
 - for each user, iterate their `shopping_list` array; for items that are objects and missing `image`:
     - try to find a product document by `id` (ObjectId string or string id) or by name
     - if product found and has `image` or `images`, set `item['image']` to the image URL
 - update user document with modified shopping_list

Run:
  .venv\Scripts\Activate.ps1
  pip install pymongo python-dotenv
  python scripts\backfill_shopping_list_images.py

Use with care — it updates user documents in-place. Make a backup or run on a copy first if needed.
"""

from dotenv import load_dotenv
import os
from pymongo import MongoClient
from bson import ObjectId
import re

load_dotenv()

MONGO_URI = os.getenv('MONGO_URI')
if not MONGO_URI:
    print('MONGO_URI not set in environment or .env')
    raise SystemExit(1)

print('Connecting to MongoDB...')
client = MongoClient(MONGO_URI)
db = client.get_default_database()
if not db:
    # fallback to smart_grocery
    db = client['smart_grocery']

users_coll = db.users
products_coll = db.products

def find_product_for_item(item):
    """Try to locate a product doc for the given shopping-list item.
    item may be a dict with id, name, title, etc., or a string.
    Returns product doc or None.
    """
    if not item:
        return None
    # if item is string, treat as name
    if isinstance(item, str):
        name = item
        # try exact name case-insensitive
        prod = products_coll.find_one({'name': {'$regex': '^' + re.escape(name) + '$', '$options': 'i'}})
        if prod:
            return prod
        # substring match
        return products_coll.find_one({'name': {'$regex': re.escape(name), '$options': 'i'}})

    if isinstance(item, dict):
        # try id first
        pid = item.get('id') or item.get('product_id')
        if pid:
            # try ObjectId
            try:
                prod = products_coll.find_one({'_id': ObjectId(str(pid))})
                if prod:
                    return prod
            except Exception:
                pass
            # fallback: try string id field
            prod = products_coll.find_one({'id': str(pid)})
            if prod:
                return prod
        # try name/title
        name = item.get('name') or item.get('title')
        if name:
            prod = products_coll.find_one({'name': {'$regex': '^' + re.escape(name) + '$', '$options': 'i'}})
            if prod:
                return prod
            prod = products_coll.find_one({'name': {'$regex': re.escape(name), '$options': 'i'}})
            if prod:
                return prod
    return None

updated_count = 0
checked_users = 0

for u in users_coll.find({}):
    checked_users += 1
    sl = u.get('shopping_list') or []
    changed = False
    new_sl = []
    for it in sl:
        # leave strings unchanged
        if not isinstance(it, dict):
            new_sl.append(it)
            continue
        # if image already present, keep
        if it.get('image'):
            new_sl.append(it)
            continue
        prod = find_product_for_item(it)
        if prod:
            img = prod.get('image') or (prod.get('images') and prod.get('images')[0])
            if img:
                it['image'] = img
                changed = True
        new_sl.append(it)
    if changed:
        users_coll.update_one({'_id': u['_id']}, {'$set': {'shopping_list': new_sl}})
        updated_count += 1
        print(f"Updated shopping_list for user {u.get('email') or u.get('_id')}")

print(f"Checked {checked_users} users, updated {updated_count} users.")
client.close()
