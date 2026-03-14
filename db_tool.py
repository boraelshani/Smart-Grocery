import os
import certifi
import pymongo
uri = "mongodb+srv://drenbuqa:boradren@cluster0.vmrpj9o.mongodb.net/smart_grocery?appName=Cluster0"
client = pymongo.MongoClient(uri, tlsCAFile=certifi.where())
db = client['smart_grocery']
print("Collections:", db.list_collection_names(), flush=True)
count = db.matched_products.count_documents({})
print("Docs in matched_products:", count, flush=True)

cursor = db.matched_products.find()
matches = 0
for doc in cursor:
    billa = next((s for s in doc['stores'] if s['store'] == 'BILLA'), None)
    if billa and "Estimated" not in billa['original_branded_name']:
        matches += 1
        print("BILLA MATCH FOUND:", doc['name'], flush=True)
print("Total matches:", matches, flush=True)
