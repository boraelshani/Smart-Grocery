import os
import psycopg2
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

DATABASE_URI = os.getenv("SQLALCHEMY_DATABASE_URI")

if not DATABASE_URI:
    print("Error: SQLALCHEMY_DATABASE_URI is not set in the .env file.")
    exit(1)

# Ensure psycopg2 can handle the postgresql:// scheme properly if needed,
# though psycopg2 connects fine with the standard URI.
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
            api_available BOOLEAN,
            scraping_required BOOLEAN,
            active BOOLEAN DEFAULT true
        );

        -- 2. categories
        CREATE TABLE IF NOT EXISTS categories (
            id SERIAL PRIMARY KEY,
            slug TEXT UNIQUE,
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
            name_de TEXT NOT NULL,
            brand TEXT,
            category_id INT REFERENCES categories(id) ON DELETE SET NULL,
            unit_normalized TEXT,
            size_normalized NUMERIC,
            default_image_url TEXT,
            barcode TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        -- 4. offers
        CREATE TABLE IF NOT EXISTS offers (
            id SERIAL PRIMARY KEY,
            product_id INT REFERENCES products(id) ON DELETE CASCADE,
            store_id TEXT REFERENCES stores(store_id) ON DELETE CASCADE,
            price NUMERIC(10,2),
            product_url TEXT,
            is_available BOOLEAN DEFAULT true,
            last_seen TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(product_id, store_id)
        );

        -- 5. price_history
        CREATE TABLE IF NOT EXISTS price_history (
            id SERIAL PRIMARY KEY,
            offer_id INT REFERENCES offers(id) ON DELETE CASCADE,
            price NUMERIC(10,2),
            recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        -- 6. promotions
        CREATE TABLE IF NOT EXISTS promotions (
            id SERIAL PRIMARY KEY,
            offer_id INT REFERENCES offers(id) ON DELETE CASCADE,
            type TEXT,
            value TEXT,
            start_date DATE,
            end_date DATE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        -- 7. users
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            user_id TEXT UNIQUE,
            email TEXT UNIQUE,
            password_hash TEXT,
            name TEXT,
            avatar TEXT,
            language TEXT DEFAULT 'de',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        -- 8. shopping_lists
        CREATE TABLE IF NOT EXISTS shopping_lists (
            id SERIAL PRIMARY KEY,
            list_id TEXT UNIQUE,
            user_id INT REFERENCES users(id) ON DELETE CASCADE,
            name TEXT,
            share_code TEXT UNIQUE,
            shared BOOLEAN DEFAULT false,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        -- 9. list_items
        CREATE TABLE IF NOT EXISTS list_items (
            id SERIAL PRIMARY KEY,
            list_id INT REFERENCES shopping_lists(id) ON DELETE CASCADE,
            product_id INT REFERENCES products(id) ON DELETE SET NULL,
            product_name TEXT,
            quantity NUMERIC DEFAULT 1,
            checked BOOLEAN DEFAULT false,
            added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        -- 10. recipes
        CREATE TABLE IF NOT EXISTS recipes (
            id SERIAL PRIMARY KEY,
            user_id INT REFERENCES users(id) ON DELETE CASCADE,
            title TEXT,
            instructions TEXT,
            image_url TEXT,
            is_public BOOLEAN DEFAULT false,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        -- 11. recipe_ingredients
        CREATE TABLE IF NOT EXISTS recipe_ingredients (
            id SERIAL PRIMARY KEY,
            recipe_id INT REFERENCES recipes(id) ON DELETE CASCADE,
            product_fingerprint TEXT,
            ingredient_name TEXT,
            quantity NUMERIC,
            unit TEXT
        );

        -- 12. favorites
        CREATE TABLE IF NOT EXISTS favorites (
            id SERIAL PRIMARY KEY,
            user_id INT REFERENCES users(id) ON DELETE CASCADE,
            product_id INT REFERENCES products(id) ON DELETE CASCADE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_id, product_id)
        );

        -- 13. featured_deals
        CREATE TABLE IF NOT EXISTS featured_deals (
            id SERIAL PRIMARY KEY,
            title TEXT,
            description TEXT,
            price NUMERIC,
            original_price NUMERIC,
            discount_percent INT,
            store_id TEXT REFERENCES stores(store_id) ON DELETE CASCADE,
            image_url TEXT,
            url TEXT,
            category_slug TEXT REFERENCES categories(slug) ON DELETE SET NULL,
            active BOOLEAN DEFAULT true,
            valid_until DATE
        );

        -- 14. community_price_reports
        CREATE TABLE IF NOT EXISTS community_price_reports (
            id SERIAL PRIMARY KEY,
            product_id INT REFERENCES products(id) ON DELETE CASCADE,
            store_name TEXT,
            observed_price NUMERIC,
            note TEXT,
            reporter_type TEXT,
            reporter_id INT REFERENCES users(id) ON DELETE SET NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        -- 15. scraper_runs
        CREATE TABLE IF NOT EXISTS scraper_runs (
            id SERIAL PRIMARY KEY,
            run_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            products_processed INT,
            offers_updated INT,
            status TEXT,
            error_message TEXT
        );

        -- Create standard indexes
        CREATE INDEX IF NOT EXISTS idx_products_fingerprint ON products(fingerprint);
        CREATE INDEX IF NOT EXISTS idx_offers_product_store ON offers(product_id, store_id);
        CREATE INDEX IF NOT EXISTS idx_price_history_offer ON price_history(offer_id);
        CREATE INDEX IF NOT EXISTS idx_promotions_offer ON promotions(offer_id);
        CREATE INDEX IF NOT EXISTS idx_list_items_list ON list_items(list_id);
        """
        
        print("Executing schema script...")
        cursor.execute(schema_sql)
        print("✅ Schema successfully initialized on PostgreSQL!")

        cursor.close()
        conn.close()

    except Exception as e:
        print(f"❌ Error initializing schema: {e}")

if __name__ == '__main__':
    init_schema()
