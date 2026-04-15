from app import app
from utils.db import mongo

with app.app_context():
    cats = mongo.db.products.distinct("category")
    print("CATEGORIES:", cats)
