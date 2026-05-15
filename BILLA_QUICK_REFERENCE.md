# Billa Scraper - Quick Reference

## 🚀 Commands

### First Time Setup
```bash
python3 scripts/billa_sitemap_to_postgres.py --resume
```
Duration: 2-3 hours | Adds missing products + updates all offers

### Regular Updates (Daily/Weekly)
```bash
python3 scripts/billa_update_offers_only.py
```
Duration: 30-45 min | Updates only prices/offers

### Check Status
```bash
python3 scripts/verify_billa_data.py
```
Shows: Product count, offer statistics, sample promotions

### Easy Mode
```bash
./scripts/run_billa_scraper.sh
```
Interactive helper with before/after verification

---

## 📊 What Each Command Does

| Command | New Products | Update Offers | Skip Unchanged | Duration |
|---------|--------------|---------------|----------------|----------|
| `--resume` | ✅ Yes | ✅ Yes | ✅ Yes | 2-3 hours |
| `update_offers_only` | ❌ No | ✅ Yes | ✅ Yes | 30-45 min |
| Without `--resume` | ⚠️ Deletes all! | ✅ Yes | ❌ No | 2-3 hours |

---

## 🎯 Decision Tree

```
Do you have all 15,000 products?
│
├─ NO → Use: billa_sitemap_to_postgres.py --resume
│        (Adds missing products + updates offers)
│
└─ YES → Do you need to check for new products?
         │
         ├─ YES → Use: billa_sitemap_to_postgres.py --resume
         │         (Monthly comprehensive check)
         │
         └─ NO → Use: billa_update_offers_only.py
                  (Fast daily/weekly price updates)
```

---

## 💡 Smart Update Logic

```
For each product:
  
  Doesn't exist? → INSERT (NEW)
  Price changed? → UPDATE offer only (UPDATED)
  Offer changed? → UPDATE offer only (UPDATED)
  Nothing changed? → SKIP
```

---

## 📈 Expected Results

### Current State
```
Products: 12,391
Missing: ~2,609
Offers: 0 with promo data
```

### After First Run
```
Products: 15,000 ✅
Offers: ~2,500 with promotions ✅
Unit Prices: ~13,500 ✅
```

---

## 🔧 Options

### Workers (Parallelism)
```bash
--workers 8   # Default (recommended)
--workers 12  # Faster (if good internet)
--workers 16  # Fastest (may hit rate limits)
```

### Parallel Processing
```bash
# Run 4 processes (4x faster)
--shard-count 4 --shard-index 0  # Terminal 1
--shard-count 4 --shard-index 1  # Terminal 2
--shard-count 4 --shard-index 2  # Terminal 3
--shard-count 4 --shard-index 3  # Terminal 4
```

---

## 🛡️ Safety

### Safe Commands
```bash
✅ --resume                    # Never deletes
✅ update_offers_only.py       # Never deletes
✅ verify_billa_data.py        # Read-only
```

### Dangerous Command
```bash
⚠️ Without --resume            # DELETES ALL DATA!
```

---

## 📊 Monitoring

### Progress Output
```
[BILLA] Progress: 5000/15000 | New: 1,234 | Updated: 2,456 | Skipped: 1,310
```

- **New**: Products added
- **Updated**: Offers changed
- **Skipped**: No changes
- **Failed**: Errors

---

## 🎓 Common Scenarios

### Scenario 1: First Time
```bash
python3 scripts/billa_sitemap_to_postgres.py --resume
# Adds 2,609 products + updates all offers
# Duration: 2-3 hours
```

### Scenario 2: Daily Update
```bash
python3 scripts/billa_update_offers_only.py
# Updates ~800 offers
# Duration: 35 minutes
```

### Scenario 3: Weekly Update
```bash
python3 scripts/billa_update_offers_only.py
# Updates ~2,500 offers
# Duration: 40 minutes
```

### Scenario 4: Monthly Check
```bash
python3 scripts/billa_sitemap_to_postgres.py --resume
# Adds new products + updates offers
# Duration: 2-3 hours
```

---

## 🔍 Verification Queries

### Check Product Count
```sql
SELECT COUNT(*) FROM products WHERE store_id = 'billa';
```

### Check Promotional Offers
```sql
SELECT COUNT(*) FROM offers 
WHERE store_id = 'billa' AND promo_price IS NOT NULL;
```

### Best Deals
```sql
SELECT p.name_de, o.base_price, o.promo_price, o.offer_details
FROM offers o
JOIN products p ON o.product_id = p.id
WHERE o.store_id = 'billa' AND o.promo_price IS NOT NULL
ORDER BY (o.base_price - o.promo_price) DESC
LIMIT 10;
```

---

## 🐛 Troubleshooting

### Script Stops
```bash
# Just run again, it will resume
python3 scripts/billa_sitemap_to_postgres.py --resume
```

### Too Slow
```bash
# Use fast offer update instead
python3 scripts/billa_update_offers_only.py
```

### Database Error
```bash
# Check connection
cat .env | grep DATABASE_URL
```

---

## 📅 Recommended Schedule

### Daily (Weekdays)
```bash
python3 scripts/billa_update_offers_only.py
```
30-45 minutes | Updates prices/promotions

### Weekly (Sunday)
```bash
python3 scripts/billa_update_offers_only.py
```
30-45 minutes | Catches weekly changes

### Monthly (1st of month)
```bash
python3 scripts/billa_sitemap_to_postgres.py --resume
```
2-3 hours | Comprehensive check for new products

---

## ✅ Quick Checklist

Before running:
- [ ] `.env` has DATABASE_URL
- [ ] Internet connection stable
- [ ] Python 3 installed

After running:
- [ ] Run `verify_billa_data.py`
- [ ] Check product count (~15,000)
- [ ] Check promotional offers (>0)

---

## 📞 Help

- **Full Guide**: `BILLA_SCRAPER_GUIDE.md`
- **Comparison**: `BILLA_UPDATE_COMPARISON.md`
- **Summary**: `BILLA_FINAL_SUMMARY.md`
- **This File**: Quick reference

---

## 🎯 TL;DR

**First time:**
```bash
python3 scripts/billa_sitemap_to_postgres.py --resume
```

**Regular updates:**
```bash
python3 scripts/billa_update_offers_only.py
```

**Check status:**
```bash
python3 scripts/verify_billa_data.py
```

**Done!** 🎉
