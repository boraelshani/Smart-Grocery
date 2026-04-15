from app import app
from utils.db import mongo

with app.app_context():
    docs = list(mongo.db.products.find({"name": {"$regex": "paprika", "$options": "i"}}))
    print(f"Found {len(docs)} items containing 'paprika'")
    for d in docs:
        print(f" - {d.get('name')} (Cat: {d.get('category')} | Price: {d.get('price')})")
