from utils.db import get_db

db = get_db()
if db is not None:
    coca_cola_zero = list(db.products.find({'name': {'$regex': 'Coca.*Zero', '$options': 'i'}}).limit(10))
    for p in coca_cola_zero:
        if "Zero" in p.get('name', ''):
            print('---')
            print('Name:', p.get('name'))
            print('Category:', p.get('category'))
            stores = p.get('stores', [])
            print(f'Stores count: {len(stores)}')
            for s in stores:
                print(f'  - {s.get("store", s.get("name"))}: {s.get("price")} ({s.get("unit_price", s.get("price_per_unit", ""))})')
