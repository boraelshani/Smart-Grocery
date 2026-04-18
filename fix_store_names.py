from app import app
from utils.db import mongo
with app.app_context():
    mongo.db.products.update_many({'store': 'billa'}, {'$set': {'store': 'BILLA'}})
    mongo.db.products.update_many({'cheapest.store': 'billa'}, {'$set': {'cheapest.store': 'BILLA'}})
    mongo.db.products.update_many({'stores.store': 'billa'}, {'$set': {'stores.$[elem].store': 'BILLA'}}, array_filters=[{'elem.store': 'billa'}])
print('Success')
