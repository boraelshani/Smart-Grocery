from app import app
from utils.db import mongo
with app.app_context():
    for q in ['hoffer', 'Hoffer', 'hofer', 'Hofer']:
        mongo.db.products.update_many({'store': q}, {'$set': {'store': 'HOFER'}})
        mongo.db.products.update_many({'cheapest.store': q}, {'$set': {'cheapest.store': 'HOFER'}})
        mongo.db.products.update_many({'stores.store': q}, {'$set': {'stores.$[elem].store': 'HOFER'}}, array_filters=[{'elem.store': q}])
print('Success')
