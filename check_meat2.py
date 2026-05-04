from app import app
from utils.db import get_db
import re

with app.app_context():
    db = get_db()
    cat_filter = "meat"
    q = {'category_path': {'$regex': f"^{re.escape(cat_filter)}$", '$options': 'i'}}
    print('Products matching meat in category_path:', db.products.count_documents(q))
    
    q2 = {'category': {'$regex': f"^{re.escape(cat_filter)}$", '$options': 'i'}}
    print('Products matching meat in category:', db.products.count_documents(q2))
