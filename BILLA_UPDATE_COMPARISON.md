# Billa Scraper - Update Strategy Comparison

## 🔄 Three Update Strategies

### 1. Full Scrape (Without --resume)
**Command:** `python3 scripts/billa_sitemap_to_postgres.py`

❌ **NOT RECOMMENDED** - Deletes all existing data!

```
What it does:
  1. TRUNCATE products, offers, price_history
  2. Scrape all 15,000 products from scratch
  3. Insert everything as new

Duration: 2-3 hours
Use case: Starting fresh (destroys existing data!)
```

---

### 2. Smart Resume (With --resume) ⭐ RECOMMENDED FOR FIRST RUN
**Command:** `python3 scripts/billa_sitemap_to_postgres.py --resume`

✅ **SMART UPDATE** - Only changes what's needed!

```
What it does:
  1. Load existing products with current prices
  2. For each product in sitemap:
     
     IF product doesn't exist:
       → INSERT new product + offer (NEW)
     
     ELSE IF price or offer changed:
       → UPDATE offer only (UPDATED)
     
     ELSE:
       → SKIP (no changes needed)

Duration: 2-3 hours (checks all, updates only what changed)
Use case: First run, adding missing products, comprehensive update
```

**Example output:**
```
[BILLA] Progress: 5000/15000 | New: 1,234 | Updated: 2,456 | Skipped: 1,310
[BILLA] Progress: 10000/15000 | New: 2,345 | Updated: 4,567 | Skipped: 3,088
[BILLA] Done. New products: 2,609 | Updated: 8,234
```

---

### 3. Fast Offer Update ⚡ RECOMMENDED FOR REGULAR UPDATES
**Command:** `python3 scripts/billa_update_offers_only.py`

✅ **FASTEST** - Updates only prices and offers!

```
What it does:
  1. Load existing products from database
  2. For each product:
     - Fetch ONLY price data (not full product page)
     - Compare with current offer
     - Update if changed, skip if same

Duration: 30-45 minutes (3-4x faster!)
Use case: Daily/weekly price updates after initial scrape
```

**Example output:**
```
[BILLA] Progress: 5000/15000 | Updated: 1,234 | Unchanged: 3,766
[BILLA] Progress: 10000/15000 | Updated: 2,456 | Unchanged: 7,544
[BILLA] Offer update complete!
  Total products: 15,000
  Updated: 3,456
  Unchanged: 11,544
```

---

## 📊 Comparison Table

| Feature | Full Scrape | Smart Resume | Fast Offer Update |
|---------|-------------|--------------|-------------------|
| **Keeps existing data** | ❌ No | ✅ Yes | ✅ Yes |
| **Adds missing products** | ✅ Yes | ✅ Yes | ❌ No |
| **Updates prices** | ✅ Yes | ✅ Yes | ✅ Yes |
| **Updates offers** | ✅ Yes | ✅ Yes | ✅ Yes |
| **Skips unchanged** | ❌ No | ✅ Yes | ✅ Yes |
| **Duration** | 2-3 hours | 2-3 hours | 30-45 min |
| **Efficiency** | Low | Medium | High |
| **Safe to run** | ⚠️ Dangerous | ✅ Safe | ✅ Safe |

---

## 🎯 Recommended Workflow

### Step 1: Initial Setup (Do Once)
```bash
# Use Smart Resume to add missing products and update all offers
python3 scripts/billa_sitemap_to_postgres.py --workers 8 --resume
```

**What happens:**
- Adds ~2,609 missing products
- Updates prices/offers for products that changed
- Skips products that haven't changed
- Takes 2-3 hours

---

### Step 2: Regular Updates (Daily/Weekly)
```bash
# Use Fast Offer Update for quick price refreshes
python3 scripts/billa_update_offers_only.py --workers 12
```

**What happens:**
- Updates only prices and offers
- Skips unchanged products
- Takes 30-45 minutes
- Perfect for keeping prices current

---

### Step 3: Monthly Check (Optional)
```bash
# Run Smart Resume again to catch any new products
python3 scripts/billa_sitemap_to_postgres.py --workers 8 --resume
```

**What happens:**
- Adds any new products Billa added
- Updates all prices/offers
- Takes 2-3 hours

---

## 💡 Decision Guide

### Use **Smart Resume** when:
- ✅ First time running after improvements
- ✅ Adding missing products
- ✅ Haven't updated in a while (weeks/months)
- ✅ Want comprehensive update
- ✅ Checking for new products

### Use **Fast Offer Update** when:
- ✅ Regular price updates (daily/weekly)
- ✅ Already have all products
- ✅ Just want to refresh offers
- ✅ Need quick updates
- ✅ Running frequently

### Use **Full Scrape** when:
- ⚠️ Starting completely fresh
- ⚠️ Database is corrupted
- ⚠️ Want to delete everything and start over
- ⚠️ **WARNING: Destroys all existing data!**

---

## 🔍 What Gets Updated

### Smart Resume Updates:

**For NEW products:**
```
✅ Product: name, brand, category, image, unit, size
✅ Offer: base_price, promo_price, unit_price, offer_details, min_quantity
✅ Price History: initial price entry
```

**For EXISTING products with changes:**
```
❌ Product: NOT touched (keeps existing data)
✅ Offer: base_price, promo_price, unit_price, offer_details, min_quantity
✅ Price History: new entry if price changed
```

**For EXISTING products without changes:**
```
❌ Nothing updated (skipped for efficiency)
```

---

### Fast Offer Update:

**For ALL existing products:**
```
❌ Product: NOT touched (never updates product data)
✅ Offer: base_price, promo_price, unit_price, offer_details, min_quantity
✅ Price History: new entry if price changed
```

---

## 📈 Performance Comparison

### Current Database: 12,391 products

**Scenario 1: First run with Smart Resume**
```
Expected:
  - New products: ~2,609
  - Updated offers: ~8,000 (prices/promotions changed)
  - Skipped: ~1,782 (no changes)
  - Duration: 2-3 hours
```

**Scenario 2: Daily update with Fast Offer**
```
Expected:
  - Updated offers: ~500-1,000 (typical daily changes)
  - Unchanged: ~14,000-14,500
  - Duration: 30-45 minutes
```

**Scenario 3: Weekly update with Fast Offer**
```
Expected:
  - Updated offers: ~2,000-3,000 (weekly changes)
  - Unchanged: ~12,000-13,000
  - Duration: 30-45 minutes
```

---

## 🛡️ Data Safety

### Smart Resume Safety:
```
✅ Never deletes products
✅ Never replaces product data
✅ Only updates offers when changed
✅ Preserves price history
✅ Can be stopped and restarted
✅ Idempotent (safe to run multiple times)
```

### Fast Offer Update Safety:
```
✅ Never touches product data
✅ Only updates offer table
✅ Preserves price history
✅ Can be stopped and restarted
✅ Idempotent (safe to run multiple times)
✅ Fastest and safest for regular updates
```

---

## 🎓 Examples

### Example 1: First Time Setup
```bash
# Current state: 12,391 products, no offer data

# Run Smart Resume
python3 scripts/billa_sitemap_to_postgres.py --resume

# Result:
#   - 15,000 products (added 2,609)
#   - All offers populated with prices, promotions, unit prices
#   - Duration: 2-3 hours
```

---

### Example 2: Daily Price Update
```bash
# Current state: 15,000 products, offers from yesterday

# Run Fast Offer Update
python3 scripts/billa_update_offers_only.py

# Result:
#   - 15,000 products (unchanged)
#   - ~800 offers updated (prices changed)
#   - ~14,200 offers unchanged (skipped)
#   - Duration: 35 minutes
```

---

### Example 3: Weekly Update
```bash
# Current state: 15,000 products, offers from last week

# Run Fast Offer Update
python3 scripts/billa_update_offers_only.py

# Result:
#   - 15,000 products (unchanged)
#   - ~2,500 offers updated (prices/promotions changed)
#   - ~12,500 offers unchanged (skipped)
#   - Duration: 40 minutes
```

---

### Example 4: Monthly Comprehensive Update
```bash
# Current state: 15,000 products, offers from last month

# Run Smart Resume
python3 scripts/billa_sitemap_to_postgres.py --resume

# Result:
#   - 15,234 products (added 234 new products)
#   - ~5,000 offers updated (prices/promotions changed)
#   - ~10,234 offers unchanged (skipped)
#   - Duration: 2.5 hours
```

---

## ✅ Summary

**For your situation (12,391 products, missing offers):**

1. **First, run Smart Resume:**
   ```bash
   python3 scripts/billa_sitemap_to_postgres.py --resume
   ```
   - Adds missing 2,609 products
   - Updates all offers with prices, promotions, unit prices
   - Takes 2-3 hours

2. **Then, use Fast Offer Update for regular updates:**
   ```bash
   python3 scripts/billa_update_offers_only.py
   ```
   - Updates only prices/offers
   - Takes 30-45 minutes
   - Run daily or weekly

**Result:** Efficient, safe, and never replaces existing data!
