"""
Migrate data from MongoDB to PostgreSQL (Neon).
Handles: stores, categories, products, offers, price_history, users, shopping_lists, featured_deals.
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
    print("Error: DATABASE_URL or SQLALCHEMY_DATABASE_URI is not set in the .env file.")
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


def migrate():
    print("Connecting to MongoDB...")
    mongo_client = MongoClient(MONGO_URI, tlsCAFile=certifi.where())
    db = mongo_client["smart_grocery"]

    print("Connecting to PostgreSQL...")
    conn = psycopg2.connect(PG_URI)
    conn.autocommit = True
    cursor = conn.cursor()

    # ── 1. Migrate Stores ──────────────────────────────────────────
    print("Migrating Stores...")
    mongo_stores = list(db.stores.find())
    product_stores = set()
    for p in db.products.find({}, {"offers.store": 1}):
        for offer in p.get("offers", []):
            if offer.get("store"):
                product_stores.add(offer.get("store").lower())

    stores_to_insert = []
    for s in mongo_stores:
        store_id = s.get("name", "unknown").lower().replace(" ", "_")
        product_stores.discard(store_id)
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

    for s in product_stores:
        stores_to_insert.append((s, s.capitalize(), None, None, "AT", True, False, True))

    if stores_to_insert:
        execute_values(
            cursor,
            "INSERT INTO stores (store_id, name, website, logo_url, country, api_available, scraping_required, active) VALUES %s ON CONFLICT (store_id) DO NOTHING",
            stores_to_insert
        )

    cursor.execute("SELECT store_id, id FROM stores;")
    store_id_to_pk = dict(cursor.fetchall())

    # ── 2. Migrate Categories (from MongoDB categories collection) ──
    print("Migrating Categories...")
    categories_to_insert = []
    cat_slug_to_pk = {}

    # First try to get categories from the dedicated categories collection
    mongo_categories = list(db.categories.find({}))
    if mongo_categories:
        print(f"  Found {len(mongo_categories)} categories in MongoDB categories collection")
        for c in mongo_categories:
            slug = (c.get("slug") or c.get("name_en") or c.get("name_de") or c.get("name") or "unknown").lower().replace(" ", "-").replace("_", "-")
            name_en = c.get("name_en") or c.get("name") or ""
            name_de = c.get("name_de") or c.get("name") or ""
            parent_id = c.get("parent_id") or c.get("parentId")
            # Try to resolve parent_id to the actual PK if it's a slug or categoryId
            if parent_id and not isinstance(parent_id, int):
                parent_id = None  # Will be resolved after initial insert
            level = c.get("level") or 1
            icon = c.get("icon") or ""
            image_url = c.get("image_url") or c.get("imageUrl") or ""

            categories_to_insert.append((
                slug, name_en, name_de, parent_id, level, icon, image_url
            ))

        # Deduplicate by slug - keep the one with the most data
        seen = {}
        for item in categories_to_insert:
            s = item[0]
            if s not in seen or (item[1] and not seen[s][1]) or (item[6] and not seen[s][6]):
                seen[s] = item
        categories_to_insert = list(seen.values())
        print(f"  Deduplicated to {len(categories_to_insert)} unique categories")
    else:
        print("  No categories collection found, extracting from products...")
        # Fallback: extract unique categories from products
        categories = set()
        for p in db.products.find({}, {"category": 1}):
            if p.get("category"):
                categories.add(str(p.get("category")).strip())

        categories_to_insert = [
            (c.lower().replace(" ", "-"), c, c, None, 1, None, None)
            for c in categories if c
        ]

    if categories_to_insert:
        execute_values(
            cursor,
            "INSERT INTO categories (slug, name_en, name_de, parent_id, level, icon, image_url) VALUES %s ON CONFLICT (slug) DO UPDATE SET name_en=EXCLUDED.name_en, name_de=EXCLUDED.name_de, image_url=COALESCE(EXCLUDED.image_url, categories.image_url)",
            categories_to_insert
        )

    cursor.execute("SELECT slug, id FROM categories;")
    cat_slug_to_pk = dict(cursor.fetchall())

    # Also build a mapping from old MongoDB categoryId to new PK
    cat_name_to_pk = {}
    cursor.execute("SELECT name_en, id FROM categories;")
    for row in cursor.fetchall():
        if row[0]:
            cat_name_to_pk[row[0].lower()] = row[1]

    # ── 3. Migrate Products, Offers, and Price History ──────────────
    print("Migrating Products, Offers, and Price History...")
    products_cursor = db.products.find()
    total_products = db.products.count_documents({})

    BATCH_SIZE = 500
    product_batch = []
    processed = 0

    for p in products_cursor:
        fingerprint = str(p.get("_id"))
        name_de = p.get("name", "Unknown Product")
        brand = p.get("brand") or p.get("brandId")

        # Resolve category
        cat_str = None
        cat_ref = p.get("category") or p.get("categoryId")
        if cat_ref:
            if isinstance(cat_ref, str):
                cat_str = cat_ref.strip().lower().replace(" ", "-")
            elif isinstance(cat_ref, dict):
                cat_str = cat_ref.get("slug", "").lower()
        if not cat_str and p.get("categoryPath"):
            path = p.get("categoryPath")
            if isinstance(path, list) and path:
                cat_str = str(path[-1]).lower().replace(" ", "-")

        category_id = cat_slug_to_pk.get(cat_str)
        if not category_id and cat_ref:
            # Try by name
            category_id = cat_name_to_pk.get(str(cat_ref).lower())

        unit = str(p.get("unit") or p.get("unit_normalized") or p.get("unitSize") or "")
        size = p.get("quantity") or p.get("size_normalized") or p.get("unitSize") or 0
        try:
            size_num = float(size) if not isinstance(size, str) else float(size.replace(",", "."))
        except (ValueError, TypeError):
            size_num = None

        default_image_url = p.get("default_image_url") or p.get("defaultImageUrl") or p.get("image") or p.get("image_url")
        barcode = p.get("barcode") or p.get("ean") or p.get("gtin")

        created_at = _parse_date(p.get("created_at") or p.get("createdAt"))
        updated_at = _parse_date(p.get("updated_at") or p.get("updatedAt") or p.get("created_at") or p.get("createdAt"))

        product_batch.append((
            fingerprint, name_de, brand, category_id, unit, size_num,
            default_image_url, barcode, created_at, updated_at
        ))
        processed += 1

        if len(product_batch) >= BATCH_SIZE or processed == total_products:
            execute_values(
                cursor,
                """INSERT INTO products
                   (fingerprint, name_de, brand, category_id, unit_normalized, size_normalized, default_image_url, barcode, created_at, updated_at)
                   VALUES %s ON CONFLICT (fingerprint) DO UPDATE SET name_de=EXCLUDED.name_de, brand=COALESCE(EXCLUDED.brand, products.brand), category_id=COALESCE(EXCLUDED.category_id, products.category_id), default_image_url=COALESCE(EXCLUDED.default_image_url, products.default_image_url), updated_at=EXCLUDED.updated_at RETURNING fingerprint, id""",
                product_batch
            )
            product_batch.clear()
            print(f"  ...processed {processed}/{total_products} products")

    # Get product mapping
    print("Pulling Product mapping from PostgreSQL...")
    cursor.execute("SELECT fingerprint, id FROM products;")
    fp_to_pk = dict(cursor.fetchall())

    # ── 4. Migrate Offers ──────────────────────────────────────────
    print("Processing Offers...")
    offers_buffer = []
    count = 0
    products_cursor.rewind()

    for p in products_cursor:
        fingerprint = str(p.get("_id"))
        prod_pk = fp_to_pk.get(fingerprint)
        if not prod_pk:
            continue

        for offer in p.get("offers", []):
            store_val = offer.get("store", "unknown").lower().replace(" ", "_")
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
                       VALUES %s ON CONFLICT (product_id, store_id) DO UPDATE SET price=EXCLUDED.price, is_available=EXCLUDED.is_available""",
                    offers_buffer
                )
                offers_buffer.clear()
                print(f"  ...processed {count} offers")

    if offers_buffer:
        execute_values(
            cursor,
            """INSERT INTO offers (product_id, store_id, price, product_url, is_available, last_seen)
               VALUES %s ON CONFLICT (product_id, store_id) DO UPDATE SET price=EXCLUDED.price, is_available=EXCLUDED.is_available""",
            offers_buffer
        )

    # ── 5. Migrate Price History ───────────────────────────────────
    print("Pulling Offers mapping...")
    cursor.execute("SELECT product_id, store_id, id FROM offers;")
    offer_map = {(r[0], r[1]): r[2] for r in cursor.fetchall()}

    print("Migrating Price History...")
    products_cursor.rewind()
    history_buffer = []
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
                h_price = h.get("price") or h.get("new_price") or 0
                try:
                    hp = float(h_price)
                except (ValueError, TypeError):
                    hp = 0.0

                h_date = _parse_date(h.get("date") or h.get("changed_at") or h.get("recorded_at") or h.get("timestamp"))
                source = h.get("source", "")
                old_price = h.get("old_price")

                history_buffer.append((offer_pk, old_price, hp, h_date, source))
                hist_count += 1

                if len(history_buffer) >= BATCH_SIZE * 5:
                    execute_values(
                        cursor,
                        "INSERT INTO price_history (offer_id, old_price, new_price, changed_at, source) VALUES %s",
                        history_buffer
                    )
                    history_buffer.clear()
                    print(f"  ...processed {hist_count} history records")

    if history_buffer:
        execute_values(
            cursor,
            "INSERT INTO price_history (offer_id, old_price, new_price, changed_at, source) VALUES %s",
            history_buffer
        )

    # ── 6. Migrate Users ───────────────────────────────────────────
    print("Migrating Users...")
    mongo_users = list(db.users.find())
    users_batch = []
    for u in mongo_users:
        user_id_str = str(u.get("_id"))
        email = u.get("email")
        if not email:
            continue

        users_batch.append((
            user_id_str,
            email,
            u.get("password") or u.get("password_hash"),
            u.get("name"),
            u.get("avatar"),
            u.get("language", "en"),
            bool(u.get("is_admin", False)),
            _parse_date(u.get("created_at") or u.get("createdAt")),
            _parse_date(u.get("updated_at") or u.get("updatedAt")),
        ))

    if users_batch:
        execute_values(
            cursor,
            "INSERT INTO users (user_id, email, password_hash, name, avatar, language, is_admin, created_at, updated_at) VALUES %s ON CONFLICT (email) DO UPDATE SET name=COALESCE(EXCLUDED.name, users.name), is_admin=COALESCE(EXCLUDED.is_admin, users.is_admin)",
            users_batch
        )

    cursor.execute("SELECT user_id, id FROM users;")
    user_id_to_pk = dict(cursor.fetchall())

    # ── 7. Migrate Shopping Lists and Items ────────────────────────
    print("Migrating Shopping Lists...")
    list_batch = []
    item_batch = []

    for u in mongo_users:
        mongo_uid = str(u.get("_id"))
        pg_uid = user_id_to_pk.get(mongo_uid)
        if not pg_uid:
            continue

        s_lists = u.get("shopping_list", [])
        if s_lists:
            list_unique_id = f"list_{mongo_uid}"
            cursor.execute("""
                INSERT INTO shopping_lists (list_id, user_id, name, share_code, created_at, updated_at)
                VALUES (%s, %s, %s, %s, NOW(), NOW()) ON CONFLICT (list_id) DO UPDATE SET name=EXCLUDED.name RETURNING id
            """, (list_unique_id, pg_uid, "My Shopping List", f"share_{mongo_uid}"))
            list_pk = cursor.fetchone()[0]

            for item in s_lists:
                i_name = item.get("name", "Unknown item") if isinstance(item, dict) else str(item)
                i_id = item.get("id") if isinstance(item, dict) else None
                prod_fk = fp_to_pk.get(i_id) if i_id else None
                qty = item.get("qty") or item.get("quantity", 1) if isinstance(item, dict) else 1
                checked = bool(item.get("purchased") or item.get("checked")) if isinstance(item, dict) else False

                item_batch.append((list_pk, prod_fk, i_name, qty, checked, True))

    if item_batch:
        execute_values(
            cursor,
            "INSERT INTO list_items (list_id, product_id, product_name, quantity, checked, is_new) VALUES %s",
            item_batch
        )

    # ── 8. Migrate Featured Deals ──────────────────────────────────
    print("Migrating Featured Deals...")
    # Reload categories for slug validation
    cursor.execute("SELECT slug FROM categories;")
    valid_slugs = {row[0] for row in cursor.fetchall()}

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
        # Validate category slug exists, otherwise set to None
        if cat_slug and cat_slug not in valid_slugs:
            # Try to find a matching slug (case-insensitive, hyphenated)
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

    if deals_batch:
        execute_values(
            cursor,
            """INSERT INTO featured_deals
               (title, description, price, original_price, discount_percent, store_id, image_url, url, category_slug, active, valid_until)
               VALUES %s ON CONFLICT DO NOTHING""",
            deals_batch
        )

    # ── 9. Migrate Favorites ───────────────────────────────────────
    print("Migrating Favorites...")
    fav_batch = []
    for f in db.favorites.find():
        fav_batch.append((
            f.get("user_email"),
            f.get("product_id"),
            f.get("product_name"),
            f.get("product_image") or f.get("image"),
            f.get("category"),
            f.get("best_price") or f.get("price"),
            f.get("store"),
            _parse_date(f.get("added_at") or f.get("created_at")),
        ))

    if fav_batch:
        execute_values(
            cursor,
            "INSERT INTO favorites (user_email, product_id, product_name, product_image, category, best_price, store, added_at) VALUES %s ON CONFLICT DO NOTHING",
            fav_batch
        )

    # ── 10. Migrate Notifications ──────────────────────────────────
    print("Migrating Notifications...")
    notif_batch = []
    for n in db.notifications.find():
        notif_batch.append((
            n.get("user_email"),
            n.get("type"),
            n.get("title"),
            n.get("message"),
            n.get("action_url"),
            n.get("priority", "normal"),
            n.get("read", False),
            n.get("product_id"),
            n.get("deal_id"),
            n.get("store_name"),
            n.get("is_toasted", False),
            _parse_date(n.get("created_at")),
        ))

    if notif_batch:
        execute_values(
            cursor,
            "INSERT INTO notifications (user_email, type, title, message, action_url, priority, read, product_id, deal_id, store_name, is_toasted, created_at) VALUES %s ON CONFLICT DO NOTHING",
            notif_batch
        )

    # ── 11. Migrate Brands ─────────────────────────────────────────
    print("Migrating Brands...")
    brand_batch = []
    for b in db.brands.find():
        brand_batch.append((
            b.get("brand_id") or b.get("brandId") or str(b.get("_id")),
            b.get("name"),
            b.get("name_en"),
            b.get("name_de"),
            b.get("image_url") or b.get("imageUrl"),
            b.get("website"),
            _parse_date(b.get("created_at")),
            _parse_date(b.get("updated_at")),
        ))

    if brand_batch:
        execute_values(
            cursor,
            "INSERT INTO brands (brand_id, name, name_en, name_de, image_url, website, created_at, updated_at) VALUES %s ON CONFLICT (brand_id) DO NOTHING",
            brand_batch
        )

    # ── Summary ─────────────────────────────────────────────────────
    cursor.execute("SELECT COUNT(*) FROM stores;")
    store_count = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM categories;")
    cat_count = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM products;")
    prod_count = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM offers;")
    offer_count = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM users;")
    user_count = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM featured_deals;")
    deal_count = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM favorites;")
    fav_count = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM brands;")
    brand_count = cursor.fetchone()[0]

    print("\n" + "=" * 50)
    print(" MIGRATION COMPLETE!")
    print("=" * 50)
    print(f"  Stores:     {store_count}")
    print(f"  Categories: {cat_count}")
    print(f"  Products:   {prod_count}")
    print(f"  Offers:     {offer_count}")
    print(f"  Users:      {user_count}")
    print(f"  Deals:      {deal_count}")
    print(f"  Favorites:  {fav_count}")
    print(f"  Brands:     {brand_count}")
    print("=" * 50)

    cursor.close()
    conn.close()


if __name__ == "__main__":
    migrate()
