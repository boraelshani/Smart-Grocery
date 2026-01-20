
import os
from pymongo import MongoClient
from bson import ObjectId
from dotenv import load_dotenv
import sys

# Add project root to path
sys.path.append(os.getcwd())

load_dotenv()

mongo_uri = os.getenv('MONGO_URI')
client = MongoClient(mongo_uri)
db = client.get_database()

print("--- Multibuy Offers ---")
offers = list(db.multibuy_offers.find().limit(5))
for o in offers:
    print(o)

print("\n--- Sample Shopping List Item (from a user) ---")
user = db.users.find_one({"shopping_lists": {"$exists": True, "$not": {"$size": 0}}})
if user:
    for lst in user.get('shopping_lists', []):
        if lst.get('items'):
            print(f"List: {lst.get('name')}")
            for item in lst.get('items')[:3]:
                print(item)
            break
else:
    print("No user with shopping lists found.")
