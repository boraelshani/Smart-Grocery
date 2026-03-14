import pymongo
uri = "mongodb+srv://drenbuqa:boradren@cluster0.vmrpj9o.mongodb.net/smart_grocery?appName=Cluster0"
client = pymongo.MongoClient(uri)
db = client['smart_grocery']
print(db.list_collection_names())
