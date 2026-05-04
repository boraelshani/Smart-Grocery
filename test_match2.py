import json
from bson.json_util import dumps
from utils.db import get_db

db = get_db()
if db is not None:
    coca_cola_zeros = list(db.products.find({'name': 'Coca Cola Zero'}))
    print(len(coca_cola_zeros))
    if coca_cola_zeros:
        print(dumps(coca_cola_zeros[0], indent=2))
