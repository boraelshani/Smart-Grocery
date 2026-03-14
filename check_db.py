from utils.db import get_db
import os
os.environ['DATABASE_NAME'] = 'smart_grocery'
db = get_db()
count = db.matched_products.count_documents({})
print(f"Total products in matched_products: {count}")
if count > 0:
    sample = db.matched_products.find_one({"stores.store": "BILLA", "stores.match_reason": {"$ne": "No match found >= 70 score"}})
    if sample:
        print(f"Found a real Billa match: {sample['name']}")
    else:
        print("No real Billa matches found yet in the current collection state.")
