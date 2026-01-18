from app import app, mongo
from flask import session
import json

with app.app_context():
    user_email = 'user1@example.com'
    update_data = {
        'name': 'Test User',
        'phone': '12345',
        'address': 'Test Street',
        'profile_image': 'https://api.dicebear.com/7.x/avataaars/svg?seed=Felix'
    }
    
    # Simulate the update_one call from main_routes.py
    res = mongo.db.users.update_one({'email': user_email}, {'$set': update_data})
    print(f"UPDATE RESULT: matched={res.matched_count}, modified={res.modified_count}")
    
    # Verify
    user = mongo.db.users.find_one({'email': user_email})
    print(f"VERIFY RECORD: {json.dumps(user, default=str)}")
