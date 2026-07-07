-- Add per-store product name and size to product_store
-- These store the store-specific name and size which may differ from the canonical product

ALTER TABLE product_store
    ADD COLUMN IF NOT EXISTS store_product_name TEXT,
    ADD COLUMN IF NOT EXISTS store_size_normalized NUMERIC(10,3),
    ADD COLUMN IF NOT EXISTS store_unit_normalized TEXT;
