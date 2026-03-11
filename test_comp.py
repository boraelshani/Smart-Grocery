import re
from app import app
from routes.main_routes import compare_prices
from models.products_model import products_model
with app.app_context():
    search_query = 'milk'
    search_regex = {'$regex': re.escape(search_query), '$options': 'i'}
    qd = {'$or': [
                    {'name': search_regex},
                    {'title': search_regex},
                    {'category': search_regex},
                    {'stores.store': search_regex},
                    {'stores.name': search_regex}
                ]}
    prods = products_model.list_products(query=qd, skip=0, limit=30)
    print("Found len:", len(prods))
    for p in prods:
         print(p.get('name'))
