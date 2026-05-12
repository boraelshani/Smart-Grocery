-- Migration: Add min_quantity column to offers table
-- Date: 2025-01-09
-- Description: Adds min_quantity column to support quantity-based discounts (e.g., "ab 24 Stück")

-- Add min_quantity column
ALTER TABLE offers 
ADD COLUMN IF NOT EXISTS min_quantity INTEGER;

-- Add comment
COMMENT ON COLUMN offers.min_quantity IS 'Minimum quantity required for promotional price (e.g., 24 for "ab 24 Stück €0.99")';

-- Create index for queries filtering by min_quantity
CREATE INDEX IF NOT EXISTS idx_offers_min_quantity ON offers(min_quantity) WHERE min_quantity IS NOT NULL;
