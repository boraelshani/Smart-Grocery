import sys
import os
import json
from dotenv import load_dotenv

# Add project root to path
sys.path.append(os.getcwd())

from utils.db import get_db
load_dotenv()

db = get_db()
if db is not None:
    user = db.users.find_one({'email': 'user1@example.com'})
    print(f"USER RECORD: {json.dumps(user, default=str)}")
else:
    print("Could not connect to database.")

