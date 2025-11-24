"""Quick DB check script that prints document counts for key collections."""
import os
from pymongo import MongoClient

uri = os.environ.get('MONGO_URI', 'mongodb://localhost:27017/smart_grocery')
print('Using URI:', uri)
client = MongoClient(uri)
db_name = None
if '/' in uri and uri.rsplit('/',1)[-1]:
    db_name = uri.rsplit('/',1)[-1]
db = client.get_database(db_name) if db_name else client['smart_grocery']

print('DB name:', db.name)
for coll in ['products','stores','featured_deals','users']:
    exists = coll in db.list_collection_names()
    cnt = db[coll].count_documents({}) if exists else 0
    print(f'{coll}: exists={exists}, count={cnt}')
