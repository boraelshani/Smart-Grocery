from app import app
from utils.db import get_db

with app.app_context():
    db = get_db()
    prods = list(db.products.find({'categoryId': {'$exists': True}}).limit(2))
    for p in prods:
        print("Product:", p.get('name'))
        print("Product categoryId:", p.get('categoryId'))
        cat = db.categories.find_one({'_id': p.get('categoryId')})
        if not cat:
            import bson
            try:
                cat = db.categories.find_one({'_id': bson.ObjectId(p.get('categoryId'))})
            except:
                pass
        print("Found Category:", cat.get('name_en') if cat else None)
        print("---")
