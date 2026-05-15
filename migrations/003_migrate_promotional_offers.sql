-- Migration: Populate promotions and promotion_targets from _old_offers
-- This migrates the 1,060 promotional offers to the new normalized structure

BEGIN;

-- Drop the incorrect foreign key constraint if it exists
ALTER TABLE promotions DROP CONSTRAINT IF EXISTS promotions_offer_id_fkey;

-- Step 1: Create promotions from unique offer patterns in _old_offers
-- Group by offer_details to create reusable promotion campaigns
INSERT INTO promotions (name, description, offer_id, start_date, end_date, is_active, created_at)
SELECT DISTINCT
    COALESCE(offer_details, 'Discount') as name,
    CASE 
        WHEN offer_details LIKE '-%' THEN 'Percentage discount: ' || offer_details
        WHEN offer_details IS NOT NULL THEN 'Special offer: ' || offer_details
        ELSE 'Price reduction'
    END as description,
    (
        SELECT id FROM offers 
        WHERE name = COALESCE(o.offer_details, 'Discount')
        LIMIT 1
    ) as offer_id,
    CURRENT_DATE as start_date,
    CURRENT_DATE + INTERVAL '30 days' as end_date,
    true as is_active,
    NOW() as created_at
FROM _old_offers o
WHERE promo_price IS NOT NULL OR offer_details IS NOT NULL
ON CONFLICT DO NOTHING;

-- Step 2: Create promotion_targets linking promotions to product-store combinations
-- This connects each promotional offer to its specific product and store
INSERT INTO promotion_targets (promotion_id, product_id, store_id, created_at)
SELECT DISTINCT
    p.id as promotion_id,
    o.product_id,
    o.store_id,
    NOW() as created_at
FROM _old_offers o
JOIN promotions p ON p.name = COALESCE(o.offer_details, 'Discount')
WHERE (o.promo_price IS NOT NULL OR o.offer_details IS NOT NULL)
  AND EXISTS (
      SELECT 1 FROM product_store ps 
      WHERE ps.product_id = o.product_id 
      AND ps.store_id = o.store_id
  )
ON CONFLICT DO NOTHING;

-- Step 3: Verify the migration
DO $$
DECLARE
    promo_count INTEGER;
    target_count INTEGER;
    old_offer_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO promo_count FROM promotions;
    SELECT COUNT(*) INTO target_count FROM promotion_targets;
    SELECT COUNT(*) INTO old_offer_count FROM _old_offers WHERE promo_price IS NOT NULL OR offer_details IS NOT NULL;
    
    RAISE NOTICE 'Migration Summary:';
    RAISE NOTICE '  Promotions created: %', promo_count;
    RAISE NOTICE '  Promotion targets created: %', target_count;
    RAISE NOTICE '  Original promotional offers: %', old_offer_count;
    
    IF target_count < old_offer_count * 0.9 THEN
        RAISE WARNING 'Less than 90%% of promotional offers were migrated. Please investigate.';
    END IF;
END $$;

COMMIT;

-- Create helpful views for querying active promotions
CREATE OR REPLACE VIEW active_promotions_view AS
SELECT 
    p.id as promotion_id,
    p.name as promotion_name,
    p.description,
    o.discount_type,
    o.discount_value,
    pt.product_id,
    pt.store_id,
    prod.name as product_name,
    prod.default_image_url,
    ps.base_price,
    CASE 
        WHEN o.discount_type = 'percentage' THEN ps.base_price * (1 - o.discount_value / 100)
        WHEN o.discount_type = 'fixed' THEN ps.base_price - o.discount_value
        ELSE ps.base_price
    END as discounted_price,
    p.start_date,
    p.end_date,
    p.is_active
FROM promotions p
JOIN promotion_targets pt ON pt.promotion_id = p.id
JOIN product_store ps ON ps.product_id = pt.product_id AND ps.store_id = pt.store_id
JOIN products prod ON prod.id = pt.product_id
LEFT JOIN offers o ON o.id = p.offer_id
WHERE p.is_active = true
  AND p.start_date <= CURRENT_DATE
  AND (p.end_date IS NULL OR p.end_date >= CURRENT_DATE);

COMMENT ON VIEW active_promotions_view IS 'Shows all currently active promotions with calculated discounted prices';
