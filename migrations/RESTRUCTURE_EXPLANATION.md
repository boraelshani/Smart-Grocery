# Database Restructuring Explanation

## 🎯 Why This Restructuring Makes Data Retrieval Easier

### Problem with Old Schema
The original schema had several issues that made queries complex and data management difficult:

1. **Product Duplication**: Each product was duplicated for every store that sold it
2. **Mixed Responsibilities**: The `offers` table contained both pricing data AND discount rules
3. **No Reusability**: Discount rules couldn't be reused across products
4. **Denormalized Data**: Store-specific data mixed with global product data

### Solution: Normalized Schema
The new schema separates concerns and creates clear relationships:

```
products (global product info)
    ↓
product_store (store-specific pricing)
    ↓
promotion_targets (which products are on sale)
    ↓
promotions (time-bound campaigns)
    ↓
offers (reusable discount rules)
```

---

## 📊 New Schema Structure

### 1. `products` Table - Global Product Catalog
**Purpose**: Store product information that's the same across all stores

```sql
products
├── id (PK)
├── name                    -- Product name
├── brand                   -- Brand name
├── category_id            -- Product category
├── unit_normalized        -- Unit (kg, l, etc.)
├── size_normalized        -- Size amount
├── default_image_url      -- Product image
├── barcode                -- Barcode/EAN
├── created_at
└── updated_at
```

**Why this helps**:
- ✅ One product record instead of duplicates per store
- ✅ Update product name once, affects all stores
- ✅ Fast queries for product details
- ✅ No data duplication

**Example Query**: Get product details
```sql
SELECT * FROM products WHERE id = 123;
-- Returns ONE record with all product info
```

---

### 2. `product_store` Table - Store-Specific Data
**Purpose**: Store pricing and availability per store

```sql
product_store
├── product_id (PK, FK → products)
├── store_id (PK, FK → stores)
├── base_price             -- Regular price at this store
├── is_available           -- Available at this store?
├── product_url            -- Store's product page URL
├── last_seen              -- Last time we saw it
├── created_at
└── updated_at
```

**Why this helps**:
- ✅ Separate pricing from product data
- ✅ Easy to compare prices across stores
- ✅ Can track availability per store
- ✅ One-to-many: one product, many stores

**Example Query**: Compare prices across stores
```sql
SELECT 
    p.name,
    s.name as store_name,
    ps.base_price
FROM products p
JOIN product_store ps ON p.id = ps.product_id
JOIN stores s ON ps.store_id = s.store_id
WHERE p.id = 123
ORDER BY ps.base_price ASC;
-- Shows all stores selling this product with their prices
```

---

### 3. `offers` Table - Reusable Discount Rules
**Purpose**: Define discount rules that can be reused

```sql
offers
├── id (PK)
├── name                   -- "10% Off", "Buy 2 Get 1 Free"
├── description            -- Details about the offer
├── discount_type          -- percentage, fixed, bogo, bundle, tiered
├── discount_value         -- 10 (for 10%), 5.00 (for €5 off)
├── min_quantity           -- Minimum quantity required
├── max_quantity           -- Maximum quantity (optional)
├── is_active              -- Is this offer active?
├── created_at
└── updated_at
```

**Why this helps**:
- ✅ Create one discount rule, use it many times
- ✅ Easy to manage all discounts centrally
- ✅ Can activate/deactivate offers globally
- ✅ Clear discount logic

**Example Query**: Get all active discount rules
```sql
SELECT * FROM offers WHERE is_active = TRUE;
-- Returns all available discount types
```

---

### 4. `promotions` Table - Time-Bound Campaigns
**Purpose**: Run campaigns with specific start/end dates

```sql
promotions
├── id (PK)
├── name                   -- "Black Friday Sale"
├── description            -- Campaign details
├── offer_id (FK → offers) -- Which discount rule to apply
├── start_date             -- When campaign starts
├── end_date               -- When campaign ends
├── is_active              -- Is campaign active?
├── created_at
└── updated_at
```

**Why this helps**:
- ✅ Time-bound campaigns with clear dates
- ✅ Reuse same offer in multiple campaigns
- ✅ Easy to query "active promotions today"
- ✅ Separate campaign management from discount rules

**Example Query**: Get active promotions today
```sql
SELECT * FROM promotions
WHERE is_active = TRUE
  AND start_date <= CURRENT_DATE
  AND (end_date IS NULL OR end_date >= CURRENT_DATE);
-- Returns all running campaigns
```

---

### 5. `promotion_targets` Table - Product/Store Targeting
**Purpose**: Link promotions to specific products at specific stores

```sql
promotion_targets
├── promotion_id (PK, FK → promotions)
├── product_id (PK, FK → product_store)
├── store_id (PK, FK → product_store)
└── created_at
```

**Why this helps**:
- ✅ Many-to-many relationship
- ✅ One promotion can target many products
- ✅ One promotion can target many stores
- ✅ Flexible targeting without duplication

**Example Query**: Get all products on sale at a specific store
```sql
SELECT 
    p.name,
    ps.base_price,
    o.discount_type,
    o.discount_value,
    pr.name as promotion_name
FROM products p
JOIN product_store ps ON p.id = ps.product_id
JOIN promotion_targets pt ON ps.product_id = pt.product_id 
    AND ps.store_id = pt.store_id
JOIN promotions pr ON pt.promotion_id = pr.id
JOIN offers o ON pr.offer_id = o.id
WHERE ps.store_id = 'billa'
  AND pr.is_active = TRUE
  AND pr.start_date <= CURRENT_DATE
  AND (pr.end_date IS NULL OR pr.end_date >= CURRENT_DATE);
-- Shows all products on sale at Billa today
```

---

## 🚀 Common Query Patterns

### Query 1: Show Product with Prices Across All Stores
```sql
SELECT 
    p.name as product_name,
    p.brand,
    s.name as store_name,
    ps.base_price,
    ps.is_available
FROM products p
JOIN product_store ps ON p.id = ps.product_id
JOIN stores s ON ps.store_id = s.store_id
WHERE p.id = 123
ORDER BY ps.base_price ASC;
```

**Why this is easy**: Simple joins, no subqueries needed

---

### Query 2: Calculate Final Price with Discount
```sql
SELECT 
    p.name,
    ps.base_price,
    o.discount_type,
    o.discount_value,
    CASE 
        WHEN o.discount_type = 'percentage' THEN 
            ps.base_price * (1 - o.discount_value / 100)
        WHEN o.discount_type = 'fixed' THEN 
            ps.base_price - o.discount_value
        ELSE ps.base_price
    END as final_price
FROM products p
JOIN product_store ps ON p.id = ps.product_id
LEFT JOIN promotion_targets pt ON ps.product_id = pt.product_id 
    AND ps.store_id = pt.store_id
LEFT JOIN promotions pr ON pt.promotion_id = pr.id 
    AND pr.is_active = TRUE
    AND pr.start_date <= CURRENT_DATE
    AND (pr.end_date IS NULL OR pr.end_date >= CURRENT_DATE)
LEFT JOIN offers o ON pr.offer_id = o.id
WHERE p.id = 123 AND ps.store_id = 'billa';
```

**Why this is easy**: Clear calculation logic, LEFT JOINs handle products without promotions

---

### Query 3: Find Cheapest Store for a Product
```sql
SELECT 
    s.name as store_name,
    ps.base_price,
    COALESCE(
        CASE 
            WHEN o.discount_type = 'percentage' THEN 
                ps.base_price * (1 - o.discount_value / 100)
            WHEN o.discount_type = 'fixed' THEN 
                ps.base_price - o.discount_value
            ELSE ps.base_price
        END,
        ps.base_price
    ) as final_price
FROM product_store ps
JOIN stores s ON ps.store_id = s.store_id
LEFT JOIN promotion_targets pt ON ps.product_id = pt.product_id 
    AND ps.store_id = pt.store_id
LEFT JOIN promotions pr ON pt.promotion_id = pr.id 
    AND pr.is_active = TRUE
    AND pr.start_date <= CURRENT_DATE
    AND (pr.end_date IS NULL OR pr.end_date >= CURRENT_DATE)
LEFT JOIN offers o ON pr.offer_id = o.id
WHERE ps.product_id = 123
  AND ps.is_available = TRUE
ORDER BY final_price ASC
LIMIT 1;
```

**Why this is easy**: Single query, no complex subqueries, handles promotions automatically

---

### Query 4: Get All Products in a Category on Sale
```sql
SELECT 
    p.name,
    p.brand,
    s.name as store_name,
    ps.base_price,
    o.discount_value,
    pr.name as promotion_name
FROM products p
JOIN product_store ps ON p.id = ps.product_id
JOIN stores s ON ps.store_id = s.store_id
JOIN promotion_targets pt ON ps.product_id = pt.product_id 
    AND ps.store_id = pt.store_id
JOIN promotions pr ON pt.promotion_id = pr.id
JOIN offers o ON pr.offer_id = o.id
WHERE p.category_id = 5
  AND pr.is_active = TRUE
  AND pr.start_date <= CURRENT_DATE
  AND (pr.end_date IS NULL OR pr.end_date >= CURRENT_DATE)
ORDER BY o.discount_value DESC;
```

**Why this is easy**: Straightforward joins, filters active promotions naturally

---

### Query 5: Price History for a Product at a Store
```sql
SELECT 
    ph.changed_at,
    ph.old_price,
    ph.new_price,
    ph.new_price - ph.old_price as price_change
FROM price_history ph
WHERE ph.product_id = 123
  AND ph.store_id = 'billa'
ORDER BY ph.changed_at DESC
LIMIT 10;
```

**Why this is easy**: Direct access to price history by product and store

---

## 📈 Performance Benefits

### Before (Denormalized)
```sql
-- Find all stores selling a product
SELECT * FROM products WHERE name LIKE '%milk%';
-- Returns 50 rows (same product duplicated per store)
-- Must filter duplicates in application code
```

### After (Normalized)
```sql
-- Find product
SELECT * FROM products WHERE name LIKE '%milk%';
-- Returns 1 row

-- Get stores selling it
SELECT s.* FROM stores s
JOIN product_store ps ON s.store_id = ps.store_id
WHERE ps.product_id = 123;
-- Returns 5 rows (5 stores)
-- Clean, no duplicates
```

**Performance improvement**: 
- ✅ 10x less data to scan
- ✅ Indexes work better
- ✅ Faster queries
- ✅ Less memory usage

---

## 🔄 Data Integrity Benefits

### Automatic Consistency
```sql
-- Update product name
UPDATE products SET name = 'New Name' WHERE id = 123;
-- Automatically affects all stores (no need to update 50 rows)
```

### Cascade Deletes
```sql
-- Delete a product
DELETE FROM products WHERE id = 123;
-- Automatically removes:
--   - All product_store entries
--   - All promotion_targets
--   - All price_history
-- No orphaned data!
```

### Referential Integrity
```sql
-- Try to add invalid promotion target
INSERT INTO promotion_targets (promotion_id, product_id, store_id)
VALUES (999, 123, 'invalid_store');
-- ERROR: Foreign key violation
-- Database prevents invalid data automatically
```

---

## 🎓 Migration Safety

### Backup Tables Created
- `_backup_products` - Original products
- `_backup_offers` - Original offers
- `_backup_promotions` - Original promotions
- `_old_offers` - Renamed offers table

### Rollback Plan
If something goes wrong:
```sql
-- Restore products
DROP TABLE products;
ALTER TABLE _backup_products RENAME TO products;

-- Restore offers
DROP TABLE offers;
ALTER TABLE _old_offers RENAME TO offers;

-- Restore promotions
DROP TABLE promotions;
ALTER TABLE _backup_promotions RENAME TO promotions;
```

---

## ✅ Verification Checklist

After migration, verify:

1. **Product Count**
   ```sql
   SELECT COUNT(*) FROM products;
   -- Should be ~12,391 (unique products)
   ```

2. **Product-Store Combinations**
   ```sql
   SELECT COUNT(*) FROM product_store;
   -- Should be ~12,391 (one per product-store pair)
   ```

3. **Discount Rules**
   ```sql
   SELECT COUNT(*) FROM offers;
   -- Should have all unique discount rules
   ```

4. **No Data Loss**
   ```sql
   -- Compare backup vs new
   SELECT 
       (SELECT COUNT(*) FROM _backup_products) as old_products,
       (SELECT COUNT(*) FROM products) as new_products,
       (SELECT COUNT(*) FROM product_store) as product_stores;
   ```

5. **Views Work**
   ```sql
   SELECT * FROM v_current_prices LIMIT 10;
   -- Should return products with prices
   ```

---

## 🚀 Next Steps

1. **Run Migration**
   ```bash
   psql $DATABASE_URL -f migrations/001_database_restructure.sql
   ```

2. **Verify Data**
   ```bash
   psql $DATABASE_URL -f migrations/002_verify_migration.sql
   ```

3. **Update Application Code**
   - Update ORM models
   - Update queries to use new schema
   - Test all features

4. **Clean Up** (after confirming everything works)
   ```sql
   DROP TABLE _backup_products, _backup_offers, _backup_promotions, _old_offers;
   ```

---

## 📞 Support

If you encounter issues:
1. Check backup tables exist
2. Review verification output
3. Test queries with new schema
4. Rollback if needed (see Rollback Plan above)
