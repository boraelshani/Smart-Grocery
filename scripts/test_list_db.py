from pymongo import MongoClient
import os

uri = os.environ.get('MONGO_URI')
if not uri:
    raise SystemExit('Set MONGO_URI in the env first')

client = MongoClient(uri, serverSelectionTimeoutMS=5000)
print('Connected to server:', client.address)
print('Databases:')
for name in client.list_database_names():
    print(' -', name)

db_name = 'smart_grocery'
if db_name in client.list_database_names():
    db = client[db_name]
    print('\nCollections in', db_name, ':', db.list_collection_names())
else:
    print(f'\nDatabase \"{db_name}\" not found on this server.')
