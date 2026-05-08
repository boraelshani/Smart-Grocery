from utils.db import get_db

db = get_db()
if db is not None:
    one_store_prods = list(db.products.find({'stores': {'$size': 1}}).limit(30))
    print(f'Found one-store products: {len(one_store_prods)}')
    for p in one_store_prods:
        print('Name:', p.get('name', ''), '| Store:', p.get('stores')[0].get('store', p.get('stores')[0].get('name')))
