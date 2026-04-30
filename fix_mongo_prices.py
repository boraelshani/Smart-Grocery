from pymongo import MongoClient

def fix_prices():
    client = MongoClient("mongodb://localhost:27017/")
    db = client["smart_grocery"]
    
    count = 0
    for product in db.products.find({"stores": {"$exists": True}}):
        stores = product.get("stores", [])
        changed = False
        
        for store in stores:
            if isinstance(store.get("price"), str):
                try:
                    store["price"] = float(store["price"].replace(',', '.'))
                    changed = True
                except (ValueError, TypeError):
                    store["price"] = 0.0
                    changed = True
                    
        if changed:
            db.products.update_one(
                {"_id": product["_id"]},
                {"$set": {"stores": stores}}
            )
            count += 1
            
    print(f"Fixed string prices in {count} documents.")

if __name__ == "__main__":
    fix_prices()
