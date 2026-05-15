# Billa Scraper Improvements

## Summary of Changes

The Billa scraper has been significantly improved to capture all products and offers with proper structure.

### Key Improvements

#### 1. **Complete Offer Data Extraction**
- ✅ **Base Price**: Regular product price
- ✅ **Promo Price**: Discounted/promotional price when available
- ✅ **Unit Price**: Price per standardized unit (e.g., "€1.99/kg")
- ✅ **Offer Details**: Discount percentage, special offers (e.g., "-30%", "2+1 gratis")
- ✅ **Min Quantity**: Minimum quantity required for promotional price (e.g., "ab 24 Stück")

#### 2. **Better Product Coverage**
- Increased retries from 3 to 5 attempts per product
- Longer timeouts (60s instead of 45s)
- Better handling of redirects and removed products
- Improved error handling for network issues

#### 3. **Enhanced Logging**
- Progress tracking every 500 products
- Separate counters for: inserted, failed, and skipped products
- Batch completion summaries
- Final summary with all statistics

#### 4. **PostgreSQL Only**
- ✅ Already using PostgreSQL (no MongoDB code to remove)
- ✅ Proper use of `base_price`, `promo_price`, `unit_price`, `offer_details`, `min_quantity` fields
- ✅ Price history tracks effective prices (promo if available, otherwise base)

### Database Schema

The scraper now properly populates the `offers` table with:

```sql
CREATE TABLE offers (
    id SERIAL PRIMARY KEY,
    product_id INTEGER REFERENCES products(id),
    store_id TEXT,
    price NUMERIC(10, 2),           -- Legacy field (for compatibility)
    base_price NUMERIC(10, 2),      -- Regular price
    promo_price NUMERIC(10, 2),     -- Promotional/discounted price
    unit_price TEXT,                 -- e.g., "€1.99/kg"
    offer_details TEXT,              -- e.g., "2+1 gratis", "-30%"
    min_quantity INTEGER,            -- Minimum quantity for promo
    product_url TEXT,
    is_available BOOLEAN,
    last_seen TIMESTAMP,
    created_at TIMESTAMP,
    updated_at TIMESTAMP
);
```

## How to Run

### First Time (Full Scrape)
```bash
cd /Users/drenbuqa/Documents/GitHub/Smart-Grocery/Smart-Grocery-1
python3 scripts/billa_sitemap_to_postgres.py --workers 8 --chunk-size 300
```

### Resume Mode (Add Missing Products)
```bash
python3 scripts/billa_sitemap_to_postgres.py --workers 8 --chunk-size 300 --resume
```

The `--resume` flag will:
- Keep all existing products and offers
- Only scrape products that aren't already in the database
- Perfect for adding the missing 3,000 products

### Parallel Processing (Faster)
If you want to speed up the scraping, you can run multiple processes:

```bash
# Terminal 1
python3 scripts/billa_sitemap_to_postgres.py --workers 8 --shard-count 4 --shard-index 0 --resume

# Terminal 2
python3 scripts/billa_sitemap_to_postgres.py --workers 8 --shard-count 4 --shard-index 1 --resume

# Terminal 3
python3 scripts/billa_sitemap_to_postgres.py --workers 8 --shard-count 4 --shard-index 2 --resume

# Terminal 4
python3 scripts/billa_sitemap_to_postgres.py --workers 8 --shard-count 4 --shard-index 3 --resume
```

## What Was Changed

### File: `scripts/billa_sitemap_to_postgres.py`

1. **New Function: `_extract_price_data()`**
   - Extracts comprehensive price and offer information
   - Handles multiple price formats from Billa's API
   - Detects discounts, promotions, and quantity-based offers
   - Extracts offer labels and badges

2. **Updated Function: `_build_product_row()`**
   - Now includes all offer fields: `base_price`, `promo_price`, `unit_price`, `offer_details`, `min_quantity`
   - Uses new `_extract_price_data()` function

3. **Updated Function: `_insert_offers()`**
   - Inserts all offer fields into database
   - Properly handles both base and promotional prices
   - Updates existing offers with new data

4. **Updated Function: `_insert_price_history()`**
   - Records effective price (promo if available, otherwise base)
   - Tracks price changes over time

5. **Updated Function: `_fetch_product()`**
   - Increased retries from 3 to 5
   - Longer timeout (60s instead of 45s)
   - Better error handling for HTTP errors
   - Handles 404/410 (removed products) gracefully

6. **Enhanced Logging**
   - Added counters for failed and skipped products
   - Progress updates every 500 products
   - Batch completion summaries
   - Final summary with all statistics

## Expected Results

After running with `--resume`:
- ✅ All ~15,000 products should be in the database
- ✅ All offers with discounts will have `promo_price` populated
- ✅ Offer details like "-30%" or "2+1 gratis" will be in `offer_details`
- ✅ Products with quantity-based pricing will have `min_quantity` set
- ✅ Unit prices like "€1.99/kg" will be in `unit_price`

## Verification

After running, you can verify the data:

```sql
-- Check total products
SELECT COUNT(*) FROM products WHERE store_id = 'billa';

-- Check offers with promotions
SELECT COUNT(*) FROM offers WHERE store_id = 'billa' AND promo_price IS NOT NULL;

-- Check offers with details
SELECT COUNT(*) FROM offers WHERE store_id = 'billa' AND offer_details IS NOT NULL;

-- Sample offers with promotions
SELECT 
    p.name_de,
    o.base_price,
    o.promo_price,
    o.offer_details,
    o.min_quantity,
    o.unit_price
FROM offers o
JOIN products p ON o.product_id = p.id
WHERE o.store_id = 'billa' 
    AND o.promo_price IS NOT NULL
LIMIT 20;
```

## Notes

- **Categories**: The scraper does NOT import Billa's categories (as requested). It only maps products to your existing category structure.
- **No Data Loss**: Using `--resume` ensures no existing data is removed or replaced.
- **MongoDB**: There was no MongoDB code in the scraper - it was already using PostgreSQL exclusively.
- **Performance**: With 8 workers, expect ~100-150 products per minute. Full scrape of 15k products takes ~2-3 hours.
