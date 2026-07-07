-- Migration 004: Add unit price and product-tier flags to product_store
-- Run once against Neon: psql $DATABASE_URL -f migrations/004_product_store_extra_fields.sql

ALTER TABLE product_store
    ADD COLUMN IF NOT EXISTS unit_price       NUMERIC(10, 4),
    ADD COLUMN IF NOT EXISTS unit_price_unit  TEXT,
    ADD COLUMN IF NOT EXISTS is_preis_gesenkt BOOLEAN DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS immer_billig     BOOLEAN DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS has_app_voucher  BOOLEAN DEFAULT FALSE;

-- unit_price: Grundpreis (e.g. 10.65 per litre) — legally required display in Austria
-- unit_price_unit: the reference unit (l, kg, stk, 100g, …)
-- is_preis_gesenkt: permanent shelf-price reduction (not a time-limited promo)
-- immer_billig: SPAR's budget "always cheap" tier
-- has_app_voucher: lower price available via the SPAR app
