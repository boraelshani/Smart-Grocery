from pymongo import MongoClient
db=MongoClient()['smart_grocery']

found = False
for p in db.products.find({"stores": {"$type": "array"}}):
    if p.get('stores'):
        for x in p['stores']:
            if isinstance(x, dict) and isinstance(x.get('price'), str):
                print('FOUND STR:', x)
                found = True
        
if not found:
    print('NO STR PRICES FOUND.')
