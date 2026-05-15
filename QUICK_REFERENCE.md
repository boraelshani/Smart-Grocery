# Smart Grocery - Quick Reference

## 🚀 Start the Application

```bash
python3 app.py
```

Then visit: **http://localhost:5000**

---

## 📊 Current Status

✅ **12,392 products** in database  
✅ **1,060 promotional offers** active  
✅ **49 unique promotions** running  
✅ **All systems operational**

---

## 🔗 Important URLs

| Page | URL |
|------|-----|
| Homepage | http://localhost:5000 |
| Deals (1,060 offers) | http://localhost:5000/featured-deals |
| Compare Prices | http://localhost:5000/compare-prices |
| Shopping Lists | http://localhost:5000/shopping-list |
| Admin Panel | http://localhost:5000/admin |

---

## 🛠️ Useful Commands

### Check Database Status
```bash
python3 scripts/check_scraper_progress.py
```

### Check Scraper Status
```bash
# View scraper runs
psql $DATABASE_URL -c "SELECT * FROM scraper_runs ORDER BY created_at DESC LIMIT 5;"
```

### View Active Promotions
```bash
psql $DATABASE_URL -c "SELECT * FROM active_promotions_view LIMIT 10;"
```

### Count Products
```bash
psql $DATABASE_URL -c "SELECT COUNT(*) FROM products;"
```

### Count Promotional Offers
```bash
psql $DATABASE_URL -c "SELECT COUNT(*) FROM promotion_targets;"
```

---

## 📁 Key Files

### Models
- `models/postgres_models.py` - Database ORM models
- `models/products_model.py` - Product queries
- `models/deals_compat.py` - Promotions compatibility layer
- `models/featured_deals_model.py` - Deals interface

### Routes
- `routes/ui/deal.py` - Deals page
- `routes/compare/common.py` - Compare prices
- `routes/ui/product.py` - Product details

### Scripts
- `scripts/check_scraper_progress.py` - Check scraper status
- `scripts/billa_sitemap_to_postgres.py` - Main scraper
- `scripts/billa_update_offers_only.py` - Fast offer updates

### Migrations
- `migrations/001_database_restructure.sql` - Schema migration
- `migrations/003_migrate_promotional_offers.sql` - Offers migration

---

## 🗄️ Database Schema

### Main Tables
- **products** - Global product catalog (12,392 rows)
- **product_store** - Store-specific pricing (12,392 rows)
- **offers** - Reusable discount rules (1,000 rows)
- **promotions** - Time-bound campaigns (49 rows)
- **promotion_targets** - Links promotions to products (1,060 rows)

### Backup Tables
- **_backup_products** - Original products
- **_backup_offers** - Original offers
- **_old_offers** - Complete offer data

---

## 🎯 Top Promotional Offers

| Discount | Products |
|----------|----------|
| -33% | 270 products |
| -20% | 75 products |
| -28% | 61 products |
| -25% | 56 products |
| -27% | 45 products |

**Best Deals:** Up to 50% off on selected products!

---

## 🔍 Sample Queries

### Get Product with Prices
```sql
SELECT 
    p.name,
    ps.store_id,
    ps.base_price,
    s.name as store_name
FROM products p
JOIN product_store ps ON ps.product_id = p.id
JOIN stores s ON s.store_id = ps.store_id
WHERE p.id = 1;
```

### Get Active Promotions
```sql
SELECT * FROM active_promotions_view
WHERE discounted_price < base_price * 0.7
ORDER BY discounted_price ASC
LIMIT 10;
```

### Get Products on Sale
```sql
SELECT 
    p.name,
    COUNT(pt.promotion_id) as promotion_count
FROM products p
JOIN promotion_targets pt ON pt.product_id = p.id
GROUP BY p.id, p.name
ORDER BY promotion_count DESC
LIMIT 10;
```

---

## 🐛 Troubleshooting

### Application Won't Start
```bash
# Check Python version
python3 --version

# Install dependencies
pip3 install -r requirements.txt

# Check database connection
echo $DATABASE_URL
```

### No Deals Showing
```bash
# Check promotions
psql $DATABASE_URL -c "SELECT COUNT(*) FROM promotion_targets;"

# Should return: 1060
```

### Products Not Loading
```bash
# Check products
psql $DATABASE_URL -c "SELECT COUNT(*) FROM products;"

# Should return: 12392
```

---

## 📚 Documentation

- **DATABASE_MIGRATION_COMPLETE.md** - Detailed migration docs
- **FIXES_COMPLETE_SUMMARY.md** - All fixes summary
- **BILLA_SCRAPER_GUIDE.md** - Scraper documentation
- **README.md** - Project overview

---

## ✅ Verification Checklist

- [x] Database migrated to normalized schema
- [x] All 12,392 products preserved
- [x] All 1,060 promotional offers migrated
- [x] Application starts without errors
- [x] Deals page shows all offers
- [x] Compare prices working
- [x] Shopping lists working
- [x] No data loss

---

## 🎉 Success Metrics

| Metric | Value |
|--------|-------|
| Products | 12,392 |
| Promotional Offers | 1,060 |
| Active Promotions | 49 |
| Discount Rules | 1,000 |
| Data Preserved | 100% |
| Application Status | ✅ Ready |

---

**Last Updated:** May 15, 2026  
**Status:** ✅ All Systems Operational  
**Version:** 2.0 (Normalized Schema)
