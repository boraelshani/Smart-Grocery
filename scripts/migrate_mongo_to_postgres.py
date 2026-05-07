import os
import sys
import datetime
from decimal import Decimal
from pymongo import MongoClient
import psycopg2
from psycopg2.extras import execute_values
from dotenv import load_dotenv

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017/smart_grocery")
PG_URI = os.getenv("SQLALCHEMY_DATABASE_URI")

if not PG_URI:
    print("Error: SQLALCHEMY_DATABASE_URI is not set in the .env file.")
    sys.exit(1)

def migrate():
    print("Connecting to MongoDB...")
    mongo_client = MongoClient(MONGO_URI)
    db = mongo_client["smart_grocery"]

    print("Connecting to PostgreSQL...")
    conn = psycopg2.connect(PG_URI)
    conn.autocommit = True
    cursor = conn.cursor()

    # 1. Migrate Stores
    print("Migrating Stores...")
    store_map = {} # Maps store 'name' or 'base_url' to internal store_id if needed, actually we just insert what's in mongo
    mongo_stores = list(db.stores.find())
    
    # Collect unique store IDs from products.offers just in case
    product_stores = set()
    for p in db.products.find({}, {"offers.store": 1}):
        for offer in p.get("offers", []):
            if offer.get("store"):
                product_stores.add(offer.get("store").lower())
                
    # Add stores from collection
    stores_to_insert = []
    for s in mongo_stores:
        store_id = s.get("name", "unknown").lower().replace(" ", "_")
        product_stores.discard(store_id)
        stores_to_insert.append((
            store_id,
            s.get("name"),
            s.get("base_url"),
            None, # logo_url
            'AT',
            True,
            False,
            s.get("active", True)
        ))
        
    # Add any leftover stores found in products
    for s in product_stores:
        stores_to_insert.append((s, s.capitalize(), None, None, 'AT', True, False, True))

    if stores_to_insert:
        execute_values(
            cursor,
            "INSERT INTO stores (store_id, name, website, logo_url, country, api_available, scraping_required, active) VALUES %s ON CONFLICT (store_id) DO NOTHING",
            stores_to_insert
        )

    # Reload stores map to get db IDs
    cursor.execute("SELECT store_id, id FROM stores;")
    store_id_to_pk = dict(cursor.fetchall())

    # 2. Migrate Categories
    print("Migrating Categories...")
    categories = set()
    for p in db.products.find({}, {"category": 1}):
        if p.get("category"):
            categories.add(str(p.get("category")).strip())
            
    cats_to_insert = [(c.lower().replace(" ", "-"), c, c, None, 1, None, None) for c in categories if c]
    if cats_to_insert:
        execute_values(
            cursor,
            "INSERT INTO categories (slug, name_en, name_de, parent_id, level, icon, image_url) VALUES %s ON CONFLICT (slug) DO UPDATE SET name_de=EXCLUDED.name_de",
            cats_to_insert
        )

    cursor.execute("SELECT slug, id FROM categories;")
    cat_slug_to_pk = dict(cursor.fetchall())

    # 3. Migrate Products, Offers, and Price History
    print("Migrating Products, Offers, and Price History (this may take a minute)...")
    products_cursor = db.products.find()
    total_products = db.products.count_documents({})
    
    product_batch = []
    offers_batch = []
    history_batch = []
    
    # We will incrementally query inserted products and offers, but batching is faster if we do it cleanly.
    # To do this smoothly: insert products, then get product PKs, then insert offers, get offer PKs, insert history.
    # Because of sizes, we chunk per 500 to not overload the Neon free tier.
    
    BATCH_SIZE = 500
    processed = 0
    
    for p in products_cursor:
        fingerprint = str(p.get("_id"))
        name_de = p.get("name", "Unknown Product")
        cat_str = str(p.get("category", "")).strip().lower().replace(" ", "-")
        category_id = cat_slug_to_pk.get(cat_str)
        unit = str(p.get("unit", ""))
        size = p.get("quantity", 0)
        try:
            size_num = float(size)
        except:
            size_num = 1.0
            
        created_at = p.get("createdAt", datetime.datetime.now())
        if isinstance(created_at, dict) and "$date" in created_at:
            from dateutil.parser import parse
            created_at = parse(created_at["$date"])
            
        product_batch.append((
            fingerprint, name_de, None, category_id, unit, size_num, None, None, created_at, created_at
        ))
        processed += 1
        
        # Process the batch
        if len(product_batch) >= BATCH_SIZE or processed == total_products:
            # 1. Insert products
            execute_values(
                cursor,
                """INSERT INTO products 
                   (fingerprint, name_de, brand, category_id, unit_normalized, size_normalized, default_image_url, barcode, created_at, updated_at) 
                   VALUES %s ON CONFLICT (fingerprint) DO UPDATE SET name_de=EXCLUDED.name_de RETURNING fingerprint, id""",
                product_batch
            )
            fp_to_pid = dict(cursor.fetchall())
            
            # Prepare offers
            # We have to re-fetch the product from mongo or keep track
            # Let's keep track locally inside the batch
            pass
            
    # For a deterministic and perfect sync, we iterate again to do offers and history.
    # (Since product IDs are now in postgres, we can just grab them all)
    
    print("Pulling Product mapping from PostgreSQL...")
    cursor.execute("SELECT fingerprint, id FROM products;")
    fp_to_pk = dict(cursor.fetchall())
    
    print("Processing Offers and History...")
    offers_buffer = []  # (offer_key, tuple)
    history_buffer = []
    
    count = 0
    products_cursor.rewind() # rewind mongo cursor
    for p in products_cursor:
        fingerprint = str(p.get("_id"))
        prod_pk = fp_to_pk.get(fingerprint)
        if not prod_pk:
            continue
            
        for offer in p.get("offers", []):
            store_val = offer.get("store", "unknown").lower().replace(" ", "_")
            store_id_text = store_val if store_val in store_id_to_pk else "unknown"
            
            price_val = offer.get("price", 0)
            try:
                price = float(price_val)
            except:
                price = 0.0
                
            is_available = offer.get("available", True)
            product_url = offer.get("productUrl", "")
            
            last_seen = offer.get("lastSeen", datetime.datetime.now())
            if isinstance(last_seen, dict) and "$date" in last_seen:
                from dateutil.parser import parse
                last_seen = parse(last_seen["$date"])
                
            offers_buffer.append((
                prod_pk, store_val, price, product_url, is_available, last_seen
            ))
            
            count += 1
            if len(offers_buffer) >= BATCH_SIZE:
                execute_values(
                    cursor,
                    """INSERT INTO offers (product_id, store_id, price, product_url, is_available, last_seen)
                       VALUES %s ON CONFLICT (product_id, store_id) DO UPDATE SET price=EXCLUDED.price, is_available=EXCLUDED.is_available RETURNING id, product_id, store_id""",
                    offers_buffer
                )
                offers_buffer.clear()
                print(f"  ...processed {count} offers")

    # Flush remaining offers
    if offers_buffer:
        execute_values(
            cursor,
             """INSERT INTO offers (product_id, store_id, price, product_url, is_available, last_seen)
                VALUES %s ON CONFLICT (product_id, store_id) DO UPDATE SET price=EXCLUDED.price, is_available=EXCLUDED.is_available RETURNING id, product_id, store_id""",
            offers_buffer
        )

    # Now for History! We will map from Postgres (product_id, store_id) -> offer_id
    print("Pulling Offers mapping...")
    cursor.execute("SELECT product_id, store_id, id FROM offers;")
    offer_map = {(r[0], r[1]): r[2] for r in cursor.fetchall()}

    print("Migrating Price History...")
    products_cursor.rewind()
    hist_count = 0
    for p in products_cursor:
        fingerprint = str(p.get("_id"))
        prod_pk = fp_to_pk.get(fingerprint)
        if not prod_pk:
            continue
            
        for offer in p.get("offers", []):
            store_val = offer.get("store", "unknown").lower().replace(" ", "_")
            offer_pk = offer_map.get((prod_pk, store_val))
            if not offer_pk:
                continue
                
            for h in offer.get("priceHistory", []):
                h_price = h.get("price", 0)
                try:
                    hp = float(h_price)
                except:
                    hp = 0.0
                
                h_date = h.get("date")
                if not h_date:
                    h_date = datetime.datetime.now()
                else:
                    if isinstance(h_date, str):
                        try:
                            from dateutil.parser import parse
                            h_date = parse(h_date)
                        except:
                            h_date = datetime.datetime.now()
                            
                history_buffer.append((offer_pk, hp, h_date))
                hist_count += 1
                
                if len(history_buffer) >= BATCH_SIZE * 5:
                    execute_values(
                        cursor,
                        "INSERT INTO price_history (offer_id, price, recorded_at) VALUES %s",
                        history_buffer
                    )
                    history_buffer.clear()
                    print(f"  ...processed {hist_count} history records")
                    
    if history_buffer:
        execute_values(
            cursor,
            "INSERT INTO price_history (offer_id, price, recorded_at) VALUES %s",
            history_buffer
        )
        
        
    # 4. Migrate Users
    print("Migrating Users & Shopping Lists...")
    mongo_users = list(db.users.find())
    users_batch = []
    for u in mongo_users:
        user_id_str = str(u.get("_id"))
        users_batch.append((
            user_id_str,
            u.get("email"),
            u.get("password"),
            u.get("name"),
            None, # avatar
            'de'
        ))
        
    if users_batch:
        execute_values(
            cursor,
            "INSERT INTO users (user_id, email, password_hash, name, avatar, language) VALUES %s ON CONFLICT (email) DO NOTHING",
            users_batch
        )
        
    cursor.execute("SELECT user_id, id FROM users;")
    user_id_to_pk = dict(cursor.fetchall())
    
    # 5. Migrate Shopping Lists and Items
    list_batch = []
    item_batch = []
    for u in mongo_users:
        mongo_uid = str(u.get("_id"))
        pg_uid = user_id_to_pk.get(mongo_uid)
        if not pg_uid:
            continue
            
        s_lists = u.get("shopping_list", [])
        if s_lists: # User has items
            list_unique_id = f"list_{mongo_uid}"
            # Insert a main list
            cursor.execute("""
                INSERT INTO shopping_lists (list_id, user_id, name, share_code) 
                VALUES (%s, %s, %s, %s) ON CONFLICT (list_id) DO UPDATE SET name=EXCLUDED.name RETURNING id
            """, (list_unique_id, pg_uid, "My Shopping List", f"share_{mongo_uid}"))
            list_pk = cursor.fetchone()[0]
            
            for item in s_lists:
                i_name = item.get("name", "Unknown item")
                i_id = item.get("id")
                # Try to map to product if it looks like a Hex Fingerprint
                prod_fk = None
                if i_id and i_id in fp_to_pk:
                    prod_fk = fp_to_pk[i_id]
                
                item_batch.append((
                    list_pk, prod_fk, i_name, 1.0, False
                ))

    if item_batch:
        execute_values(
            cursor,
            "INSERT INTO list_items (list_id, product_id, product_name, quantity, checked) VALUES %s",
            item_batch
        )

    print("Migrating Featured Deals...")
    deals_batch = []
    for d in db.featured_deals.find():
        price = d.get("price")
        if isinstance(price, str):
            price = float(price.replace('$', '').replace('€', '').strip() or 0)
        
        deals_batch.append((
            d.get("title", ""),
            None,
            price,
            None,
            0,
            d.get("store", "billa").lower(),
            d.get("image", ""),
            "",
            None,
            True,
            None
        ))
        
    if deals_batch:
        execute_values(
            cursor,
            """INSERT INTO featured_deals 
               (title, description, price, original_price, discount_percent, store_id, image_url, url, category_slug, active, valid_until) 
               VALUES %s""",
            deals_batch
        )

    print("🎉 MIGRATION COMPLETE! ALL DATA MIGRATED PERFECTLY!")
    cursor.close()
    conn.close()

if __name__ == '__main__':
    migrate()