"""
Initialize PostgreSQL schema to match the SQLAlchemy models in postgres_models.py.
Run this once to create all tables if they don't already exist.
"""
import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()

DATABASE_URI = os.getenv("DATABASE_URL") or os.getenv("SQLALCHEMY_DATABASE_URI")

if not DATABASE_URI:
    print("Error: DATABASE_URL or SQLALCHEMY_DATABASE_URI is not set in the .env file.")
    exit(1)


def init_schema():
    print("Connecting to PostgreSQL...")
    try:
        conn = psycopg2.connect(DATABASE_URI)
        conn.autocommit = True
        cursor = conn.cursor()

        schema_sql = """
        -- 1. stores
        CREATE TABLE IF NOT EXISTS stores (
            id SERIAL PRIMARY KEY,
            store_id TEXT UNIQUE,
            name TEXT,
            website TEXT,
            logo_url TEXT,
            country TEXT DEFAULT 'AT',
            api_available BOOLEAN DEFAULT false,
            scraping_required BOOLEAN DEFAULT true,
            active BOOLEAN DEFAULT true
        );

        -- 2. categories
        CREATE TABLE IF NOT EXISTS categories (
            id SERIAL PRIMARY KEY,
            slug TEXT,
            name_en TEXT,
            name_de TEXT,
            parent_id INT REFERENCES categories(id) ON DELETE SET NULL,
            level INT,
            icon TEXT,
            image_url TEXT
        );

        -- 3. products
        CREATE TABLE IF NOT EXISTS products (
            id SERIAL PRIMARY KEY,
            fingerprint TEXT UNIQUE,
            name_de TEXT,
            brand TEXT,
            category_id INT REFERENCES categories(id) ON DELETE SET NULL,
            unit_normalized TEXT,
            size_normalized NUMERIC,
            default_image_url TEXT,
            barcode TEXT,
            created_at TIMESTAMP,
            updated_at TIMESTAMP
        );

        -- 4. offers
        CREATE TABLE IF NOT EXISTS offers (
            id SERIAL PRIMARY KEY,
            product_id INT NOT NULL REFERENCES products(id) ON DELETE CASCADE,
            store_id TEXT,
            price NUMERIC(10,2),
            product_url TEXT,
            is_available BOOLEAN DEFAULT true,
            last_seen TIMESTAMP,
            created_at TIMESTAMP,
            updated_at TIMESTAMP
        );
        CREATE UNIQUE INDEX IF NOT EXISTS uq_offers_product_store ON offers(product_id, store_id);

        -- 5. price_history
        CREATE TABLE IF NOT EXISTS price_history (
            id SERIAL PRIMARY KEY,
            offer_id INT REFERENCES offers(id) ON DELETE CASCADE,
            old_price NUMERIC,
            new_price NUMERIC,
            changed_at TIMESTAMP,
            source TEXT
        );

        -- 6. users
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            user_id TEXT UNIQUE,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT,
            name TEXT,
            avatar TEXT,
            language TEXT DEFAULT 'en',
            is_admin BOOLEAN DEFAULT false,
            created_at TIMESTAMP,
            updated_at TIMESTAMP
        );

        -- 7. shopping_lists
        CREATE TABLE IF NOT EXISTS shopping_lists (
            id SERIAL PRIMARY KEY,
            list_id TEXT UNIQUE,
            user_id INT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            name TEXT DEFAULT 'My List',
            share_code TEXT,
            shared BOOLEAN DEFAULT false,
            created_at TIMESTAMP,
            updated_at TIMESTAMP
        );

        -- 8. list_items
        CREATE TABLE IF NOT EXISTS list_items (
            id SERIAL PRIMARY KEY,
            list_id INT NOT NULL REFERENCES shopping_lists(id) ON DELETE CASCADE,
            product_id INT,
            product_name TEXT,
            quantity NUMERIC DEFAULT 1,
            checked BOOLEAN DEFAULT false,
            is_new BOOLEAN DEFAULT true,
            added_at TIMESTAMP
        );

        -- 9. featured_deals
        CREATE TABLE IF NOT EXISTS featured_deals (
            id SERIAL PRIMARY KEY,
            title TEXT,
            description TEXT,
            price NUMERIC,
            original_price NUMERIC,
            discount_percent INT,
            store_id TEXT,
            image_url TEXT,
            url TEXT,
            category_slug TEXT,
            active BOOLEAN DEFAULT true,
            valid_until DATE
        );

        -- 10. notifications
        CREATE TABLE IF NOT EXISTS notifications (
            id SERIAL PRIMARY KEY,
            user_email TEXT,
            type TEXT,
            title TEXT,
            message TEXT,
            action_url TEXT,
            priority TEXT DEFAULT 'normal',
            read BOOLEAN DEFAULT false,
            product_id TEXT,
            deal_id TEXT,
            store_name TEXT,
            is_toasted BOOLEAN DEFAULT false,
            created_at TIMESTAMP
        );

        -- 11. favorites
        CREATE TABLE IF NOT EXISTS favorites (
            id SERIAL PRIMARY KEY,
            user_email TEXT,
            product_id TEXT,
            product_name TEXT,
            product_image TEXT,
            category TEXT,
            best_price NUMERIC,
            store TEXT,
            discount_tiers JSONB,
            offer TEXT,
            added_at TIMESTAMP
        );

        -- 12. feedback
        CREATE TABLE IF NOT EXISTS feedback (
            id SERIAL PRIMARY KEY,
            feedback_id TEXT UNIQUE,
            user_email TEXT,
            type TEXT,
            subject TEXT,
            message TEXT,
            status TEXT DEFAULT 'pending',
            created_at TIMESTAMP,
            updated_at TIMESTAMP
        );

        -- 13. price_feedback
        CREATE TABLE IF NOT EXISTS price_feedback (
            id SERIAL PRIMARY KEY,
            product_id TEXT,
            store TEXT,
            user_email TEXT,
            is_correct BOOLEAN,
            reported_price NUMERIC,
            timestamp TIMESTAMP
        );

        -- 14. saved_recipes
        CREATE TABLE IF NOT EXISTS saved_recipes (
            id SERIAL PRIMARY KEY,
            user_email TEXT,
            title TEXT,
            ingredients JSONB,
            instructions JSONB,
            total_items INT DEFAULT 0,
            matched_items INT DEFAULT 0,
            total_price NUMERIC DEFAULT 0,
            created_at TIMESTAMP
        );

        -- 15. community_price_reports
        CREATE TABLE IF NOT EXISTS community_price_reports (
            id SERIAL PRIMARY KEY,
            product_id TEXT,
            store_name TEXT,
            observed_price NUMERIC,
            created_at TIMESTAMP
        );

        -- 16. pending_products
        CREATE TABLE IF NOT EXISTS pending_products (
            id SERIAL PRIMARY KEY,
            barcode TEXT UNIQUE,
            name TEXT,
            image TEXT,
            status TEXT DEFAULT 'pending',
            submitted_by TEXT,
            created_at TIMESTAMP
        );

        -- 17. public_lists
        CREATE TABLE IF NOT EXISTS public_lists (
            id SERIAL PRIMARY KEY,
            list_id TEXT UNIQUE,
            name TEXT,
            items JSONB,
            created_at TIMESTAMP
        );

        -- 18. brands
        CREATE TABLE IF NOT EXISTS brands (
            id SERIAL PRIMARY KEY,
            brand_id TEXT UNIQUE,
            name TEXT,
            name_en TEXT,
            name_de TEXT,
            image_url TEXT,
            website TEXT,
            created_at TIMESTAMP,
            updated_at TIMESTAMP
        );

        -- Standard indexes
        CREATE INDEX IF NOT EXISTS idx_products_fingerprint ON products(fingerprint);
        CREATE INDEX IF NOT EXISTS idx_products_category_id ON products(category_id);
        CREATE INDEX IF NOT EXISTS idx_offers_product_id ON offers(product_id);
        CREATE INDEX IF NOT EXISTS idx_offers_store_id ON offers(store_id);
        CREATE INDEX IF NOT EXISTS idx_price_history_offer_id ON price_history(offer_id);
        CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
        CREATE INDEX IF NOT EXISTS idx_shopping_lists_user_id ON shopping_lists(user_id);
        CREATE INDEX IF NOT EXISTS idx_list_items_list_id ON list_items(list_id);
        CREATE INDEX IF NOT EXISTS idx_notifications_user_email ON notifications(user_email);
        CREATE INDEX IF NOT EXISTS idx_notifications_read ON notifications(read);
        CREATE INDEX IF NOT EXISTS idx_favorites_user_email ON favorites(user_email);
        CREATE INDEX IF NOT EXISTS idx_saved_recipes_user_email ON saved_recipes(user_email);
        CREATE INDEX IF NOT EXISTS idx_categories_parent_id ON categories(parent_id);
        CREATE INDEX IF NOT EXISTS idx_categories_slug ON categories(slug);
        """

        print("Executing schema script...")
        cursor.execute(schema_sql)
        print("Schema successfully initialized on PostgreSQL!")

        cursor.close()
        conn.close()

    except Exception as e:
        print(f"Error initializing schema: {e}")

if __name__ == '__main__':
    init_schema()
