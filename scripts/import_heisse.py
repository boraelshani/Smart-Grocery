import sys
import os
import requests
from pymongo import MongoClient

def main():
    print("Fetching data from heisse-preise...")
    r = requests.get('https://heisse-preise.io/data/latest-canonical.json')
    data = r.json()
    
    # 1. Group by Name
    # Keep only the cheapest per store for that name
    grouped = {}
    for item in data:
        name = item.get('name', '').strip()
        store = item.get('store', '').lower()
        price = item.get('price', 0)
        
        if not name or not store: continue
        
        if name not in grouped:
            grouped[name] = {}
        
        if store not in grouped[name] or price < grouped[name][store]['price']:
            grouped[name][store] = item

    print(f"Grouped into {len(grouped)} distinct items.")
    
    client = MongoClient('mongodb://localhost:27017/')
    db = client['smart_grocery']
    
    print("Formatting and inserting into MongoDB...")
    docs_to_insert = []
    
    import itertools
    # Process all to fully answer the request
    for name, store_items in grouped.items():
        stores_list = []
        for store, item_data in store_items.items():
            stores_list.append({
                'store': store.capitalize(),
                'price': float(item_data['price']),
                'url': item_data.get('url', '')
            })
            
        # The template requires the cheapest element and full stores array
        stores_list.sort(key=lambda x: x['price'])
        cheapest_obj = stores_list[0]
        
        docs_to_insert.append({
            'name': name,
            'price': cheapest_obj['price'],
            'cheapest': cheapest_obj,
            'stores': stores_list,
            'image': '',
            'is_placeholder': False,
            'category': 'HeissePrices',
            'normalized_unit_price': None,
            'normalized_unit_label': ''
        })

    # Clear old inserts
    db.products.delete_many({'category': 'HeissePrices'}) 
    # Batch insert to avoid BSON document size limits
    batch_size = 5000
    for i in range(0, len(docs_to_insert), batch_size):
        db.products.insert_many(docs_to_insert[i:i+batch_size])
    print(f"Inserted {len(docs_to_insert)} items into products collection. DONE.")

if __name__ == '__main__':
    main()
