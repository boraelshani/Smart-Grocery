from app import app
from utils.db import get_db
with app.app_context():
    db = get_db()
    o = db.store_products.find_one({'storeProductId': 'sp_prod_organic-greek-style-yogurt-10-fat_c70aa9_store_lidl'})
    print(o)
