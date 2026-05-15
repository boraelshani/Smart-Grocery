-- ============================================================================
-- Smart Grocery Database Restructuring Migration
-- ============================================================================
-- Purpose: Transform from denormalized to normalized schema
-- - Separate product data from store-specific data
-- - Create reusable discount rules
-- - Enable many-to-many relationships
-- - Improve query performance and data consistency
-- ============================================================================

-- ============================================================================
-- STEP 1: ADD NAME COLUMN TO PRODUCTS (IF MISSING)
-- ============================================================================
-- Why: Products need a global name independent of store
-- Benefit: One product name to maintain, not duplicated per store

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'products' AND column_name = 'name'
    ) THEN
        ALTER TABLE products ADD COLUMN name TEXT;
        -- Populate from name_de as default
        UPDATE products SET name = name_de WHERE name IS NULL;
        ALTER TABLE products ALTER COLUMN name SET NOT NULL;
        
        RAISE NOTICE 'Added name column to products table';
    ELSE
        RAISE NOTICE 'Name column already exists in products table';
    END IF;
END $$;

-- ============================================================================
-- STEP 2: CREATE BACKUP TABLES (SAFETY FIRST!)
-- ============================================================================
-- Why: Preserve original data in case we need to rollback
-- Benefit: Can restore if something goes wrong

CREATE TABLE IF NOT EXISTS _backup_products AS SELECT * FROM products;
CREATE TABLE IF NOT EXISTS _backup_offers AS SELECT * FROM offers;
CREATE TABLE IF NOT EXISTS _backup_promotions AS SELECT * FROM promotions;

RAISE NOTICE 'Created backup tables: _backup_products, _backup_offers, _backup_promotions';

-- ============================================================================
-- STEP 3: CREATE NEW product_store TABLE
-- ============================================================================
-- Why: Separate global product data from store-specific pricing/availability
-- Benefit: 
--   - One product record shared across all stores
--   - Easy to query "show all stores selling this product"
--   - No data duplication for product attributes
--   - Fast price comparisons across stores

CREATE TABLE IF NOT EXISTS product_store (
    product_id INTEGER NOT NULL,
    store_id TEXT NOT NULL,
    base_price NUMERIC(10,2) NOT NULL,
    is_available BOOLEAN DEFAULT TRUE,
    product_url TEXT,
    last_seen TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (product_id, store_id)
);

-- Add foreign keys (will be enabled after data migration)
-- We'll add these constraints later to avoid issues during migration

COMMENT ON TABLE product_store IS 'Store-specific product data: prices, availability, URLs';
COMMENT ON COLUMN product_store.product_id IS 'References global product';
COMMENT ON COLUMN product_store.store_id IS 'References store';
COMMENT ON COLUMN product_store.base_price IS 'Regular price at this store';
COMMENT ON COLUMN product_store.is_available IS 'Currently available at this store';
COMMENT ON COLUMN product_store.product_url IS 'Product page URL at this store';

-- ============================================================================
-- STEP 4: MIGRATE DATA FROM offers TO product_store
-- ============================================================================
-- Why: Move store-specific pricing data to new normalized structure
-- Benefit: Preserves all existing price and availability data

INSERT INTO product_store (
    product_id,
    store_id,
    base_price,
    is_available,
    product_url,
    last_seen,
    created_at,
    updated_at
)
SELECT DISTINCT
    o.product_id,
    o.store_id,
    COALESCE(o.base_price, o.price, 0) as base_price,
    COALESCE(o.is_available, TRUE) as is_available,
    o.product_url,
    o.last_seen,
    o.created_at,
    o.updated_at
FROM offers o
WHERE o.product_id IS NOT NULL 
  AND o.store_id IS NOT NULL
  AND COALESCE(o.base_price, o.price) IS NOT NULL
ON CONFLICT (product_id, store_id) DO UPDATE SET
    base_price = EXCLUDED.base_price,
    is_available = EXCLUDED.is_available,
    product_url = EXCLUDED.product_url,
    last_seen = EXCLUDED.last_seen,
    updated_at = EXCLUDED.updated_at;

-- Get count of migrated records
DO $$
DECLARE
    migrated_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO migrated_count FROM product_store;
    RAISE NOTICE 'Migrated % product-store records to product_store table', migrated_count;
END $$;

-- ============================================================================
-- STEP 5: CREATE NEW NORMALIZED offers TABLE STRUCTURE
-- ============================================================================
-- Why: Separate discount rules from product/store targeting
-- Benefit:
--   - Reusable discount rules (one "10% off" rule for many products)
--   - Easy to manage promotions centrally
--   - Query "all active discounts" without product duplication

-- Rename old offers table
ALTER TABLE offers RENAME TO _old_offers;

-- Create new offers table with normalized structure
CREATE TABLE offers (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    discount_type TEXT NOT NULL CHECK (discount_type IN ('percentage', 'fixed', 'bogo', 'bundle', 'tiered')),
    discount_value NUMERIC(10,2) NOT NULL,
    min_quantity INTEGER DEFAULT 1,
    max_quantity INTEGER,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE offers IS 'Reusable discount rules that can be applied to multiple products/stores';
COMMENT ON COLUMN offers.discount_type IS 'Type: percentage (10% off), fixed (€5 off), bogo (buy one get one), bundle, tiered';
COMMENT ON COLUMN offers.discount_value IS 'Value: 10 for 10%, 5.00 for €5 off, etc.';
COMMENT ON COLUMN offers.min_quantity IS 'Minimum quantity required for discount';

-- ============================================================================
-- STEP 6: MIGRATE DISCOUNT DATA FROM OLD offers TO NEW offers
-- ============================================================================
-- Why: Preserve all existing promotional pricing data
-- Benefit: No loss of discount information

INSERT INTO offers (
    name,
    description,
    discount_type,
    discount_value,
    min_quantity,
    is_active,
    created_at,
    updated_at
)
SELECT DISTINCT
    COALESCE(o.offer_details, 'Discount ' || o.id) as name,
    o.offer_details as description,
    CASE
        WHEN o.promo_price IS NOT NULL AND o.base_price IS NOT NULL AND o.base_price > 0 THEN
            CASE
                WHEN o.offer_details ILIKE '%-%' OR o.offer_details ILIKE '%percent%' THEN 'percentage'
                WHEN o.offer_details ILIKE '%+%' OR o.offer_details ILIKE '%gratis%' OR o.offer_details ILIKE '%free%' THEN 'bogo'
                ELSE 'fixed'
            END
        ELSE 'percentage'
    END as discount_type,
    CASE
        WHEN o.promo_price IS NOT NULL AND o.base_price IS NOT NULL AND o.base_price > 0 THEN
            CASE
                WHEN o.offer_details ILIKE '%-%' OR o.offer_details ILIKE '%percent%' THEN
                    ROUND(((o.base_price - o.promo_price) / o.base_price * 100), 2)
                ELSE
                    o.base_price - o.promo_price
            END
        ELSE 10.00
    END as discount_value,
    COALESCE(o.min_quantity, 1) as min_quantity,
    TRUE as is_active,
    o.created_at,
    o.updated_at
FROM _old_offers o
WHERE o.promo_price IS NOT NULL
  AND o.offer_details IS NOT NULL
  AND o.base_price IS NOT NULL
  AND o.base_price > 0
ON CONFLICT DO NOTHING;

-- Get count of migrated offers
DO $$
DECLARE
    offers_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO offers_count FROM offers;
    RAISE NOTICE 'Migrated % discount rules to offers table', offers_count;
END $$;

-- ============================================================================
-- STEP 7: RESTRUCTURE promotions TABLE
-- ============================================================================
-- Why: Promotions should be time-bound campaigns, not discount rules
-- Benefit:
--   - Clear separation: offers = rules, promotions = campaigns
--   - Easy to query "active promotions today"
--   - Can reuse same offer in multiple campaigns

-- Add new columns to promotions
ALTER TABLE promotions ADD COLUMN IF NOT EXISTS name TEXT;
ALTER TABLE promotions ADD COLUMN IF NOT EXISTS description TEXT;
ALTER TABLE promotions ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT TRUE;
ALTER TABLE promotions ADD COLUMN IF NOT EXISTS offer_id INTEGER;

-- Populate name from existing data
UPDATE promotions 
SET name = COALESCE(name, 'Campaign ' || id)
WHERE name IS NULL;

-- Make name required
ALTER TABLE promotions ALTER COLUMN name SET NOT NULL;

-- Drop old columns that belong in offers table
ALTER TABLE promotions DROP COLUMN IF EXISTS type;
ALTER TABLE promotions DROP COLUMN IF EXISTS value;

COMMENT ON TABLE promotions IS 'Time-bound campaigns that apply offers to specific products/stores';
COMMENT ON COLUMN promotions.offer_id IS 'References the discount rule to apply';
COMMENT ON COLUMN promotions.is_active IS 'Whether this campaign is currently active';

-- ============================================================================
-- STEP 8: CREATE promotion_targets TABLE
-- ============================================================================
-- Why: Enable many-to-many relationship between promotions and products/stores
-- Benefit:
--   - One promotion can target multiple products
--   - One promotion can target multiple stores
--   - Easy to query "all products on sale at Store X"
--   - Flexible targeting without data duplication

CREATE TABLE IF NOT EXISTS promotion_targets (
    promotion_id INTEGER NOT NULL,
    product_id INTEGER NOT NULL,
    store_id TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (promotion_id, product_id, store_id)
);

COMMENT ON TABLE promotion_targets IS 'Links promotions to specific product-store combinations';
COMMENT ON COLUMN promotion_targets.promotion_id IS 'Which campaign';
COMMENT ON COLUMN promotion_targets.product_id IS 'Which product';
COMMENT ON COLUMN promotion_targets.store_id IS 'At which store';

-- Migrate existing promotion data if any
-- This creates promotion targets from old offers that had promo_price
INSERT INTO promotion_targets (promotion_id, product_id, store_id)
SELECT DISTINCT
    p.id as promotion_id,
    o.product_id,
    o.store_id
FROM promotions p
CROSS JOIN _old_offers o
WHERE o.promo_price IS NOT NULL
  AND o.product_id IS NOT NULL
  AND o.store_id IS NOT NULL
  AND p.start_date <= CURRENT_DATE
  AND (p.end_date IS NULL OR p.end_date >= CURRENT_DATE)
LIMIT 1000  -- Limit to avoid creating too many targets without proper mapping
ON CONFLICT DO NOTHING;

-- ============================================================================
-- STEP 9: REMOVE store_id FROM products TABLE
-- ============================================================================
-- Why: Products are global entities, not store-specific
-- Benefit:
--   - One product record instead of duplicates per store
--   - Easier to maintain product information
--   - Faster queries for product details

-- First, ensure we have all product data in product_store
-- Then remove the store_id column

ALTER TABLE products DROP CONSTRAINT IF EXISTS products_store_id_fkey;
ALTER TABLE products DROP COLUMN IF EXISTS store_id;

COMMENT ON TABLE products IS 'Global product catalog - store-independent product information';

-- ============================================================================
-- STEP 10: DELETE featured_deals TABLE
-- ============================================================================
-- Why: Explicitly requested to remove this table
-- Benefit: Simplifies schema, removes unused/redundant data

DROP TABLE IF EXISTS featured_deals CASCADE;

RAISE NOTICE 'Deleted featured_deals table as requested';

-- ============================================================================
-- STEP 11: ADD FOREIGN KEY CONSTRAINTS
-- ============================================================================
-- Why: Ensure referential integrity
-- Benefit: Database enforces data consistency automatically

-- product_store foreign keys
ALTER TABLE product_store
    ADD CONSTRAINT fk_product_store_product
    FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE;

ALTER TABLE product_store
    ADD CONSTRAINT fk_product_store_store
    FOREIGN KEY (store_id) REFERENCES stores(store_id) ON DELETE CASCADE;

-- promotions foreign key to offers
ALTER TABLE promotions
    ADD CONSTRAINT fk_promotions_offer
    FOREIGN KEY (offer_id) REFERENCES offers(id) ON DELETE SET NULL;

-- promotion_targets foreign keys
ALTER TABLE promotion_targets
    ADD CONSTRAINT fk_promotion_targets_promotion
    FOREIGN KEY (promotion_id) REFERENCES promotions(id) ON DELETE CASCADE;

ALTER TABLE promotion_targets
    ADD CONSTRAINT fk_promotion_targets_product_store
    FOREIGN KEY (product_id, store_id) REFERENCES product_store(product_id, store_id) ON DELETE CASCADE;

-- ============================================================================
-- STEP 12: CREATE INDEXES FOR PERFORMANCE
-- ============================================================================
-- Why: Optimize common query patterns
-- Benefit: Fast lookups for price comparisons, promotion queries, etc.

-- product_store indexes
CREATE INDEX IF NOT EXISTS idx_product_store_product_id ON product_store(product_id);
CREATE INDEX IF NOT EXISTS idx_product_store_store_id ON product_store(store_id);
CREATE INDEX IF NOT EXISTS idx_product_store_base_price ON product_store(base_price);
CREATE INDEX IF NOT EXISTS idx_product_store_available ON product_store(is_available) WHERE is_available = TRUE;

-- offers indexes
CREATE INDEX IF NOT EXISTS idx_offers_active ON offers(is_active) WHERE is_active = TRUE;
CREATE INDEX IF NOT EXISTS idx_offers_discount_type ON offers(discount_type);

-- promotions indexes
CREATE INDEX IF NOT EXISTS idx_promotions_active ON promotions(is_active) WHERE is_active = TRUE;
CREATE INDEX IF NOT EXISTS idx_promotions_dates ON promotions(start_date, end_date);
CREATE INDEX IF NOT EXISTS idx_promotions_offer_id ON promotions(offer_id);

-- promotion_targets indexes
CREATE INDEX IF NOT EXISTS idx_promotion_targets_promotion ON promotion_targets(promotion_id);
CREATE INDEX IF NOT EXISTS idx_promotion_targets_product ON promotion_targets(product_id);
CREATE INDEX IF NOT EXISTS idx_promotion_targets_store ON promotion_targets(store_id);

-- ============================================================================
-- STEP 13: UPDATE price_history TO REFERENCE product_store
-- ============================================================================
-- Why: Price history should track product_store prices, not old offers
-- Benefit: Maintains historical pricing data in normalized structure

-- Add new columns to price_history
ALTER TABLE price_history ADD COLUMN IF NOT EXISTS product_id INTEGER;
ALTER TABLE price_history ADD COLUMN IF NOT EXISTS store_id TEXT;

-- Migrate data from old offer_id to product_id/store_id
UPDATE price_history ph
SET 
    product_id = o.product_id,
    store_id = o.store_id
FROM _old_offers o
WHERE ph.offer_id = o.id
  AND ph.product_id IS NULL;

-- Create index for performance
CREATE INDEX IF NOT EXISTS idx_price_history_product_store 
ON price_history(product_id, store_id, changed_at DESC);

-- ============================================================================
-- STEP 14: CREATE HELPFUL VIEWS FOR COMMON QUERIES
-- ============================================================================
-- Why: Simplify complex queries for the application
-- Benefit: Easy-to-use views that hide join complexity

-- View: Current prices with promotions
CREATE OR REPLACE VIEW v_current_prices AS
SELECT 
    p.id as product_id,
    p.name as product_name,
    p.brand,
    ps.store_id,
    s.name as store_name,
    ps.base_price,
    ps.is_available,
    ps.product_url,
    o.id as offer_id,
    o.name as offer_name,
    o.discount_type,
    o.discount_value,
    CASE 
        WHEN o.discount_type = 'percentage' THEN 
            ps.base_price * (1 - o.discount_value / 100)
        WHEN o.discount_type = 'fixed' THEN 
            ps.base_price - o.discount_value
        ELSE ps.base_price
    END as final_price,
    pr.id as promotion_id,
    pr.name as promotion_name,
    pr.start_date,
    pr.end_date
FROM products p
JOIN product_store ps ON p.id = ps.product_id
JOIN stores s ON ps.store_id = s.store_id
LEFT JOIN promotion_targets pt ON ps.product_id = pt.product_id AND ps.store_id = pt.store_id
LEFT JOIN promotions pr ON pt.promotion_id = pr.id 
    AND pr.is_active = TRUE
    AND pr.start_date <= CURRENT_DATE
    AND (pr.end_date IS NULL OR pr.end_date >= CURRENT_DATE)
LEFT JOIN offers o ON pr.offer_id = o.id AND o.is_active = TRUE;

COMMENT ON VIEW v_current_prices IS 'Current prices with active promotions applied';

-- View: Products by store
CREATE OR REPLACE VIEW v_products_by_store AS
SELECT 
    s.store_id,
    s.name as store_name,
    COUNT(DISTINCT ps.product_id) as product_count,
    AVG(ps.base_price) as avg_price,
    COUNT(DISTINCT CASE WHEN pt.promotion_id IS NOT NULL THEN ps.product_id END) as products_on_sale
FROM stores s
LEFT JOIN product_store ps ON s.store_id = ps.store_id AND ps.is_available = TRUE
LEFT JOIN promotion_targets pt ON ps.product_id = pt.product_id AND ps.store_id = pt.store_id
LEFT JOIN promotions pr ON pt.promotion_id = pr.id 
    AND pr.is_active = TRUE
    AND pr.start_date <= CURRENT_DATE
    AND (pr.end_date IS NULL OR pr.end_date >= CURRENT_DATE)
GROUP BY s.store_id, s.name;

COMMENT ON VIEW v_products_by_store IS 'Product statistics by store';

-- ============================================================================
-- STEP 15: VERIFICATION QUERIES
-- ============================================================================
-- Why: Ensure migration was successful
-- Benefit: Confidence that no data was lost

DO $$
DECLARE
    original_products INTEGER;
    new_products INTEGER;
    original_offers INTEGER;
    new_product_stores INTEGER;
    new_offers INTEGER;
BEGIN
    -- Count original data
    SELECT COUNT(*) INTO original_products FROM _backup_products;
    SELECT COUNT(*) INTO original_offers FROM _backup_offers;
    
    -- Count new data
    SELECT COUNT(*) INTO new_products FROM products;
    SELECT COUNT(*) INTO new_product_stores FROM product_store;
    SELECT COUNT(*) INTO new_offers FROM offers;
    
    -- Report
    RAISE NOTICE '=== MIGRATION VERIFICATION ===';
    RAISE NOTICE 'Original products: %', original_products;
    RAISE NOTICE 'New products: %', new_products;
    RAISE NOTICE 'Product-store combinations: %', new_product_stores;
    RAISE NOTICE 'Original offers (with pricing): %', original_offers;
    RAISE NOTICE 'New discount rules: %', new_offers;
    RAISE NOTICE '============================';
    
    IF new_products < original_products THEN
        RAISE WARNING 'Product count decreased! Check migration.';
    END IF;
    
    IF new_product_stores = 0 THEN
        RAISE WARNING 'No product_store records created! Check migration.';
    END IF;
END $$;

-- ============================================================================
-- MIGRATION COMPLETE
-- ============================================================================
-- Next steps:
-- 1. Review verification output above
-- 2. Test application queries with new schema
-- 3. Update application code to use new structure
-- 4. After confirming everything works, drop backup tables:
--    DROP TABLE _backup_products, _backup_offers, _backup_promotions, _old_offers;
-- ============================================================================
