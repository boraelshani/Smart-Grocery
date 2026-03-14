import os
import certifi
import pymongo
uri = "mongodb+srv://drenbuqa:boradren@cluster0.vmrpj9o.mongodb.net/smart_grocery?appName=Cluster0"
client = pymongo.MongoClient(uri, tlsCAFile=certifi.where())
db = client['smart_grocery']

cursor = db.matched_products.find()
for doc in cursor:
    billa = next((s for s in doc['stores'] if s['store'] == 'BILLA'), None)
    if billa:
        state = "MATCH" if "Estimated" not in billa['original_branded_name'] else "MISSED"
        reason = billa.get('match_reason', 'N/A')
        print(f"{state} | {doc['name']} | Reason: {reason}")
