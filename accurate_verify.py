import pymongo
uri = "mongodb+srv://drenbuqa:boradren@cluster0.vmrpj9o.mongodb.net/smart_grocery?appName=Cluster0"
client = pymongo.MongoClient(uri)
db = client['smart_grocery']
print(f"Checking collection matched_products...")
cursor = db.matched_products.find()
match_count = 0
for doc in cursor:
    billa = next((s for s in doc['stores'] if s['store'] == 'BILLA'), None)
    if billa and "Estimated" not in billa['original_branded_name']:
        match_count += 1
        print(f"YES: {doc['name']} matched with Billa: {billa['original_branded_name']}")
print(f"Total real Billa matches: {match_count}")
