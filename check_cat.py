import os
import sys
from app import app
from utils.db import get_db

with app.app_context():
    db = get_db()
    all_cats = list(db.categories.find({}, {"_id": 0}).sort([("name_en", 1)]))
    print("CATEGORIES:", all_cats)
