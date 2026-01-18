from app import app, mongo
import json

with app.app_context():
    user = mongo.db.users.find_one({'email': 'user1@example.com'})
    print(f"USER RECORD: {json.dumps(user, default=str)}")
