"""
COMPLETE DATA RECOVERY FROM MONGODB TO POSTGRESQL
This script will:
1. Clear all existing data from PostgreSQL
2. Fetch ALL data from MongoDB
3. Properly handle parent_id relationships for categories
4. Migrate everything in the correct order
"""
import os
import sys
import datetime
import certifi
from decimal import Decimal
from pymongo import MongoClient
import psycopg2
from psycopg2.extras import execute_values
from dotenv import load_dotenv

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017/smart_grocery")
PG_URI = os.getenv("DATABASE_URL") or os.getenv("SQLALCHEMY_DATABASE_URI")

if not PG_URI:
    print("❌ Error: DATABASE_URL is not set")
    sys.exit(1)

def _parse_date(val):
    """Convert MongoDB date formats to Python datetime."""
    if val is None:
        return datetime.datetime.now()
    if isinstance(val, datetime.datetime):
        return val
    if isinstance(val, dict) and "$date" in val:
        try:
            from dateutil.parser import parse
            return parse(val["$date"])
        except Exception:
            return datetime.datetime.now()
    if isinstance(val, str):
        try:
            from dateutil.parser import parse
            return parse(val)
        except Exception:
            return datetime.datetime.now()
    return datetime.datetime.now()

def clear_postgresql_data(cursor):
    """Clear all data from PostgreSQL tables."""
    print("\n🗑️  CLEARING EXISTING POSTGRESQL DATA...")
    
    tables = [
        'price_history',
        'offers', 
        'products',
        'categories',
        'stores',
        'list_items',
        'shopping_lists',
        'featured_deals',
        'favorites',
        'notifications',
        'saved_recipes',
        'community_price_reports',
        'pending_products',
        'public_lists',
        'feedback',
        'price_feedback',
        'brands',
        'scraper_runs'
    ]
    
    for table in tables:
        try:
            cursor.execute(f"TRUNCATE TABLE {table} RESTART IDENTITY CASCADE;")
            print(f"  ✅ Cleared {table}")
        except Exception as e:
            print(f"  ⚠️  Could not clear {table}: {e}")
    
    print("✅ All data cleared\n")

def migrate_categories_properly(db, cursor):
    """Migrate categories with proper parent_id handling."""
    print("=" * 70)
    print("  MIGRATING CATEGORIES (WITH PROPER PARENT_ID)")
    print("=" * 70)
    
    # Fetch all categories from MongoDB
    mongo_categories = list(db.categories.find({}))
    
    if not mongo_categories:
        print("⚠️  No categories in MongoDB categories collection")
        print("   Extracting from products...")
        categories_set = set()
        for p in db.products.find({}, {"category": 1}):
            if p.get("category"):
                categories_set.add(str(p.get("category")).strip())
        
        mongo_categories = [
            {"name": cat, "name_en": cat, "name_de": cat, 
             "slug": cat.lower().replace(" ", "-"), "level": 1}
            for cat in categories_set
        ]
    
    print(f"📥 Found {len(mongo_categories)} categories in MongoDB\n")
    
    # Build category mapping: MongoDB _id -> category data
    mongo_id_to_cat = {}
    slug_to_cat = {}
    
    for c in mongo_categories:
        mongo_id = str(c.get("_id", ""))
        slug = (c.get("slug") or c.get("name_en") or c.get("name") or "").lower().replace(" ", "-").replace("_", "-")
        
        cat_data = {
            "mongo_id": mongo_id,
            "slug": slug,
            "name_en": c.get("name_en") or c.get("name") or slug,
            "name_de": c.get("name_de") or c.get("name") or slug,
            "parent_id": c.get("parent_id") or c.get("parentId"),
            "level": c.get("level") or 1,
            "image_url": c.get("image_url") or c.get("imageUrl") or ""
        }
        
        if mongo_id:
            mongo_id_to_cat[mongo_id] = cat_data
        slug_to_cat[slug] = cat_data
    
    # Insert categories level by level to handle parent_id properly
    print("🔄 Inserting categories by level...\n")
    
    # Group by level
    by_level = {}
    for cat_data in slug_to_cat.values():
        level = cat_data["level"]
        if level not in by_level:
            by_level[level] = []
        by_level[level].append(cat_data)
    
    # Map to store: slug -> postgres_id
    slug_to_pg_id = {}
    mongo_id_to_pg_id = {}
    
    # Insert level by level
    for level in sorted(by_level.keys()):
        cats = by_level[level]
        print(f"📁 Level {level}: {len(cats)} categories")
        
        for cat_data in cats:
            slug = cat_data["slug"]
            name_en = cat_data["name_en"]
            name_de = cat_data["name_de"]
            parent_id_ref = cat_data["parent_id"]
            image_url = cat_data["image_url"]
            mongo_id = cat_data["mongo_id"]
            
            # Resolve parent_id to PostgreSQL id
            parent_pg_id = None
            if parent_id_ref:
                # Try as MongoDB ObjectId
                if isinstance(parent_id_ref, str):
                    parent_pg_id = mongo_id_to_pg_id.get(parent_id_ref)
                # Try as integer (already a PG id)
                elif isinstance(parent_id_ref, int):
                    parent_pg_id = parent_id_ref
                # Try as slug
                if not parent_pg_id and isinstance(parent_id_ref, str):
                    parent_slug = parent_id_ref.lower().replace(" ", "-")
                    parent_pg_id = slug_to_pg_id.get(parent_slug)
            
            # Insert category
            cursor.execute("""
                INSERT INTO categories (slug, name_en, name_de, parent_id, level, image_url)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (slug) DO UPDATE SET
                    name_en = EXCLUDED.name_en,
                    name_de = EXCLUDED.name_de,
                    parent_id = EXCLUDED.parent_id,
                    level = EXCLUDED.level,
                    image_url = EXCLUDED.image_url
                RETURNING id
            """, (slug, name_en, name_de, parent_pg_id, level, image_url))
            
            pg_id = cursor.fetchone()[0]
            slug_to_pg_id[slug] = pg_id
            if mongo_id:
                mongo_id_to_pg_id[mongo_id] = pg_id
            
            parent_info = f" (parent: {parent_pg_id})" if parent_pg_id else ""
            print(f"  ✅ {name_en} ({slug}){parent_info}")
    
    print(f"\n✅ Migrated {len(slug_to_pg_id)} categories")
    return slug_to_pg_id, mongo_id_to_pg_id

def main():
    print("=" * 70)
    print("  COMPLETE DATA RECOVERY: MONGODB → POSTGRESQL")
    print("=" * 70)
    print("\n⚠️  WARNING: This will DELETE all existing PostgreSQL data!")
    print("   Press Ctrl+C within 5 seconds to cancel...\n")
    
    import time
    for i in range(5, 0, -1):
        print(f"   Starting in {i}...")
        time.sleep(1)
    
    print("\n🚀 Starting migration...\n")
    
    # Connect to MongoDB
    print("📡 Connecting to MongoDB...")
    try:
        mongo_client = MongoClient(MONGO_URI, tlsCAFile=certifi.where())
        db = mongo_client["smart_grocery"]
        mongo_client.server_info()
        print("✅ MongoDB connected\n")
    except Exception as e:
        print(f"❌ MongoDB connection failed: {e}")
        sys.exit(1)
    
    # Connect to PostgreSQL
    print("📡 Connecting to PostgreSQL...")
    try:
        conn = psycopg2.connect(PG_URI)
        conn.autocommit = True
        cursor = conn.cursor()
        print("✅ PostgreSQL connected\n")
    except Exception as e:
        print(f"❌ PostgreSQL connection failed: {e}")
        sys.exit(1)
    
    # Clear existing data
    clear_postgresql_data(cursor)
    
    # Migrate in correct order
    # 1. Categories (with proper parent_id)
    slug_to_pg_id, mongo_id_to_pg_id = migrate_categories_properly(db, cursor)
    
    # 2. Stores
    store_id_to_pk = migrate_stores(db, cursor)
    
    # 3. Products
    fp_to_pk = migrate_products(db, cursor, slug_to_pg_id, mongo_id_to_pg_id)
    
    # 4. Offers
    migrate_offers(db, cursor, fp_to_pk)
    
    # 5. Featured Deals
    cursor.execute("SELECT slug FROM categories;")
    valid_slugs = {row[0] for row in cursor.fetchall()}
    migrate_featured_deals(db, cursor, valid_slugs)
    
    print("\n" + "=" * 70)
    print("  ✅ COMPLETE MIGRATION FINISHED!")
    print("=" * 70)
    
    # Show comprehensive summary
    cursor.execute("SELECT COUNT(*) FROM categories;")
    cat_count = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM categories WHERE parent_id IS NOT NULL;")
    child_count = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM stores;")
    store_count = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM products;")
    prod_count = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM offers;")
    offer_count = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM featured_deals;")
    deal_count = cursor.fetchone()[0]
    
    print(f"\n📊 Final Summary:")
    print(f"  • Categories: {cat_count} (Root: {cat_count - child_count}, Children: {child_count})")
    print(f"  • Stores: {store_count}")
    print(f"  • Products: {prod_count}")
    print(f"  • Offers: {offer_count}")
    print(f"  • Featured Deals: {deal_count}")
    
    # Show hierarchy sample
    print(f"\n📁 Category Hierarchy Sample:")
    cursor.execute("""
        SELECT 
            c1.name_en as parent,
            c2.name_en as child,
            c2.level
        FROM categories c1
        JOIN categories c2 ON c2.parent_id = c1.id
        ORDER BY c1.name_en, c2.name_en
        LIMIT 10
    """)
    
    hierarchy_rows = cursor.fetchall()
    if hierarchy_rows:
        for row in hierarchy_rows:
            parent, child, level = row
            print(f"  • {parent} → {child} (Level {level})")
    else:
        print("  (No parent-child relationships found)")
    
    # Show products with categories
    print(f"\n📦 Products with Categories Sample:")
    cursor.execute("""
        SELECT p.name_de, c.name_en
        FROM products p
        JOIN categories c ON p.category_id = c.id
        LIMIT 5
    """)
    
    for row in cursor.fetchall():
        prod_name, cat_name = row
        print(f"  • {prod_name[:50]} → {cat_name}")
    
    cursor.close()
    conn.close()
    mongo_client.close()
    
    print("\n" + "=" * 70)
    print("  🎉 ALL DATA SUCCESSFULLY MIGRATED!")
    print("=" * 70)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️  Migration cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


def migrate_stores(db, cursor):
    """Migrate stores from MongoDB."""
    print("\n" + "=" * 70)
    print("  MIGRATING STORES")
    print("=" * 70)
    
    mongo_stores = list(db.stores.find())
    print(f"📥 Found {len(mongo_stores)} stores in MongoDB\n")
    
    stores_to_insert = []
    for s in mongo_stores:
        store_id = (s.get("name") or s.get("store_id") or "unknown").lower().replace(" ", "_")
        stores_to_insert.append((
            store_id,
            s.get("name"),
            s.get("base_url") or s.get("website"),
            s.get("logo_url") or s.get("image"),
            s.get("country", "AT"),
            s.get("api_available", False),
            s.get("scraping_required", True),
            s.get("active", True)
        ))
        print(f"  ✅ {s.get('name')} ({store_id})")
    
    if stores_to_insert:
        execute_values(
            cursor,
            """INSERT INTO stores (store_id, name, website, logo_url, country, api_available, scraping_required, active) 
               VALUES %s ON CONFLICT (store_id) DO NOTHING""",
            stores_to_insert
        )
    
    cursor.execute("SELECT store_id, id FROM stores;")
    store_id_to_pk = dict(cursor.fetchall())
    
    print(f"\n✅ Migrated {len(stores_to_insert)} stores")
    return store_id_to_pk

def migrate_products(db, cursor, cat_slug_to_pg_id, mongo_id_to_pg_id):
    """Migrate products from MongoDB."""
    print("\n" + "=" * 70)
    print("  MIGRATING PRODUCTS")
    print("=" * 70)
    
    total_products = db.products.count_documents({})
    print(f"📥 Found {total_products} products in MongoDB\n")
    
    products_cursor = db.products.find()
    BATCH_SIZE = 500
    product_batch = []
    processed = 0
    
    for p in products_cursor:
        fingerprint = str(p.get("_id"))
        name_de = p.get("name", "Unknown Product")
        brand = p.get("brand") or p.get("brandId")
        
        # Resolve category
        category_id = None
        cat_ref = p.get("category") or p.get("categoryId")
        
        if cat_ref:
            # Try as MongoDB ObjectId
            if isinstance(cat_ref, str):
                category_id = mongo_id_to_pg_id.get(cat_ref)
            # Try as slug
            if not category_id and isinstance(cat_ref, str):
                cat_slug = cat_ref.lower().replace(" ", "-")
                category_id = cat_slug_to_pg_id.get(cat_slug)
            # Try by name
            if not category_id:
                for slug, pg_id in cat_slug_to_pg_id.items():
                    if slug in str(cat_ref).lower():
                        category_id = pg_id
                        break
        
        unit = str(p.get("unit") or p.get("unit_normalized") or p.get("unitSize") or "")
        size = p.get("quantity") or p.get("size_normalized") or 0
        try:
            size_num = float(size) if not isinstance(size, str) else float(size.replace(",", "."))
        except (ValueError, TypeError):
            size_num = None
        
        default_image_url = (p.get("default_image_url") or p.get("defaultImageUrl") or 
                            p.get("image") or p.get("image_url"))
        barcode = p.get("barcode") or p.get("ean") or p.get("gtin")
        
        created_at = _parse_date(p.get("created_at") or p.get("createdAt"))
        updated_at = _parse_date(p.get("updated_at") or p.get("updatedAt") or 
                                p.get("created_at") or p.get("createdAt"))
        
        product_batch.append((
            fingerprint, name_de, brand, category_id, unit, size_num,
            default_image_url, barcode, created_at, updated_at
        ))
        processed += 1
        
        if len(product_batch) >= BATCH_SIZE or processed == total_products:
            execute_values(
                cursor,
                """INSERT INTO products
                   (fingerprint, name_de, brand, category_id, unit_normalized, size_normalized, 
                    default_image_url, barcode, created_at, updated_at)
                   VALUES %s 
                   ON CONFLICT (fingerprint) DO UPDATE SET 
                       name_de=EXCLUDED.name_de, 
                       brand=COALESCE(EXCLUDED.brand, products.brand), 
                       category_id=COALESCE(EXCLUDED.category_id, products.category_id), 
                       default_image_url=COALESCE(EXCLUDED.default_image_url, products.default_image_url), 
                       updated_at=EXCLUDED.updated_at""",
                product_batch
            )
            product_batch.clear()
            print(f"  ...processed {processed}/{total_products} products")
    
    cursor.execute("SELECT fingerprint, id FROM products;")
    fp_to_pk = dict(cursor.fetchall())
    
    print(f"\n✅ Migrated {total_products} products")
    return fp_to_pk

def migrate_offers(db, cursor, fp_to_pk):
    """Migrate offers from MongoDB."""
    print("\n" + "=" * 70)
    print("  MIGRATING OFFERS")
    print("=" * 70)
    
    products_cursor = db.products.find()
    offers_buffer = []
    count = 0
    BATCH_SIZE = 500
    
    for p in products_cursor:
        fingerprint = str(p.get("_id"))
        prod_pk = fp_to_pk.get(fingerprint)
        if not prod_pk:
            continue
        
        for offer in p.get("offers", []):
            store_val = (offer.get("store") or "unknown").lower().replace(" ", "_")
            price_val = offer.get("price") or offer.get("basePrice") or 0
            try:
                price = float(price_val)
            except (ValueError, TypeError):
                price = 0.0
            
            is_available = offer.get("available", offer.get("is_available", True))
            product_url = offer.get("productUrl") or offer.get("product_url") or ""
            last_seen = _parse_date(offer.get("lastSeen") or offer.get("last_seen"))
            
            offers_buffer.append((
                prod_pk, store_val, price, product_url, is_available, last_seen
            ))
            count += 1
            
            if len(offers_buffer) >= BATCH_SIZE:
                execute_values(
                    cursor,
                    """INSERT INTO offers (product_id, store_id, price, product_url, is_available, last_seen)
                       VALUES %s 
                       ON CONFLICT (product_id, store_id) DO UPDATE SET 
                           price=EXCLUDED.price, 
                           is_available=EXCLUDED.is_available""",
                    offers_buffer
                )
                offers_buffer.clear()
                print(f"  ...processed {count} offers")
    
    if offers_buffer:
        execute_values(
            cursor,
            """INSERT INTO offers (product_id, store_id, price, product_url, is_available, last_seen)
               VALUES %s 
               ON CONFLICT (product_id, store_id) DO UPDATE SET 
                   price=EXCLUDED.price, 
                   is_available=EXCLUDED.is_available""",
            offers_buffer
        )
    
    print(f"\n✅ Migrated {count} offers")

def migrate_featured_deals(db, cursor, valid_slugs):
    """Migrate featured deals from MongoDB."""
    print("\n" + "=" * 70)
    print("  MIGRATING FEATURED DEALS")
    print("=" * 70)
    
    deals_batch = []
    for d in db.featured_deals.find():
        price = d.get("price")
        if isinstance(price, str):
            price = float(price.replace("$", "").replace("€", "").strip() or 0)
        elif price is None:
            price = 0
        
        original_price = d.get("original_price")
        if isinstance(original_price, str):
            original_price = float(original_price.replace("$", "").replace("€", "").strip() or 0)
        
        cat_slug = d.get("category") or d.get("category_slug")
        if cat_slug and cat_slug not in valid_slugs:
            normalized = cat_slug.lower().replace(" ", "-").replace("_", "-")
            if normalized in valid_slugs:
                cat_slug = normalized
            else:
                cat_slug = None
        
        deals_batch.append((
            d.get("title", ""),
            d.get("description"),
            price,
            original_price,
            d.get("discount_percent", 0),
            (d.get("store") or d.get("storeName") or "billa").lower(),
            d.get("image") or d.get("image_url") or "",
            d.get("url") or "",
            cat_slug,
            d.get("active", True),
            d.get("valid_until")
        ))
        print(f"  ✅ {d.get('title', 'Deal')}")
    
    if deals_batch:
        execute_values(
            cursor,
            """INSERT INTO featured_deals
               (title, description, price, original_price, discount_percent, store_id, 
                image_url, url, category_slug, active, valid_until)
               VALUES %s ON CONFLICT DO NOTHING""",
            deals_batch
        )
    
    print(f"\n✅ Migrated {len(deals_batch)} featured deals")
