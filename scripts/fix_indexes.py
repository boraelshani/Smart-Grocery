import os
from utils.db import get_db

db = get_db()
if db is not None:
    for index in db.categories.list_indexes():
        if 'slug' in index['name']:
            db.categories.drop_index(index['name'])
            print(f"Dropped {index['name']}")
    print("Done checking indexes.")
