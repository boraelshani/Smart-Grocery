from app import app
from utils.db import get_db

with app.app_context():
    db = get_db()
    prods = list(db.products.find({}).limit(5))
    for p in prods:
        print(p)
