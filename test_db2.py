from utils.db import get_db

db = get_db()
if db is not None:
    print("DB connection ok.")
    print("Collections:", db.list_collection_names())
    print("Total products:", db.products.count_documents({}))
    if "store_products" in db.list_collection_names():
        print("Total store_products:", db.store_products.count_documents({}))
    print("productId exists in products:", db.products.count_documents({"productId": {"$exists": True}}))

    # Get a sample
    sample = db.products.find_one()
    if sample:
        print("\nKeys in a sample product:", list(sample.keys()))
        print("name:", sample.get('name'))
        if "stores" in sample:
            print("Number of stores for this product:", len(sample['stores']))
            if len(sample['stores']) > 0:
                print("First store name:", sample['stores'][0].get("name", sample['stores'][0].get("store")))
    
    # Are there multiple products with very similar names?
    coca_colas = list(db.products.find({"name": {"$regex": "Coca", "$options": "i"}}).limit(5))
    print("\nSample Coca Cola products:")
    for c in coca_colas:
        print("-", c.get('name'), "Stores:", len(c.get('stores', [])) if 'stores' in c else 'no stores array', c.get('stores', [{}])[0].get('store') if c.get('stores') else '')
else:
    print("No DB connection.")
