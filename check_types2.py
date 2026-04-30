from pymongo import MongoClient

db = MongoClient()['smart_grocery']

for p in db.products.find():
    if p.get('stores'):
        s = p.get('stores')
        if not isinstance(s, list):
            print('Found weird stores type:', type(s), p['_id'])
            continue
        for x in s:
            if not isinstance(x, dict):
                print('Found weird store item type:', type(x), p['_id'])
                continue
            if 'price' not in x:
                print('Found store without price:', x, p['_id'])
            elif isinstance(x['price'], str):
                print('Found store with STR price:', x['price'], p['_id'])
            elif isinstance(x['price'], float) or isinstance(x['price'], int):
                pass
            else:
                 print('Found store with weird price type:', type(x['price']), x['price'], p['_id'])
