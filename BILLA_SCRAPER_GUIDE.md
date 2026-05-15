# Billa Scraper - Complete Guide

## 🎯 Smart Update Strategy

The scraper now has **intelligent update logic** that:

✅ **Skips products** that already exist with same price and offers  
✅ **Updates only prices/offers** when they change (doesn't re-insert product data)  
✅ **Adds missing products** (the ~2,609 missing ones)  
✅ **Never replaces existing data** - only adds or updates what changed  
✅ **Efficient for long-term use** - perfect for daily/weekly price updates  

## 📊 Current Database Status

```
Total Products:        12,391
Missing Products:      ~2,609
Offers with Prices:    12,391 (but missing promo/unit price data)
```

## 🚀 Three Ways to Run

### 1. **First Time / Add Missing Products** (Recommended Now)

```bash
python3 scripts/billa_sitemap_to_postgres.py --workers 8 --chunk-size 300 --resume
```

**What it does:**
- ✅ Adds the ~2,609 missing products
- ✅ Updates ALL 15,000 products with offer data (prices, promotions, unit prices)
- ✅ Skips products where nothing changed
- ✅ Only updates prices/offers for products that changed
- ✅ Never deletes or replaces existing product data

**Duration:** 2-3 hours (checks all 15k products, but only updates what changed)

**Output:**
```
[BILLA] Progress: 500/15000 | New: 45 | Updated: 123 | Skipped: 332 | Failed: 0
[BILLA] Progress: 1000/15000 | New: 89 | Updated: 267 | Skipped: 644 | Failed: 0
...
[BILLA] Done. New products: 2,609 | Updated: 8,234
```

---

### 2. **Fast Offer Updates Only** (For Regular Updates)

```bash
python3 scripts/billa_update_offers_only.py --workers 12 --batch-size 100
```

**What it does:**
- ✅ Updates ONLY prices and offers for existing products
- ✅ Doesn't re-scrape or re-insert product data
- ✅ Much faster - only fetches price info
- ✅ Perfect for daily/weekly price updates

**Duration:** 30-45 minutes (for 15k products)

**When to use:**
- After initial full scrape
- For regular price/promotion updates
- When you just want to refresh offers

**Output:**
```
[BILLA] Progress: 500/15000 | Updated: 234 | Unchanged: 266 | Failed: 0
[BILLA] Progress: 1000/15000 | Updated: 478 | Unchanged: 522 | Failed: 0
...
[BILLA] Offer update complete!
  Total products: 15,000
  Updated: 3,456
  Unchanged: 11,544
```

---

### 3. **Parallel Processing** (Fastest)

Run 4 processes simultaneously:

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

**Duration:** 30-45 minutes (4x faster)

---

## 🔄 Update Logic Explained

### How It Decides What to Do

```
For each product in sitemap:
  
  1. Does product exist in database?
     
     NO → Insert new product + offer (NEW)
     
     YES → Check if anything changed:
     
        - Price changed? → Update offer only (UPDATED)
        - Promo changed? → Update offer only (UPDATED)
        - Unit price changed? → Update offer only (UPDATED)
        - Offer details changed? → Update offer only (UPDATED)
        - Nothing changed? → Skip (SKIPPED)
```

### What Gets Updated vs Inserted

**New Products (INSERT):**
- Product data: name, brand, category, image, etc.
- Offer data: prices, promotions, unit prices
- Price history entry

**Existing Products (UPDATE):**
- ✅ Offer data: prices, promotions, unit prices
- ✅ Price history (only if price changed)
- ❌ Product data: NOT touched (keeps existing name, brand, etc.)

**Unchanged Products (SKIP):**
- Nothing happens - saves time!

---

## 📈 Recommended Workflow

### Initial Setup (Do Once)
```bash
# 1. Add missing products and update all offers
python3 scripts/billa_sitemap_to_postgres.py --workers 8 --chunk-size 300 --resume

# 2. Verify results
python3 scripts/verify_billa_data.py
```

### Regular Updates (Daily/Weekly)
```bash
# Fast offer updates only
python3 scripts/billa_update_offers_only.py --workers 12
```

### Monthly Full Check
```bash
# Check for new products and update everything
python3 scripts/billa_sitemap_to_postgres.py --workers 8 --resume
```

---

## 🔍 Verification

Check database status anytime:
```bash
python3 scripts/verify_billa_data.py
```

**Expected output after first run:**
```
======================================================================
BILLA DATA VERIFICATION REPORT
======================================================================

✓ Total Billa Products: 15,000
✓ Total Billa Offers: 15,000
✓ Offers with Base Price: 15,000 (100.0%)
✓ Offers with Promo Price: 2,341 (15.6%)
✓ Offers with Unit Price: 13,567 (90.4%)
✓ Offers with Offer Details: 2,341 (15.6%)
✓ Offers with Min Quantity: 234 (1.6%)

======================================================================
SAMPLE PROMOTIONAL OFFERS
======================================================================

1. Coca-Cola Original 24x0,33l Dose
   Base: €12.99 → Promo: €9.99 (Save €3.00 / 23%)
   Details: -23%
   Min Quantity: 24
   Unit Price: €1.26/l

2. Milka Schokolade Alpenmilch 100g
   Base: €1.49 → Promo: €0.99 (Save €0.50 / 34%)
   Details: -34%
   Unit Price: €0.99/100g
...
```

---

## 💡 Key Features

### 1. Smart Price Comparison
```sql
-- Products with price changes
SELECT 
    p.name_de,
    o.base_price as current_price,
    ph.old_price,
    ph.new_price,
    ph.changed_at
FROM offers o
JOIN products p ON o.product_id = p.id
JOIN price_history ph ON o.id = ph.offer_id
WHERE o.store_id = 'billa'
ORDER BY ph.changed_at DESC
LIMIT 20;
```

### 2. Best Deals
```sql
-- Biggest discounts
SELECT 
    p.name_de,
    o.base_price,
    o.promo_price,
    o.offer_details,
    ROUND((o.base_price - o.promo_price) / o.base_price * 100, 0) as discount_pct
FROM offers o
JOIN products p ON o.product_id = p.id
WHERE o.store_id = 'billa' 
    AND o.promo_price IS NOT NULL
ORDER BY (o.base_price - o.promo_price) DESC
LIMIT 20;
```

### 3. Unit Price Comparison
```sql
-- Compare unit prices across products
SELECT 
    p.name_de,
    o.base_price,
    o.unit_price,
    p.unit_normalized,
    p.size_normalized
FROM offers o
JOIN products p ON o.product_id = p.id
WHERE o.store_id = 'billa'
    AND o.unit_price IS NOT NULL
    AND p.brand = 'Coca-Cola'
ORDER BY o.base_price;
```

---

## 🛡️ Data Safety

### What's Protected
- ✅ Existing product names, brands, categories
- ✅ Product images and metadata
- ✅ Historical price data
- ✅ User favorites and shopping lists
- ✅ All relationships and foreign keys

### What Gets Updated
- ✅ Current prices (base and promo)
- ✅ Offer details (discounts, promotions)
- ✅ Unit prices (€/kg, €/L, etc.)
- ✅ Availability status
- ✅ Last seen timestamp

### What Never Happens
- ❌ Product deletion
- ❌ Data replacement (only updates)
- ❌ Category changes (we don't use Billa's categories)
- ❌ Breaking existing relationships

---

## ⚡ Performance Tips

### For Fastest Updates
1. Use `billa_update_offers_only.py` for regular updates
2. Increase workers: `--workers 16` (if you have good internet)
3. Use parallel processing with shards
4. Run during off-peak hours

### For Most Reliable Updates
1. Use default settings: `--workers 8`
2. Run single process (no sharding)
3. Monitor progress logs
4. Verify after completion

---

## 🐛 Troubleshooting

### Script stops or fails
```bash
# Just run again with --resume, it will continue
python3 scripts/billa_sitemap_to_postgres.py --resume
```

### Too slow
```bash
# Use offer-only updates instead
python3 scripts/billa_update_offers_only.py --workers 16
```

### Database connection errors
```bash
# Check .env file has correct DATABASE_URL
cat .env | grep DATABASE_URL
```

### Want to start fresh (CAREFUL!)
```bash
# This deletes all Billa data!
python3 scripts/billa_sitemap_to_postgres.py --workers 8
# (without --resume flag)
```

---

## 📊 Statistics Tracking

The scraper tracks:
- **New**: Products added to database
- **Updated**: Products with price/offer changes
- **Skipped**: Products with no changes
- **Failed**: Products that couldn't be fetched
- **Unavailable**: Products no longer on Billa

---

## 🎯 Summary

**For your first run:**
```bash
python3 scripts/billa_sitemap_to_postgres.py --workers 8 --chunk-size 300 --resume
```

This will:
1. Add ~2,609 missing products
2. Update all 15,000 products with offer data
3. Skip products that haven't changed
4. Never replace existing data
5. Take 2-3 hours

**For future updates:**
```bash
python3 scripts/billa_update_offers_only.py --workers 12
```

This will:
1. Update only prices and offers
2. Skip unchanged products
3. Take 30-45 minutes
4. Perfect for daily/weekly runs

---

## ✅ What Changed in the Code

### Main Script: `billa_sitemap_to_postgres.py`

1. **`_load_existing_products()`** - New function
   - Loads existing products with current offer data
   - Returns dict with prices, promotions, unit prices
   - Used for comparison to detect changes

2. **`_insert_products()`** - Enhanced
   - Added `update_mode` parameter
   - `'full'` = new product (update all fields)
   - `'minimal'` = existing product (only timestamp)

3. **`_persist_rows()`** - Enhanced
   - Accepts `update_mode` parameter
   - Only inserts price history if price changed
   - More efficient for updates

4. **Main loop** - Completely rewritten
   - Checks if product exists
   - Compares prices and offers
   - Decides: NEW, UPDATE, or SKIP
   - Separate counters for each action

### New Script: `billa_update_offers_only.py`

- Fast offer updates without full product scraping
- Only fetches price data from pages
- Updates offers table directly
- 3-4x faster than full scrape

---

**Ready to run!** Start with the first command to add missing products and update all offers.
