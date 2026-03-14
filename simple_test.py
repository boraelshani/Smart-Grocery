import os
import pymongo
client = pymongo.MongoClient("mongodb://localhost:27017")
db = client['smart_grocery']
print("Collections:", db.list_collection_names())
count = db.matched_products.count_documents({})
print("Count:", count)
for doc in db.matched_products.find({"stores.store": "BILLA"}):
    billa = [s for s in doc['stores'] if s['store'] == 'BILLA'][0]
    if "Estimated" not in billa['original_branded_name']:
        print("REAL MATCH:", doc['name'])
