from pymongo import MongoClient

db = MongoClient()['smart_grocery']
c = 0
c_str = 0
c_fl = 0
c_int = 0
c_none = 0

for p in db.products.find():
    if 'stores' in p:
        for s in p['stores']:
            if isinstance(s.get('price'), str): 
                c_str += 1
            elif isinstance(s.get('price'), float): 
                c_fl += 1
            elif isinstance(s.get('price'), int): 
                c_int += 1
            else: 
                c_none += 1
        c += 1

print('Total products with stores:', c, 'str:', c_str, 'float:', c_fl, 'int:', c_int, 'none:', c_none)
