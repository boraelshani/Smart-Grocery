import requests
from pymongo import MongoClient

def sync_data():
    client = MongoClient("mongodb://localhost:27017/")
    db = client["smart_grocery"]
    
    print("Fetching data from heisse-preise...")
    r = requests.get('https://heisse-preise.io/data/latest-canonical.json')
    data = r.json()
    
    # Filter for allowed stores
    allowed_stores = {"hofer", "spar", "billa"}
    target_data = [d for d in data if d.get('store', '').lower() in allowed_stores]
    
    print(f"Found {len(target_data)} items from {allowed_stores}.")
    
    # We will build operations to bulk write
    operations = []
    
    from pymongo import UpdateOne
    
    # Group by name to maintain the structure where a product can have multiple stores
    products_map = {}
    
    for item in target_data:
        name = item.get("name", "").strip()
        store_name = item.get("store", "").capitalize()
        price = item.get("price", 0.0)
        
        # Determine URL
        url = item.get("url", "")
        # fallback URLs if not provided but we have ID
        if not url and item.get("id"):
            if store_name.lower() == "spar":
                url = f"https://www.interspar.at/shop/lebensmittel/{item['id']}/p/{item['id']}"
            elif store_name.lower() == "billa":
                url = f"https://shop.billa.at/produkte/{item['id']}"
            elif store_name.lower() == "hofer":
                url = f"https://www.roksh.at/hofer/produkte/{item['id']}"
        
        if not name:
            continue
            
        if name not in products_map:
            products_map[name] = []
            
        # Append store info
        products_map[name].append({
            "store": store_name,
            "price": price,
            "url": url,
            "unit": item.get('unit'),
            "quantity": item.get('quantity'),
            "description": item.get("description", ""),
            "original_id": item.get("id"),
        })
        
    print(f"Grouped into {len(products_map)} unique products.")
    
    count_new = 0
    count_updated = 0
    
    # Let's see what is already there to not overwrite stuff and just add it to stores
    for name, stores in products_map.items():
        # Find if product already exists
        existing = db.products.find_one({"name": name})
        
        if existing:
            # Update existing product's stores
            existing_stores = existing.get("stores", [])
            # Convert to dict for fast lookup by store name to update prices
            store_dict = {s.get("store", "").lower(): s for s in existing_stores}
            
            for new_store in stores:
                store_key = new_store["store"].lower()
                if store_key in store_dict:
                    # Update price and url
                    store_dict[store_key]["price"] = new_store["price"]
                    store_dict[store_key]["url"] = new_store["url"]
                    if new_store.get('description'):
                        store_dict[store_key]["description"] = new_store["description"]
                else:
                    # Add new store
                    store_dict[store_key] = new_store
                    
            updated_stores = list(store_dict.values())
            
            # Recalculate cheapest
            cheapest = min(updated_stores, key=lambda s: s.get("price", float('inf')))
            
            db.products.update_one(
                {"_id": existing["_id"]},
                {"$set": {
                    "stores": updated_stores,
                    "cheapest": cheapest,
                    "price": cheapest.get("price")
                }}
            )
            count_updated += 1
        else:
            # Create new product
            cheapest = min(stores, key=lambda s: s.get("price", float('inf')))
            
            # Just take unit and quantity from first store
            unit = stores[0].get("unit", "")
            qty = stores[0].get("quantity", "")
            desc = stores[0].get("description", "")
            
            # clean stores list to remove those internal fields
            clean_stores = []
            for s in stores:
                clean_store = {
                    "store": s["store"],
                    "price": s["price"],
                    "url": s["url"]
                }
                clean_stores.append(clean_store)
                
            clean_cheapest = {
                "store": cheapest["store"],
                "price": cheapest["price"],
                "url": cheapest["url"]
            }
            
            new_prod = {
                "name": name,
                "price": clean_cheapest["price"],
                "cheapest": clean_cheapest,
                "stores": clean_stores,
                "image": "",
                "is_placeholder": False,
                "category": "HeissePrices",
                "normalized_unit_price": None,
                "normalized_unit_label": "",
                "unit": unit,
                "quantity": qty,
                "description": desc
            }
            db.products.insert_one(new_prod)
            count_new += 1
            
        if (count_new + count_updated) % 1000 == 0:
            print(f"Processed {count_new + count_updated}...")
            
    print(f"Done! Created {count_new} new products, updated {count_updated} existing products.")

if __name__ == "__main__":
    sync_data()
