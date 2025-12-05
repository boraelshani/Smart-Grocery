"""
Normalize price fields in `products` collection.
- Converts common string price formats like "$1.99" or "1,299.50" to float numbers.
- Normalizes `stores[*].price`, `price`, and `cheapest.price`.
- Recomputes `cheapest` based on `stores` when possible.

Usage:
  set the `MONGO_URI` env var or create a `.env` with MONGO_URI, then run:
    python .\scripts\normalize_prices.py

This script is idempotent and prints a summary.
"""
import os
from dotenv import load_dotenv
from pymongo import MongoClient
import re

load_dotenv()
MONGO_URI = os.environ.get('MONGO_URI')
if not MONGO_URI:
    print('MONGO_URI not set in environment. Set it and re-run.')
    exit(1)

client = MongoClient(MONGO_URI)
db = client.get_default_database()

price_re = re.compile(r"[0-9]+(?:[\.,][0-9]{1,2})?")

def parse_price(val):
    if val is None:
        return None
    if isinstance(val, (int, float)):
        return float(val)
    try:
        s = str(val)
        m = price_re.search(s)
        if not m:
            return None
        clean = m.group(0).replace(',', '')
        return float(clean)
    except Exception:
        return None


def normalize_product(p):
    changed = False
    updates = {}
    stores = p.get('stores') or []
    new_stores = []
    min_price = None
    min_store = None
    for s in stores:
        s_copy = dict(s)
        price_raw = s_copy.get('price')
        parsed = parse_price(price_raw)
        if parsed is not None:
            # store numeric value
            if s_copy.get('price') != parsed:
                s_copy['price'] = parsed
                changed = True
        new_stores.append(s_copy)
        if parsed is not None and (min_price is None or parsed < min_price):
            min_price = parsed
            min_store = s_copy.get('store') or s_copy.get('name')

    # update stores array if any change
    if changed:
        updates['stores'] = new_stores

    # normalize top-level price
    top_price = parse_price(p.get('price'))
    if top_price is not None and p.get('price') != top_price:
        updates['price'] = top_price
        changed = True

    # normalize cheapest.price
    cheapest = p.get('cheapest') or {}
    cheapest_price = parse_price(cheapest.get('price')) if isinstance(cheapest, dict) else None
    # prefer recomputed min_price from stores
    if min_price is not None:
        if not isinstance(cheapest, dict) or cheapest.get('price') != min_price or cheapest.get('store') != min_store:
            updates['cheapest'] = {'price': min_price, 'store': min_store}
            changed = True
    else:
        if cheapest_price is not None and (not isinstance(cheapest, dict) or cheapest.get('price') != cheapest_price):
            updates['cheapest'] = {'price': cheapest_price, 'store': cheapest.get('store') if isinstance(cheapest, dict) else None}
            changed = True

    return changed, updates


def main():
    products = db.products.find({})
    total = 0
    changed_count = 0
    for p in products:
        total += 1
        changed, updates = normalize_product(p)
        if changed:
            changed_count += 1
            try:
                db.products.update_one({'_id': p['_id']}, {'$set': updates})
                print(f"Updated product {_short(p)} with: {list(updates.keys())}")
            except Exception as e:
                print('Error updating product', p.get('name'), e)
    print(f"Processed {total} products; updated {changed_count} products.")


def _short(p):
    return f"{p.get('_id')} ({p.get('name')})"


if __name__ == '__main__':
    main()
