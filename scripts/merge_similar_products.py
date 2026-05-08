import re
from collections import defaultdict
from pymongo import MongoClient
import os
from datetime import datetime, timezone

def get_db():
    uri = os.environ.get("MONGO_URI", "mongodb://localhost:27017/")
    client = MongoClient(uri)
    return client.get_database("smart_grocery")

def normalize_title(title):
    t = str(title).lower()
    # Replace special chars with space
    t = re.sub(r'[^a-z0-9öäüß]', ' ', t)
    # Collapse spaces
    t = re.sub(r'\s+', ' ', t).strip()
    return t

def extract_volume(title):
    # Look for patterns like 1.5l, 1,5 l, 500ml, 500 ml, 100g, 1 kg
    match = re.search(r'(\d+(?:[.,]\d+)?)\s*(ml|l|g|kg|cl|dl)', title.lower().replace(' ', ''))
    if match:
        val = match.group(1).replace(',', '.')
        unit = match.group(2)
        if unit == 'kg':
            return float(val) * 1000, 'g'
        if unit == 'l':
            return float(val) * 1000, 'ml'
        if unit == 'dl':
            return float(val) * 100, 'ml'
        if unit == 'cl':
            return float(val) * 10, 'ml'
        return float(val), unit
    return None, None

def strip_volume(title):
    # Remove volume strings from title
    t = re.sub(r'\d+(?:[.,]\d+)?\s*(ml|l|g|kg|cl|dl)\b', '', title.lower())
    t = re.sub(r'\s+', ' ', t).strip()
    return t

def get_base_key(title):
    norm = normalize_title(title)
    vol_val, vol_unit = extract_volume(norm)
    base_name = strip_volume(norm)
    # Give a canonical generic name combining both so we only match identical volumes
    return f"{base_name}::{vol_val}{vol_unit}"

def merge_products():
    db = get_db()
    print("Fetching all products for deduplication...")
    
    # We mainly target the old-style products which are used by UI route
    products = list(db.products.find({'is_placeholder': {'$ne': True}}))
    print(f"Found {len(products)} active products.")
    
    groups = defaultdict(list)
    for p in products:
        name = p.get('name') or p.get('title') or ''
        key = get_base_key(name)
        groups[key].append(p)

    merged_groups_count = 0
    products_removed = 0
    
    for key, items in groups.items():
        if len(items) <= 1:
            continue
            
        merged_groups_count += 1
        
        # Pick the master product (the one with the most stores, or shortest name)
        items.sort(key=lambda x: (-len(x.get('stores', [])), len(x.get('name', ''))))
        master = items[0]
        
        # Merge others into master
        master_id = master['_id']
        master_stores = { (s.get('store', '').lower(), s['url']): s for s in master.get('stores', []) }
        
        ids_to_remove = []
        
        for p in items[1:]:
            ids_to_remove.append(p['_id'])
            for s in p.get('stores', []):
                store_key = (s.get('store', '').lower(), s['url'])
                if store_key not in master_stores:
                    master_stores[store_key] = s
        
        new_stores_list = list(master_stores.values())
        
        # Calculate cheapest
        cheapest_store = None
        for s in new_stores_list:
            price = s.get('price')
            if price is not None:
                if cheapest_store is None or price < cheapest_store.get('price', float('inf')):
                    cheapest_store = s
                    
        update_doc = {
            'stores': new_stores_list,
            'updated_at': datetime.now(timezone.utc)
        }
        
        if cheapest_store:
            update_doc['cheapest'] = {
                'store': cheapest_store.get('store'),
                'price': cheapest_store.get('price'),
                'url': cheapest_store.get('url')
            }
            update_doc['price'] = cheapest_store.get('price')
            
        # Update master
        db.products.update_one({'_id': master_id}, {'$set': update_doc})
        
        # Remove duplicates
        if ids_to_remove:
            db.products.delete_many({'_id': {'$in': ids_to_remove}})
            products_removed += len(ids_to_remove)

    print(f"Merged {merged_groups_count} groups.")
    print(f"Removed {products_removed} duplicate products.")

if __name__ == "__main__":
    merge_products()
