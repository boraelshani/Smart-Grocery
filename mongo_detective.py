from pymongo import MongoClient
from pymongo.errors import ConnectionFailure

def verify():
    print('Connecting to MongoDB at localhost:27017...')
    client = MongoClient('mongodb://localhost:27017/', serverSelectionTimeoutMS=5000)
    try:
        client.admin.command('ping')
        print('? MongoDB is running and reachable!\n')
    except ConnectionFailure:
        print('? MongoDB is NOT running or reachable at localhost:27017.')
        return

    print('--- DATABASE SCAN START ---')
    for db_name in client.list_database_names():
        print(f'\n?? Database: {db_name}')
        db = client[db_name]
        for col_name in db.list_collection_names():
            col = db[col_name]
            count = col.count_documents({})
            print(f'  +- ?? Collection: {col_name} | Document count: {count}')
            if count > 0 and db_name not in ['admin', 'local', 'config']:
                if col.find_one({'': [{'name': {'': 'milch|billa|hofer', '': 'i'}}, {'store': {'': 'milch|billa|hofer', '': 'i'}}]}):
                    print('      ? FOUND KEYWORD MATCH IN THIS COLLECTION!')
    print('\n--- DATABASE SCAN COMPLETE ---')

if __name__ == '__main__':
    verify()
