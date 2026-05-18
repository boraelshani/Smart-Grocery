# 🚀 SPAR Scraper - Installation & First Run

## ⚡ Quick Install (2 Minutes)

### Step 1: Install Playwright
```bash
pip install playwright
```

### Step 2: Install Chromium Browser
```bash
playwright install chromium
```

### Step 3: Test Installation
```bash
python3 -c "from playwright.sync_api import sync_playwright; print('✅ Playwright installed successfully!')"
```

## 🎯 First Run (Test Mode)

### Run with visible browser (see what's happening):
```bash
python3 run_spar_playwright_scraper.py --test --visible --dry-run
```

**What this does:**
- Opens a browser window (you can watch!)
- Scrapes 2 pages from SPAR
- Shows you the products found
- Does NOT save to database (dry-run)

**Expected output:**
```
╔═══════════════════════════════════════════════════════════════╗
║          SPAR AUSTRIA SCRAPER (PLAYWRIGHT)                    ║
╚═══════════════════════════════════════════════════════════════╝

[*] Starting browser...
[✓] Browser started
[*] Scraping page 1...
[*] Found 24 products
[✓] Extracted 24 products from page 1

SAMPLE PRODUCTS (first 5)
================================================================================

1. SPAR Vollmilch 3,5% 1L
   Brand: SPAR
   Price: €1.29
   Original Price: €1.49 (-13%)
   Offer ends: 24.05.2026
   Unit: l 1.0

[*] DRY RUN MODE: Skipping database insertion
[*] Would have inserted 48 products
```

## ✅ If Test Succeeds

### Run a small database test (5 pages):
```bash
python3 run_spar_playwright_scraper.py --max-pages 5
```

**What this does:**
- Scrapes 5 pages
- Saves products to database
- Shows statistics

### Check the results:
```bash
python3 -c "
from app import app
from models.postgres_models import db, Product, ProductStore
with app.app_context():
    count = db.session.query(Product).join(ProductStore).filter(
        ProductStore.store_id == 'spar'
    ).count()
    print(f'✅ SPAR products in database: {count}')
"
```

## 🚀 Full Production Run

### Scrape all SPAR products:
```bash
python3 run_spar_playwright_scraper.py
```

**This will:**
- Scrape all pages (might take 20-30 minutes)
- Save all products to database
- Show detailed statistics

## ❌ If Something Goes Wrong

### Error: "Playwright not installed"
```bash
pip install playwright
playwright install chromium
```

### Error: "Browser won't start"
```bash
# Reinstall Playwright browsers
playwright install chromium

# On Linux, install dependencies
playwright install-deps
```

### Error: "Database connection failed"
Check your `.env` file:
```bash
cat .env | grep DATABASE_URL
```

Should show something like:
```
DATABASE_URL=postgresql://user:pass@host/database
```

### Error: "No products found"
1. Check if SPAR website is accessible:
   ```bash
   curl -I https://www.spar.at
   ```
2. Run with visible browser to see what's happening:
   ```bash
   python3 run_spar_playwright_scraper.py --test --visible
   ```

## 📋 Command Reference

### Test Commands
```bash
# Test with visible browser, no database
python3 run_spar_playwright_scraper.py --test --visible --dry-run

# Test with headless browser, no database
python3 run_spar_playwright_scraper.py --test --dry-run

# Test with database (2 pages)
python3 run_spar_playwright_scraper.py --test
```

### Production Commands
```bash
# Scrape 10 pages
python3 run_spar_playwright_scraper.py --max-pages 10

# Scrape all pages with 3-second delay
python3 run_spar_playwright_scraper.py --delay 3.0

# Full scrape (all products)
python3 run_spar_playwright_scraper.py
```

### Diagnostic Commands
```bash
# Test Playwright installation
python3 -c "from playwright.sync_api import sync_playwright; print('Playwright OK')"

# Test database connection
python3 -c "from app import app; from models.postgres_models import db; app.app_context().push(); print('Database OK')"

# Test scraper import
python3 -c "from scrapers.spar_playwright_scraper import SparPlaywrightScraper; print('Scraper OK')"

# Count SPAR products in database
python3 -c "from app import app; from models.postgres_models import db, ProductStore; app.app_context().push(); print(f'SPAR products: {ProductStore.query.filter_by(store_id=\"spar\").count()}')"
```

## 🎯 Recommended First-Time Flow

### 1. Install (2 minutes)
```bash
pip install playwright
playwright install chromium
```

### 2. Test Installation (10 seconds)
```bash
python3 -c "from playwright.sync_api import sync_playwright; print('✅ Ready!')"
```

### 3. Test Scraper - Visible (1 minute)
```bash
python3 run_spar_playwright_scraper.py --test --visible --dry-run
```
Watch the browser scrape products!

### 4. Test Scraper - Headless (1 minute)
```bash
python3 run_spar_playwright_scraper.py --test --dry-run
```
Faster, no browser window.

### 5. Small Database Test (2 minutes)
```bash
python3 run_spar_playwright_scraper.py --max-pages 5
```
Scrape 5 pages and save to database.

### 6. Check Results (10 seconds)
```bash
python3 -c "from app import app; from models.postgres_models import db, ProductStore; app.app_context().push(); print(f'Products: {ProductStore.query.filter_by(store_id=\"spar\").count()}')"
```

### 7. Full Production Run (20-30 minutes)
```bash
python3 run_spar_playwright_scraper.py
```
Scrape all SPAR products!

## 📊 What to Expect

### Test Run (2 pages):
- Time: ~30 seconds
- Products: ~40-50
- Database size: +50 rows

### Small Run (5 pages):
- Time: ~2 minutes
- Products: ~100-120
- Database size: +120 rows

### Full Run (all pages):
- Time: ~20-30 minutes
- Products: ~400-600
- Database size: +600 rows

## ✅ Success Indicators

### You'll know it's working when you see:
```
[✓] Browser started
[*] Found 24 products
[✓] Extracted 24 products from page 1
[+] New product: SPAR Vollmilch 3,5% 1L
```

### You'll know it succeeded when you see:
```
╔═══════════════════════════════════════════════════════════════╗
║                   OPERATION COMPLETE                          ║
╚═══════════════════════════════════════════════════════════════╝

[✓] All products successfully saved to database!
```

## 🆘 Need Help?

### Read the documentation:
- **SPAR_README.md** - Main documentation
- **SPAR_QUICK_START.md** - Quick reference
- **SPAR_SCRAPER_GUIDE.md** - Complete guide

### Run diagnostics:
```bash
# Test everything
python3 -c "
from playwright.sync_api import sync_playwright
from app import app
from models.postgres_models import db
from scrapers.spar_playwright_scraper import SparPlaywrightScraper

print('Testing...')
print('✅ Playwright: OK')
app.app_context().push()
print('✅ Database: OK')
print('✅ Scraper: OK')
print('All systems ready!')
"
```

## 🎉 You're Ready!

Just run:
```bash
pip install playwright
playwright install chromium
python3 run_spar_playwright_scraper.py --test --visible --dry-run
```

**That's it! Happy scraping! 🚀**

---

**Installation Time**: 2 minutes  
**First Test**: 1 minute  
**Full Scrape**: 20-30 minutes  
**Difficulty**: Easy ⭐⭐☆☆☆
