from pymongo import MongoClient
from dotenv import load_dotenv
import os
import certifi

load_dotenv()
uri = os.getenv('MONGO_URI')
database_name = os.getenv('DATABASE_NAME', 'smart_grocery')

try:
    client = MongoClient(uri, tlsCAFile=certifi.where())
    db = client[database_name]
    products = list(db.products.find({}))
    print(f'Total products: {len(products)}')
    
    # Check for duplicates
    names = {}
    for p in products:
        name = p.get('name', 'Unknown')
        names[name] = names.get(name, 0) + 1
    
    print('\nProduct counts:')
    for name, count in sorted(names.items()):
        if count > 1:
            print(f'{name}: {count} DUPLICATE')
        else:
            print(f'{name}: {count}')
        
except Exception as e:
    print(f'Error: {e}')
