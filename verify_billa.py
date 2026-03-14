from app import app
from utils.db import mongo
with app.app_context():
    cursor = mongo.db.matched_products.find({"stores.store": "BILLA"})
    count = 0
    matches = 0
    for doc in cursor:
        count += 1
        billa_store = next(s for s in doc['stores'] if s['store'] == 'BILLA')
        if "Estimated" not in billa_store['original_branded_name']:
            matches += 1
            print(f"MATCH: {doc['name']} -> Billa: {billa_store['original_branded_name']} ({billa_store['price']}€)")
    print(f"Checked {count} products. Found {matches} real Billa matches.")
