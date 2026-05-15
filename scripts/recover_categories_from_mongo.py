"""
Recover deleted categories from MongoDB and insert them into PostgreSQL.
This script fetches all categories from MongoDB and inserts/updates them in PostgreSQL,
excluding the 'icon' field as requested.
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
    print("❌ Error: DATABASE_URL or SQLALCHEMY_DATABASE_URI is not set in the .env file.")
    sys.exit(1)


def recover_categories():
    print("=" * 60)
    print("  CATEGORY RECOVERY FROM MONGODB TO POSTGRESQL")
    print("=" * 60)
    
    # Connect to MongoDB
    print("\n📡 Connecting to MongoDB...")
    try:
        mongo_client = MongoClient(MONGO_URI, tlsCAFile=certifi.where())
        db = mongo_client["smart_grocery"]
        # Test connection
        mongo_client.server_info()
        print("✅ MongoDB connection successful")
    except Exception as e:
        print(f"❌ MongoDB connection failed: {e}")
        sys.exit(1)

    # Connect to PostgreSQL
    print("\n📡 Connecting to PostgreSQL...")
    try:
        conn = psycopg2.connect(PG_URI)
        conn.autocommit = True
        cursor = conn.cursor()
        print("✅ PostgreSQL connection successful")
    except Exception as e:
        print(f"❌ PostgreSQL connection failed: {e}")
        sys.exit(1)

    # Fetch categories from MongoDB
    print("\n📥 Fetching categories from MongoDB...")
    mongo_categories = list(db.categories.find({}))
    
    if not mongo_categories:
        print("⚠️  No categories found in MongoDB categories collection")
        print("   Trying to extract from products...")
        
        # Fallback: extract unique categories from products
        categories_set = set()
        for p in db.products.find({}, {"category": 1}):
            if p.get("category"):
                categories_set.add(str(p.get("category")).strip())
        
        if not categories_set:
            print("❌ No categories found in products either")
            sys.exit(1)
        
        # Convert to category format
        mongo_categories = [
            {
                "name": cat,
                "name_en": cat,
                "name_de": cat,
                "slug": cat.lower().replace(" ", "-").replace("_", "-"),
                "level": 1
            }
            for cat in categories_set
        ]
        print(f"✅ Extracted {len(mongo_categories)} categories from products")
    else:
        print(f"✅ Found {len(mongo_categories)} categories in MongoDB")

    # Prepare categories for PostgreSQL (excluding icon field)
    print("\n🔄 Processing categories...")
    categories_to_insert = []
    
    for c in mongo_categories:
        # Generate slug
        slug = (c.get("slug") or 
                c.get("name_en") or 
                c.get("name_de") or 
                c.get("name") or 
                "unknown").lower().replace(" ", "-").replace("_", "-")
        
        # Get names
        name_en = c.get("name_en") or c.get("name") or slug
        name_de = c.get("name_de") or c.get("name") or slug
        
        # Get parent_id (set to None if not valid integer)
        parent_id = c.get("parent_id") or c.get("parentId")
        if parent_id and not isinstance(parent_id, int):
            parent_id = None
        
        # Get level
        level = c.get("level") or 1
        
        # Get image_url
        image_url = c.get("image_url") or c.get("imageUrl") or ""
        
        # NOTE: We're excluding the 'icon' field as requested
        
        categories_to_insert.append((
            slug,
            name_en,
            name_de,
            parent_id,
            level,
            image_url
        ))
        
        print(f"  • {name_en} ({slug})")

    # Deduplicate by slug - keep the one with the most data
    print("\n🔍 Deduplicating categories...")
    seen = {}
    for item in categories_to_insert:
        slug = item[0]
        # Keep if new, or if has more data (name_en or image_url)
        if slug not in seen or (item[1] and not seen[slug][1]) or (item[5] and not seen[slug][5]):
            seen[slug] = item
    
    categories_to_insert = list(seen.values())
    print(f"✅ Deduplicated to {len(categories_to_insert)} unique categories")

    # Check current categories in PostgreSQL
    print("\n📊 Checking current PostgreSQL categories...")
    cursor.execute("SELECT COUNT(*) FROM categories;")
    current_count = cursor.fetchone()[0]
    print(f"   Current categories in PostgreSQL: {current_count}")

    # Insert/Update categories in PostgreSQL
    print("\n💾 Inserting/Updating categories in PostgreSQL...")
    if categories_to_insert:
        try:
            execute_values(
                cursor,
                """INSERT INTO categories (slug, name_en, name_de, parent_id, level, image_url) 
                   VALUES %s 
                   ON CONFLICT (slug) DO UPDATE SET 
                       name_en = EXCLUDED.name_en,
                       name_de = EXCLUDED.name_de,
                       parent_id = COALESCE(EXCLUDED.parent_id, categories.parent_id),
                       level = EXCLUDED.level,
                       image_url = COALESCE(EXCLUDED.image_url, categories.image_url)""",
                categories_to_insert
            )
            print("✅ Categories inserted/updated successfully")
        except Exception as e:
            print(f"❌ Error inserting categories: {e}")
            conn.rollback()
            sys.exit(1)

    # Verify the result
    print("\n✅ Verifying results...")
    cursor.execute("SELECT COUNT(*) FROM categories;")
    new_count = cursor.fetchone()[0]
    print(f"   Categories in PostgreSQL after recovery: {new_count}")
    print(f"   Categories added/updated: {new_count - current_count}")

    # Show sample of recovered categories
    print("\n📋 Sample of categories in PostgreSQL:")
    cursor.execute("SELECT slug, name_en, level, image_url FROM categories ORDER BY level, name_en LIMIT 10;")
    for row in cursor.fetchall():
        slug, name_en, level, image_url = row
        has_image = "🖼️" if image_url else "  "
        print(f"   {has_image} Level {level}: {name_en} ({slug})")

    # Close connections
    cursor.close()
    conn.close()
    mongo_client.close()

    print("\n" + "=" * 60)
    print("  ✅ CATEGORY RECOVERY COMPLETE!")
    print("=" * 60)
    print(f"\n  Total categories in PostgreSQL: {new_count}")
    print(f"  Categories recovered: {new_count - current_count}")
    print("\n  Note: The 'icon' field was excluded as requested.")
    print("=" * 60)


if __name__ == "__main__":
    try:
        recover_categories()
    except KeyboardInterrupt:
        print("\n\n⚠️  Recovery interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
