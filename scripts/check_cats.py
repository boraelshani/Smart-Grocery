import os
from utils.db import get_db

db = get_db()
if db is not None:
    count = db.products.count_documents({
        'is_placeholder': {'$ne': True}, 
        '$or': [
            {'category': 'HeissePrices'}, 
            {'categoryId': 'cat_heisseprices'}, 
            {'category': None}, 
            {'category': ''},
            {'category': {'$exists': False}}
        ]
    })
    print(f'Uncategorized products (no category or category=HeissePrices): {count}')
