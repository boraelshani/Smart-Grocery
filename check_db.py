from app import app
from utils.db import get_db

with app.app_context():
    db = get_db()
    if db is not None:
        print("Community Price Reports:")
        for r in db.community_price_reports.find():
            print(r)
        print("Feedback:")
        for r in db.feedback.find():
            print(r)
