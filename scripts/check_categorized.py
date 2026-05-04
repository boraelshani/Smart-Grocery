import os
from utils.db import get_db

db = get_db()
if db is not None:
    sample = list(db.products.find({'is_placeholder': {'$ne': True}, 'category_path': {'$exists': True}}).limit(10))
    for p in sample:
        print(p.get('name'), "=>", p.get('category'), p.get('category_path'))
