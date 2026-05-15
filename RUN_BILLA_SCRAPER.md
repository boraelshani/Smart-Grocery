# How to Run the Improved Billa Scraper

## Current Status (Verified)
- ✅ 12,391 products in database
- ❌ Missing ~2,609 products (target: 15,000)
- ❌ **0 promotional offers captured** (all offer fields are empty)

## What the Improved Scraper Will Do

The updated scraper will:
1. ✅ Add the missing ~2,609 products
2. ✅ Update ALL 15,000 products with proper offer data:
   - Base prices (regular price)
   - Promotional prices (discounted price when on sale)
   - Unit prices (e.g., "€1.99/kg")
   - Offer details (e.g., "-30%", "2+1 gratis")
   - Minimum quantities for bulk discounts

3. ✅ Keep all existing data (no deletions)
4. ✅ Only use PostgreSQL (no MongoDB)

## Run Command

```bash
cd /Users/drenbuqa/Documents/GitHub/Smart-Grocery/Smart-Grocery-1

# Run in resume mode to add missing products and update offers
python3 scripts/billa_sitemap_to_postgres.py --workers 8 --chunk-size 300 --resume
```

### What This Does:
- `--workers 8`: Uses 8 parallel threads for faster scraping
- `--chunk-size 300`: Processes 300 products per batch
- `--resume`: Keeps existing data, only adds/updates what's missing

### Expected Duration:
- ~2-3 hours for full run (15,000 products)
- Progress updates every 500 products
- You can stop and restart anytime (it will resume where it left off)

## Monitoring Progress

The scraper will show:
```
[BILLA] Progress: 500/15000 | Inserted: 450 | Failed: 10 | Skipped: 40
[BILLA] Progress: 1000/15000 | Inserted: 920 | Failed: 15 | Skipped: 65
...
```

## After Running

Verify the results:
```bash
python3 scripts/verify_billa_data.py
```

You should see:
- ✅ ~15,000 total products
- ✅ Offers with promotional prices (10-20% of products typically on sale)
- ✅ Offer details populated
- ✅ Unit prices populated

## What Changed in the Code

### File: `scripts/billa_sitemap_to_postgres.py`

**New Features:**
1. **Complete Offer Extraction** - New `_extract_price_data()` function that captures:
   - Regular prices vs promotional prices
   - Discount percentages
   - Special offers (2+1, etc.)
   - Quantity-based pricing
   - Unit prices

2. **Better Reliability**:
   - 5 retries instead of 3
   - 60-second timeout instead of 45
   - Better error handling
   - Handles removed/redirected products

3. **Enhanced Logging**:
   - Separate counters for inserted/failed/skipped
   - Progress every 500 products
   - Final summary statistics

4. **Database Updates**:
   - Properly saves to `base_price`, `promo_price`, `unit_price`, `offer_details`, `min_quantity`
   - Updates existing offers with new data
   - Tracks price history

## Troubleshooting

### If scraper fails:
Just run the same command again with `--resume` - it will continue where it left off.

### If you want to start fresh:
```bash
# WARNING: This deletes all Billa data!
python3 scripts/billa_sitemap_to_postgres.py --workers 8 --chunk-size 300
```
(Without `--resume` flag, it clears existing data)

### If you want faster scraping:
Run 4 parallel processes (each handles 1/4 of products):

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

This will complete in ~30-45 minutes instead of 2-3 hours.

## Database Schema

The offers table now properly uses these fields:

```sql
offers (
    id                  SERIAL PRIMARY KEY,
    product_id          INTEGER,
    store_id            TEXT,
    price               NUMERIC(10,2),  -- Legacy (for compatibility)
    base_price          NUMERIC(10,2),  -- ✅ Regular price
    promo_price         NUMERIC(10,2),  -- ✅ Promotional price
    unit_price          TEXT,           -- ✅ e.g., "€1.99/kg"
    offer_details       TEXT,           -- ✅ e.g., "-30%", "2+1 gratis"
    min_quantity        INTEGER,        -- ✅ Min qty for promo
    product_url         TEXT,
    is_available        BOOLEAN,
    last_seen           TIMESTAMP,
    created_at          TIMESTAMP,
    updated_at          TIMESTAMP
)
```

## Questions?

Check `BILLA_SCRAPER_IMPROVEMENTS.md` for detailed technical documentation.
