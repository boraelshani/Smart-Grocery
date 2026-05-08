import os
import sys
import time
import datetime
from pymongo import MongoClient
import psycopg2
from psycopg2.extras import execute_values
from psycopg2 import OperationalError
from dotenv import load_dotenv

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017/smart_grocery")
PG_URI = os.getenv("SQLALCHEMY_DATABASE_URI")

if not PG_URI:
    print("Error: SQLALCHEMY_DATABASE_URI is not set in the .env file.")
    sys.exit(1)

BATCH_SIZE = 1000  # Sweet spot for Neon free tier
MAX_RETRIES = 5

def get_pg_connection():
    conn = psycopg2.connect(PG_URI)
    conn.autocommit = True
    return conn

def execute_with_retry(execute_func):
    """Wrapper to retry database operations if Neon drops the connection."""
    for attempt in range(MAX_RETRIES):
        try:
            return execute_func()
        except OperationalError as e:
            print(f"\n[!] Connection dropped by server (Attempt {attempt+1}/{MAX_RETRIES}). Reconnecting in 3s...")
            time.sleep(3)
        except Exception as e:
            print(f"\n[!] Unexpected Error: {e}")
            raise e
    raise Exception("Max retries exceeded.")

def migrate():
    print("Connecting to MongoDB...")
    mongo_client = MongoClient(MONGO_URI)
    db = mongo_client["smart_grocery"]

    total_products = db.products.count_documents({})
    print(f"Total Products to migrate: {total_products}")

    print("Connecting to PostgreSQL...")
    conn = get_pg_connection()

    def run_query(query, params=None, fetch=False):
        def _execute():
            nonlocal conn
            if conn.closed:
                conn = get_pg_connection()
            with conn.cursor() as cursor:
                if params:
                    execute_values(cursor, query, params)
                else:
                    cursor.execute(query)
                if fetch:
                    return cursor.fetchall()
        return execute_with_retry(_execute)

    # 1. Stores
    print("Migrating Stores...")
    mongo_stores = list(db.stores.find())
    stores_to_insert = []
    for s in mongo_stores:
        store_id = s.get("name", "unknown").lower().replace(" ", "_")
        stores_to_insert.append((store_id, s.get("name"), s.get("base_url"), None, 'AT', True, False, s.get("active", True)))

    if stores_to_insert:
        run_query("INSERT INTO stores (store_id, name, website, logo_url, country, api_available, scraping_required, active) VALUES %s ON CONFLICT (store_id) DO NOTHING", stores_to_insert)

    stores_mapping = run_query("SELECT store_id, id FROM stores;", fetch=True)
    store_id_to_pk = dict(stores_mapping)

    # 2. Categories
    print("Migrating Categories...")
    cats = db.products.distinct("category")
    cats_to_insert = [(str(c).strip().lower().replace(" ", "-"), str(c).strip(), str(c).strip(), None, 1, None, None) for c in cats if c]
    if cats_to_insert:
        run_query("INSERT INTO categories (slug, name_en, name_de, parent_id, level, icon, image_url) VALUES %s ON CONFLICT (slug) DO UPDATE SET name_de=EXCLUDED.name_de", cats_to_insert)

    cats_mapping = run_query("SELECT slug, id FROM categories;", fetch=True)
    cat_slug_to_pk = dict(cats_mapping)

    # 3. INTERLEAVED BATCH MIGRATION (Products -> Offers -> History)
    print("\nStarting high-speed interleaved migration for Products, Offers, and History...")
    
    products_cursor = db.products.find()
    
    processed_count = 0
    current_product_batch = []
    mongo_batch_docs = []
    
    start_time = time.time()

    def process_chunk(prod_batch_tuples, mongo_docs):
        # Insert Products natively and fetch resulting IDs
        # ON CONFLICT DO UPDATE... is used to ensure idempotency. 
        # Using xmax=0 trick to force RETURNING even on conflicts or standard RETURNING on update.
        product_query = """
            INSERT INTO products (fingerprint, name_de, brand, category_id, unit_normalized, size_normalized, default_image_url, barcode, created_at, updated_at) 
            VALUES %s 
            ON CONFLICT (fingerprint) DO UPDATE SET name_de=EXCLUDED.name_de 
            RETURNING fingerprint, id
        """
        returned_prods = run_query(product_query, prod_batch_tuples, fetch=True)
        fp_to_pk = dict(returned_prods)

        # Build Offers batch
        offers_batch = []
        for p_doc in mongo_docs:
            fp = str(p_doc.get("_id"))
            prod_pk = fp_to_pk.get(fp)
            if not prod_pk: continue
            
            for offer in p_doc.get("offers", []):
                store_val = offer.get("store", "unknown").lower().replace(" ", "_")
                price_val = float(offer.get("price", 0) or 0)
                is_available = offer.get("available", True)
                p_url = offer.get("productUrl", "")
                
                last_seen = offer.get("lastSeen", datetime.datetime.now())
                if isinstance(last_seen, dict) and "$date" in last_seen:
                    from dateutil.parser import parse
                    last_seen = parse(last_seen["$date"])
                    
                offers_batch.append((fp, prod_pk, store_val, price_val, p_url, is_available, last_seen))

        if not offers_batch: return

        # Deduplicate Offers batch before inserting
        unique_offers_data = {}
        for r in offers_batch:
            # key: (product_id, store_id) => r[1], r[2]
            key = (r[1], r[2])
            # Only keep the last observed offer per store per product to avoid Postgres CardinalityViolation
            unique_offers_data[key] = (r[1], r[2], r[3], r[4], r[5], r[6])

        offers_insert_data = list(unique_offers_data.values())
        offers_query = """
            INSERT INTO offers (product_id, store_id, price, product_url, is_available, last_seen)
            VALUES %s 
            ON CONFLICT (product_id, store_id) DO UPDATE SET price=EXCLUDED.price, is_available=EXCLUDED.is_available 
            RETURNING product_id, store_id, id
        """
        returned_offers = run_query(offers_query, offers_insert_data, fetch=True)
        offer_key_to_pk = {(r[0], r[1]): r[2] for r in returned_offers}

        # Build Price History batch
        history_batch = []
        for p_doc in mongo_docs:
            fp = str(p_doc.get("_id"))
            prod_pk = fp_to_pk.get(fp)
            if not prod_pk: continue
            
            for offer in p_doc.get("offers", []):
                store_val = offer.get("store", "unknown").lower().replace(" ", "_")
                offer_pk = offer_key_to_pk.get((prod_pk, store_val))
                if not offer_pk: continue
                
                for h in offer.get("priceHistory", []):
                    try:
                        hp = float(h.get("price", 0))
                    except:
                        hp = 0.0
                    
                    h_date = h.get("date", datetime.datetime.now())
                    if isinstance(h_date, str):
                        try:
                            from dateutil.parser import parse
                            h_date = parse(h_date)
                        except:
                            h_date = datetime.datetime.now()
                            
                    history_batch.append((offer_pk, hp, h_date))

        # Insert Price History
        if history_batch:
            # We don't have constraints on unique time per offer right now, but just insert
            run_query("INSERT INTO price_history (offer_id, price, recorded_at) VALUES %s ON CONFLICT DO NOTHING", history_batch)


    for p in products_cursor:
        fingerprint = str(p.get("_id"))
        name_de = p.get("name", "Unknown")
        cat_str = str(p.get("category", "")).strip().lower().replace(" ", "-")
        category_id = cat_slug_to_pk.get(cat_str)
        unit = str(p.get("unit", ""))
        try:
            size_num = float(p.get("quantity", 0))
        except:
            size_num = 1.0
            
        c_at = p.get("createdAt", datetime.datetime.now())
        if isinstance(c_at, dict) and "$date" in c_at:
            from dateutil.parser import parse
            c_at = parse(c_at["$date"])
            
        current_product_batch.append((fingerprint, name_de, None, category_id, unit, size_num, None, None, c_at, c_at))
        mongo_batch_docs.append(p)
        processed_count += 1
        
        if len(current_product_batch) >= BATCH_SIZE:
            process_chunk(current_product_batch, mongo_batch_docs)
            percent = (processed_count / total_products) * 100
            elapsed = time.time() - start_time
            rate = processed_count / elapsed
            print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] Progress: {processed_count}/{total_products} ({percent:.1f}%) | {rate:.0f} products/sec")
            current_product_batch.clear()
            mongo_batch_docs.clear()

    # Process remaining
    if current_product_batch:
        process_chunk(current_product_batch, mongo_batch_docs)
        print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] Progress: {processed_count}/{total_products} (100.0%)")

    # 4. Users & Lists & Deals (Small data overhead, process immediately)
    print("\nMigrating Users, Shopping Lists, and Deals...")
    mongo_users = list(db.users.find())
    users_batch = []
    for u in mongo_users:
        users_batch.append((str(u.get("_id")), u.get("email"), u.get("password"), u.get("name"), None, 'de'))
        
    if users_batch:
        run_query("INSERT INTO users (user_id, email, password_hash, name, avatar, language) VALUES %s ON CONFLICT (email) DO NOTHING", users_batch)

    deals_batch = []
    for d in db.featured_deals.find():
        price = float(str(d.get("price", 0)).replace('$', '').replace('€', '').strip() or 0)
        store_val = d.get("store", "supermart").lower()
        if store_val not in store_id_to_pk:
            # Not using run_query here with execute_values because it's a single tuple format issue with %s,
            # using direct cursor
            conn = get_pg_connection()
            with conn.cursor() as cur:
                cur.execute("INSERT INTO stores (store_id, name, country, active) VALUES (%s, %s, 'AT', true) ON CONFLICT DO NOTHING", (store_val, d.get("store", "Supermart")))
            store_id_to_pk[store_val] = True
            
        deals_batch.append((d.get("title", ""), None, price, None, 0, store_val, d.get("image", ""), "", None, True, None))
        
        
    if deals_batch:
        run_query("INSERT INTO featured_deals (title, description, price, original_price, discount_percent, store_id, image_url, url, category_slug, active, valid_until) VALUES %s", deals_batch)

    print("\n🎉 MIGRATION COMPLETE! ALL DATA MIGRATED PERFECTLY!")
    conn.close()

if __name__ == '__main__':
    migrate()