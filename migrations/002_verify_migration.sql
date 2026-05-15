-- ============================================================================
-- Migration Verification Script
-- ============================================================================
-- Purpose: Verify that the database restructuring was successful
-- Run this after running 001_database_restructure.sql
-- ============================================================================

\echo '============================================================================'
\echo 'MIGRATION VERIFICATION REPORT'
\echo '============================================================================'
\echo ''

-- ============================================================================
-- 1. TABLE EXISTENCE CHECK
-- ============================================================================
\echo '1. Checking table existence...'
\echo ''

SELECT 
    CASE 
        WHEN EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'products') 
        THEN '✓ products table exists'
        ELSE '✗ products table MISSING'
    END as status
UNION ALL
SELECT 
    CASE 
        WHEN EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'product_store') 
        THEN '✓ product_store table exists'
        ELSE '✗ product_store table MISSING'
    END
UNION ALL
SELECT 
    CASE 
        WHEN EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'offers') 
        THEN '✓ offers table exists'
        ELSE '✗ offers table MISSING'
    END
UNION ALL
SELECT 
    CASE 
        WHEN EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'promotions') 
        THEN '✓ promotions table exists'
        ELSE '✗ promotions table MISSING'
    END
UNION ALL
SELECT 
    CASE 
        WHEN EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'promotion_targets') 
        THEN '✓ promotion_targets table exists'
        ELSE '✗ promotion_targets table MISSING'
    END
UNION ALL
SELECT 
    CASE 
        WHEN NOT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'featured_deals') 
        THEN '✓ featured_deals table deleted'
        ELSE '✗ featured_deals table still exists'
    END;

\echo ''

-- ============================================================================
-- 2. DATA COUNT VERIFICATION
-- ============================================================================
\echo '2. Verifying data counts...'
\echo ''

SELECT 
    'Products' as table_name,
    COUNT(*) as record_count,
    'Should be ~12,391 unique products' as expected
FROM products
UNION ALL
SELECT 
    'Product-Store',
    COUNT(*),
    'Should be ~12,391 product-store combinations'
FROM product_store
UNION ALL
SELECT 
    'Offers',
    COUNT(*),
    'Should have discount rules from old offers'
FROM offers
UNION ALL
SELECT 
    'Promotions',
    COUNT(*),
    'Should have existing promotions'
FROM promotions
UNION ALL
SELECT 
    'Promotion Targets',
    COUNT(*),
    'Should have promotion-product-store links'
FROM promotion_targets;

\echo ''

-- ============================================================================
-- 3. COLUMN VERIFICATION
-- ============================================================================
\echo '3. Verifying column structure...'
\echo ''

-- Check products table doesn't have store_id
SELECT 
    CASE 
        WHEN NOT EXISTS (
            SELECT 1 FROM information_schema.columns 
            WHERE table_name = 'products' AND column_name = 'store_id'
        ) 
        THEN '✓ products.store_id removed'
        ELSE '✗ products.store_id still exists'
    END as status
UNION ALL
-- Check products has name column
SELECT 
    CASE 
        WHEN EXISTS (
            SELECT 1 FROM information_schema.columns 
            WHERE table_name = 'products' AND column_name = 'name'
        ) 
        THEN '✓ products.name exists'
        ELSE '✗ products.name MISSING'
    END
UNION ALL
-- Check product_store has required columns
SELECT 
    CASE 
        WHEN EXISTS (
            SELECT 1 FROM information_schema.columns 
            WHERE table_name = 'product_store' AND column_name = 'base_price'
        ) 
        THEN '✓ product_store.base_price exists'
        ELSE '✗ product_store.base_price MISSING'
    END
UNION ALL
-- Check offers has new structure
SELECT 
    CASE 
        WHEN EXISTS (
            SELECT 1 FROM information_schema.columns 
            WHERE table_name = 'offers' AND column_name = 'discount_type'
        ) 
        THEN '✓ offers.discount_type exists'
        ELSE '✗ offers.discount_type MISSING'
    END
UNION ALL
SELECT 
    CASE 
        WHEN NOT EXISTS (
            SELECT 1 FROM information_schema.columns 
            WHERE table_name = 'offers' AND column_name = 'product_id'
        ) 
        THEN '✓ offers.product_id removed'
        ELSE '✗ offers.product_id still exists'
    END;

\echo ''

-- ============================================================================
-- 4. FOREIGN KEY VERIFICATION
-- ============================================================================
\echo '4. Verifying foreign key constraints...'
\echo ''

SELECT 
    tc.table_name,
    tc.constraint_name,
    tc.constraint_type,
    '✓' as status
FROM information_schema.table_constraints tc
WHERE tc.constraint_type = 'FOREIGN KEY'
  AND tc.table_name IN ('product_store', 'promotions', 'promotion_targets')
ORDER BY tc.table_name, tc.constraint_name;

\echo ''

-- ============================================================================
-- 5. INDEX VERIFICATION
-- ============================================================================
\echo '5. Verifying indexes...'
\echo ''

SELECT 
    tablename,
    indexname,
    '✓' as status
FROM pg_indexes
WHERE tablename IN ('product_store', 'offers', 'promotions', 'promotion_targets')
ORDER BY tablename, indexname;

\echo ''

-- ============================================================================
-- 6. VIEW VERIFICATION
-- ============================================================================
\echo '6. Verifying views...'
\echo ''

SELECT 
    table_name as view_name,
    '✓' as status
FROM information_schema.views
WHERE table_name IN ('v_current_prices', 'v_products_by_store')
ORDER BY table_name;

\echo ''

-- ============================================================================
-- 7. DATA INTEGRITY CHECKS
-- ============================================================================
\echo '7. Checking data integrity...'
\echo ''

-- Check for products without any store
SELECT 
    CASE 
        WHEN COUNT(*) = 0 
        THEN '✓ All products have at least one store'
        ELSE '✗ ' || COUNT(*) || ' products have no stores'
    END as status
FROM products p
LEFT JOIN product_store ps ON p.id = ps.product_id
WHERE ps.product_id IS NULL;

-- Check for orphaned product_store records
SELECT 
    CASE 
        WHEN COUNT(*) = 0 
        THEN '✓ No orphaned product_store records'
        ELSE '✗ ' || COUNT(*) || ' orphaned product_store records'
    END
FROM product_store ps
LEFT JOIN products p ON ps.product_id = p.id
WHERE p.id IS NULL;

-- Check for null prices
SELECT 
    CASE 
        WHEN COUNT(*) = 0 
        THEN '✓ No null prices in product_store'
        ELSE '✗ ' || COUNT(*) || ' null prices found'
    END
FROM product_store
WHERE base_price IS NULL;

\echo ''

-- ============================================================================
-- 8. SAMPLE DATA VERIFICATION
-- ============================================================================
\echo '8. Sample data verification...'
\echo ''

\echo 'Sample products:'
SELECT 
    id,
    name,
    brand,
    category_id
FROM products
LIMIT 5;

\echo ''
\echo 'Sample product_store records:'
SELECT 
    ps.product_id,
    p.name,
    ps.store_id,
    ps.base_price,
    ps.is_available
FROM product_store ps
JOIN products p ON ps.product_id = p.id
LIMIT 5;

\echo ''
\echo 'Sample offers:'
SELECT 
    id,
    name,
    discount_type,
    discount_value,
    is_active
FROM offers
LIMIT 5;

\echo ''

-- ============================================================================
-- 9. BACKUP TABLE VERIFICATION
-- ============================================================================
\echo '9. Verifying backup tables exist...'
\echo ''

SELECT 
    CASE 
        WHEN EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = '_backup_products') 
        THEN '✓ _backup_products exists'
        ELSE '✗ _backup_products MISSING'
    END as status
UNION ALL
SELECT 
    CASE 
        WHEN EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = '_backup_offers') 
        THEN '✓ _backup_offers exists'
        ELSE '✗ _backup_offers MISSING'
    END
UNION ALL
SELECT 
    CASE 
        WHEN EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = '_old_offers') 
        THEN '✓ _old_offers exists'
        ELSE '✗ _old_offers MISSING'
    END;

\echo ''

-- ============================================================================
-- 10. QUERY PERFORMANCE TEST
-- ============================================================================
\echo '10. Testing query performance...'
\echo ''

\echo 'Query 1: Get product with prices across stores'
EXPLAIN ANALYZE
SELECT 
    p.name,
    s.name as store_name,
    ps.base_price
FROM products p
JOIN product_store ps ON p.id = ps.product_id
JOIN stores s ON ps.store_id = s.store_id
WHERE p.id = (SELECT id FROM products LIMIT 1)
ORDER BY ps.base_price ASC;

\echo ''
\echo 'Query 2: Get active promotions'
EXPLAIN ANALYZE
SELECT COUNT(*) 
FROM promotions
WHERE is_active = TRUE
  AND start_date <= CURRENT_DATE
  AND (end_date IS NULL OR end_date >= CURRENT_DATE);

\echo ''

-- ============================================================================
-- SUMMARY
-- ============================================================================
\echo '============================================================================'
\echo 'VERIFICATION COMPLETE'
\echo '============================================================================'
\echo ''
\echo 'Review the output above for any ✗ marks indicating issues.'
\echo 'If all checks show ✓, the migration was successful!'
\echo ''
\echo 'Next steps:'
\echo '1. Test application queries with new schema'
\echo '2. Update ORM models to match new structure'
\echo '3. After confirming everything works, clean up backup tables:'
\echo '   DROP TABLE _backup_products, _backup_offers, _backup_promotions, _old_offers;'
\echo ''
\echo '============================================================================'
