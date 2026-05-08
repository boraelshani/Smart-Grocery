from app import app
from utils.db import get_db

with app.app_context():
    db = get_db()
    cats = list(db.categories.find({}))
    print([c.get('name_en') for c in cats if c.get('name_en') and 'meat' in c.get('name_en').lower()])
