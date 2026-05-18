# SPAR Scraper - Quick Start Guide

## 🚀 Quick Start (3 Steps)

### 1. Test the Scraper
```bash
python run_spar_scraper.py --test --dry-run
```
This will scrape 2 pages without saving to database.

### 2. Run a Small Test with Database
```bash
python run_spar_scraper.py --max-pages 5
```
This will scrape 5 pages and save to database.

### 3. Run Full Scrape
```bash
python run_spar_scraper.py
```
This will scrape all products from SPAR.

## 📋 Common Commands

| Command | Description |
|---------|-------------|
| `python run_spar_scraper.py --test` | Test mode (2 pages only) |
| `python run_spar_scraper.py --dry-run` | Scrape without saving |
| `python run_spar_scraper.py --max-pages 10` | Limit to 10 pages |
| `python run_spar_scraper.py --delay 2.0` | 2 second delay between requests |

## ✅ What Gets Scraped

- ✅ Product names
- ✅ Brands
- ✅ Current prices
- ✅ Original prices (for sales)
- ✅ Discount percentages
- ✅ Offer end dates
- ✅ Product images
- ✅ Product URLs
- ✅ Unit information (g, kg, L, ml)

## 🔒 Safety Features

- ✅ **No data replacement** - Only adds new products
- ✅ **Validation** - All data validated before insertion
- ✅ **Error recovery** - Continues on errors
- ✅ **Rate limiting** - Respectful delays between requests
- ✅ **Transaction safety** - Rollback on database errors

## 📊 Expected Output

```
╔═══════════════════════════════════════════════════════════════╗
║              SPAR AUSTRIA SCRAPER                             ║
╚═══════════════════════════════════════════════════════════════╝

[*] Scraping SPAR page 1...
[*] Found 24 products
[+] New product: SPAR Vollmilch 3,5% 1L
[+] New product: S-BUDGET Butter 250g
...

╔═══════════════════════════════════════════════════════════════╗
║                   OPERATION COMPLETE                          ║
╚═══════════════════════════════════════════════════════════════╝

SCRAPING RESULTS:
  Products scraped:        487
  
DATABASE OPERATIONS:
  Products added:          412
  Products updated:        75
  Promotions added:        89

[✓] All products successfully saved to database!
```

## 🐛 Troubleshooting

### No products found?
1. Check internet connection
2. Try: `python run_spar_scraper.py --test --dry-run`
3. Verify SPAR website is accessible

### Database errors?
1. Check `.env` file has correct `DATABASE_URL`
2. Verify database is running
3. Check database schema is up to date

### Too slow?
1. Reduce delay: `--delay 1.0`
2. Limit pages: `--max-pages 20`

## 📖 Full Documentation

See `SPAR_SCRAPER_GUIDE.md` for complete documentation.

## 🎯 Next Steps

After scraping:
1. Check products in database: `SELECT COUNT(*) FROM products WHERE fingerprint LIKE '%spar%';`
2. View SPAR products in app: Navigate to Browse → Filter by SPAR
3. Check promotions: Navigate to Deals → SPAR offers

---

**Need help?** Check `SPAR_SCRAPER_GUIDE.md` for detailed documentation.
