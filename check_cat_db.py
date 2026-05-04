from app import app
from utils.db import get_db

with app.app_context():
    db = get_db()
    print('Products with category_path:', db.products.count_documents({'category_path': {'$exists': True}}))
    print('Total products:', db.products.count_documents({}))
    
    sample = db.products.find_one({'category_path': {'$exists': True}})
    if sample:
        print('Sample category_path:', sample.get('category_path'))
        print('Sample category:', sample.get('category'))
        
    cats = list(db.categories.find({}))
    print('Total categories:', len(cats))
