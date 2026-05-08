import os
import json
from bson import json_util
from utils.db import get_db

db = get_db()
if db is not None:
    cats = list(db.categories.find({}))
    print('Total categories:', len(cats))
    
    products_with_cat_id = db.products.count_documents({'categoryId': {'$exists': True}})
    products_without_cat_id = db.products.count_documents({'$or': [{'categoryId': {'$exists': False}}, {'categoryId': None}]})
    print(f'Products with categoryId: {products_with_cat_id}')
    print(f'Products without categoryId: {products_without_cat_id}')
    
    if len(cats) > 0:
        print('\nSample categories:')
        for c in cats[:5]:
            print(f"- {c.get('categoryId')}: {c.get('name_en')} / {c.get('name_de')}")
