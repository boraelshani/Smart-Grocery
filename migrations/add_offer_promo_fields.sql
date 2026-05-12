-- Migration: Add promotional pricing fields to offers table
-- Date: 2025-01-09
-- Description: Adds base_price, promo_price, unit_price, and offer_details columns to support promotional offers

-- Add new columns to offers table
ALTER TABLE offers 
ADD COLUMN IF NOT EXISTS base_price NUMERIC(10, 2),
ADD COLUMN IF NOT EXISTS promo_price NUMERIC(10, 2),
ADD COLUMN IF NOT EXISTS unit_price TEXT,
ADD COLUMN IF NOT EXISTS offer_details TEXT;

-- Migrate existing data: copy price to base_price if base_price is null
UPDATE offers 
SET base_price = price 
WHERE base_price IS NULL AND price IS NOT NULL;

-- Add comment to columns
COMMENT ON COLUMN offers.base_price IS 'Regular/base price of the product';
COMMENT ON COLUMN offers.promo_price IS 'Promotional/discounted price (if on sale)';
COMMENT ON COLUMN offers.unit_price IS 'Unit price string (e.g., €1.99/kg)';
COMMENT ON COLUMN offers.offer_details IS 'Offer description (e.g., 2+1 gratis, -30%)';

-- Create index on promo_price for faster queries on promotional items
CREATE INDEX IF NOT EXISTS idx_offers_promo_price ON offers(promo_price) WHERE promo_price IS NOT NULL;
