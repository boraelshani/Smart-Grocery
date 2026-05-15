"""
List all categories from MongoDB to see what's available for recovery.
This is a read-only script that shows what categories exist in MongoDB.
"""
import os
import sys
import certifi
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017/smart_grocery")

if not MONGO_URI:
    print("❌ Error: MONGO_URI is not set in the .env file.")
    sys.exit(1)


def list_categories():
    print("=" * 60)
    print("  MONGODB CATEGORIES LISTING")
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
        print("\nTroubleshooting:")
        print("  1. Check if MONGO_URI is correct in .env file")
        print("  2. Ensure MongoDB server is running")
        print("  3. Check network connectivity")
        sys.exit(1)

    # Fetch categories from MongoDB
    print("\n📥 Fetching categories from MongoDB...")
    try:
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
            
            print(f"\n✅ Found {len(categories_set)} unique categories in products:")
            print("\n" + "=" * 60)
            for i, cat in enumerate(sorted(categories_set), 1):
                print(f"  {i:3d}. {cat}")
            print("=" * 60)
        else:
            print(f"\n✅ Found {len(mongo_categories)} categories in MongoDB")
            
            # Group by level
            by_level = {}
            for c in mongo_categories:
                level = c.get("level", 1)
                if level not in by_level:
                    by_level[level] = []
                by_level[level].append(c)
            
            # Display categories grouped by level
            print("\n" + "=" * 60)
            print("  CATEGORIES BY LEVEL")
            print("=" * 60)
            
            for level in sorted(by_level.keys()):
                cats = by_level[level]
                print(f"\n📁 Level {level} ({len(cats)} categories):")
                print("-" * 60)
                
                for c in sorted(cats, key=lambda x: x.get("name_en", x.get("name", ""))):
                    slug = c.get("slug", "")
                    name_en = c.get("name_en", c.get("name", ""))
                    name_de = c.get("name_de", "")
                    image_url = c.get("image_url", c.get("imageUrl", ""))
                    icon = c.get("icon", "")
                    parent_id = c.get("parent_id", c.get("parentId"))
                    
                    # Build display string
                    display = f"  • {name_en}"
                    if name_de and name_de != name_en:
                        display += f" / {name_de}"
                    display += f" ({slug})"
                    
                    # Add indicators
                    indicators = []
                    if image_url:
                        indicators.append("🖼️")
                    if icon:
                        indicators.append(f"icon:{icon}")
                    if parent_id:
                        indicators.append(f"parent:{parent_id}")
                    
                    if indicators:
                        display += f" [{', '.join(indicators)}]"
                    
                    print(display)
            
            print("\n" + "=" * 60)
            print(f"  TOTAL: {len(mongo_categories)} categories")
            print("=" * 60)
            
            # Show statistics
            print("\n📊 Statistics:")
            print(f"  • Total categories: {len(mongo_categories)}")
            print(f"  • Levels: {', '.join(map(str, sorted(by_level.keys())))}")
            
            with_images = sum(1 for c in mongo_categories if c.get("image_url") or c.get("imageUrl"))
            with_icons = sum(1 for c in mongo_categories if c.get("icon"))
            with_parents = sum(1 for c in mongo_categories if c.get("parent_id") or c.get("parentId"))
            
            print(f"  • With images: {with_images}")
            print(f"  • With icons: {with_icons}")
            print(f"  • With parent: {with_parents}")
            
    except Exception as e:
        print(f"❌ Error fetching categories: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        mongo_client.close()

    print("\n💡 To recover these categories to PostgreSQL, run:")
    print("   python scripts/recover_categories_from_mongo.py")
    print()


if __name__ == "__main__":
    try:
        list_categories()
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
