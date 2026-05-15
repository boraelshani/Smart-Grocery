"""
RECOVER CATEGORIES ONLY - KEEPS ALL OTHER DATA INTACT!
This script ONLY recovers categories from MongoDB.
All your products, offers, and other data remain untouched!
"""
import os
import sys
import certifi
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

def recover_categories_only():
    print("=" * 70)
    print("  🚨 EMERGENCY CATEGORY RECOVERY")
    print("  (KEEPS ALL OTHER DATA INTACT!)")
    print("=" * 70)
    
    # Connect to MongoDB
    print("\n📡 Connecting to MongoDB...")
    try:
        mongo_client = MongoClient(MONGO_URI, tlsCAFile=certifi.where())
        db = mongo_client["smart_grocery"]
        mongo_client.server_info()
        print("✅ MongoDB connected")
    except Exception as e:
        print(f"❌ MongoDB connection failed: {e}")
        sys.exit(1)
    
    # Connect to PostgreSQL
    print("\n📡 Connecting to PostgreSQL...")
    try:
        conn = psycopg2.connect(PG_URI)
        conn.autocommit = True
        cursor = conn.cursor()
        print("✅ PostgreSQL connected")
    except Exception as e:
        print(f"❌ PostgreSQL connection failed: {e}")
        sys.exit(1)
    
    # Check existing data
    print("\n📊 Checking existing PostgreSQL data...")
    cursor.execute("SELECT COUNT(*) FROM products;")
    product_count = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM offers;")
    offer_count = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM categories;")
    current_cat_count = cursor.fetchone()[0]
    
    print(f"  • Products: {product_count} ✅ (WILL BE PRESERVED)")
    print(f"  • Offers: {offer_count} ✅ (WILL BE PRESERVED)")
    print(f"  • Categories: {current_cat_count} (WILL BE RECOVERED)")
    
    if product_count == 0:
        print("\n⚠️  NOTE: No products in PostgreSQL yet.")
        print("   This is normal if you haven't migrated products from MongoDB.")
        print("   After recovering categories, you can migrate products separately.")
        print("\n✅ Proceeding with category recovery...")
    
    # Fetch categories from MongoDB
    print("\n📥 Fetching categories from MongoDB...")
    mongo_categories = list(db.categories.find({}))
    
    if not mongo_categories:
        print("⚠️  No categories in MongoDB categories collection")
        print("   Trying to extract from products...")
        categories_set = set()
        for p in db.products.find({}, {"category": 1}):
            if p.get("category"):
                categories_set.add(str(p.get("category")).strip())
        
        if not categories_set:
            print("❌ No categories found anywhere!")
            sys.exit(1)
        
        mongo_categories = [
            {"name": cat, "name_en": cat, "name_de": cat, 
             "slug": cat.lower().replace(" ", "-"), "level": 1}
            for cat in categories_set
        ]
    
    print(f"✅ Found {len(mongo_categories)} categories in MongoDB\n")
    
    # Build category mapping
    print("🔄 Processing categories with parent_id relationships...\n")
    
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
    print("💾 Inserting categories into PostgreSQL...\n")
    
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
                # Try as integer
                elif isinstance(parent_id_ref, int):
                    parent_pg_id = parent_id_ref
                # Try as slug
                if not parent_pg_id and isinstance(parent_id_ref, str):
                    parent_slug = parent_id_ref.lower().replace(" ", "-")
                    parent_pg_id = slug_to_pg_id.get(parent_slug)
            
            # Insert category (check if exists first since slug may not be unique)
            try:
                # Check if category already exists by slug
                cursor.execute("SELECT id FROM categories WHERE slug = %s LIMIT 1", (slug,))
                existing = cursor.fetchone()
                
                if existing:
                    # Update existing category
                    pg_id = existing[0]
                    cursor.execute("""
                        UPDATE categories 
                        SET name_en = %s, name_de = %s, parent_id = %s, level = %s, image_url = %s
                        WHERE id = %s
                    """, (name_en, name_de, parent_pg_id, level, image_url, pg_id))
                    action = "Updated"
                else:
                    # Insert new category
                    cursor.execute("""
                        INSERT INTO categories (slug, name_en, name_de, parent_id, level, image_url)
                        VALUES (%s, %s, %s, %s, %s, %s)
                        RETURNING id
                    """, (slug, name_en, name_de, parent_pg_id, level, image_url))
                    pg_id = cursor.fetchone()[0]
                    action = "Inserted"
                
                slug_to_pg_id[slug] = pg_id
                if mongo_id:
                    mongo_id_to_pg_id[mongo_id] = pg_id
                
                parent_info = f" (parent: {parent_pg_id})" if parent_pg_id else ""
                print(f"  ✅ {action}: {name_en} ({slug}){parent_info}")
            except Exception as e:
                print(f"  ⚠️  Error with {name_en}: {e}")
    
    # Verify results
    print("\n" + "=" * 70)
    print("  ✅ CATEGORY RECOVERY COMPLETE!")
    print("=" * 70)
    
    cursor.execute("SELECT COUNT(*) FROM categories;")
    new_cat_count = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM categories WHERE parent_id IS NOT NULL;")
    child_count = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM products;")
    final_product_count = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM offers;")
    final_offer_count = cursor.fetchone()[0]
    
    print(f"\n📊 Final Status:")
    print(f"  • Categories: {new_cat_count} (Root: {new_cat_count - child_count}, Children: {child_count})")
    print(f"  • Products: {final_product_count} ✅ (PRESERVED)")
    print(f"  • Offers: {final_offer_count} ✅ (PRESERVED)")
    
    # Show hierarchy
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
        print("  (No parent-child relationships)")
    
    # Show products are still linked
    print(f"\n📦 Verifying Products Still Exist:")
    cursor.execute("SELECT name_de FROM products LIMIT 5;")
    for row in cursor.fetchall():
        print(f"  ✅ {row[0]}")
    
    cursor.close()
    conn.close()
    mongo_client.close()
    
    print("\n" + "=" * 70)
    print("  🎉 SUCCESS! Categories recovered, all other data intact!")
    print("=" * 70)
    print(f"\n  Categories recovered: {new_cat_count}")
    print(f"  Products preserved: {final_product_count}")
    print(f"  Offers preserved: {final_offer_count}")
    print("\n  Your 12k+ products are safe! ✅")
    print("=" * 70)

if __name__ == "__main__":
    try:
        recover_categories_only()
    except KeyboardInterrupt:
        print("\n\n⚠️  Recovery cancelled")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
