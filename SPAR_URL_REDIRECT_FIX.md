# SPAR URL Redirect Issue - Fix

## 🔴 Problem You Found

When navigating to page 2, SPAR automatically redirects back to page 1:
```
Navigate to: https://www.spar.at/produktwelt/suche?search=&page=2
Redirects to: https://www.spar.at/produktwelt/suche (page 1)
```

This is why you're getting the same 32 products on every page!

## 🔍 Step 1: Test URL Behavior (2 minutes)

Run this to see exactly what's happening:

```bash
python3 test_spar_url_redirect.py
```

This will:
- Test different URL formats
- Show you which ones work
- Test clicking pagination
- Tell you the best approach

**Watch the browser** - you'll see if SPAR redirects or not.

## 🛠️ Step 2: Try the Session-Based Scraper

I created a new scraper that:
1. Visits homepage first (establishes session)
2. Accepts cookies
3. Navigates naturally to products
4. Interacts with page (scrolls)
5. THEN starts scraping

This makes SPAR think you're a real user!

### Test it (10 pages):
```bash
python3 -c "
from scrapers.spar_session_scraper import SparSessionScraper
from app import app
from models.postgres_models import db

with app.app_context():
    scraper = SparSessionScraper(headless=False)  # Visible
    products = scraper.scrape_all_products(max_pages=10, delay=2.0)
    
    if products:
        print(f'\n✓ Got {len(products)} unique products')
        scraper.save_to_database(products, db.session)
    else:
        print('\n❌ Still not working')
"
```

**Watch for:**
- Does it stay on page 2 or redirect to page 1?
- Do you see different products on each page?
- Does the product count increase?

## 📊 What to Expect

### If Session Scraper Works:
```
[*] Establishing session with SPAR...
    [1/4] Visiting homepage...
    [2/4] Handling cookies...
        ✓ Accepted cookies
    [3/4] Navigating to products...
    [4/4] Interacting with page...
[✓] Session established successfully

[*] Page 1/10
    Already on page 1
[✓] Page 1 | New: 32 | Total: 32
    First: Schloss Fels...

[*] Page 2/10
    ✓ Navigated to page 2
[✓] Page 2 | New: 28 | Total: 60  ← Different products!
    First: SPAR Torten...
```

### If Still Redirecting:
```
[*] Page 2/10
    ✗ Redirected from page 2
    [!] Could not navigate to page 2
```

## 💡 Why This Happens

SPAR's bot protection checks:
1. **Session cookies** - Do you have a valid session?
2. **Referrer** - Did you come from their homepage?
3. **Behavior** - Are you scrolling, waiting, acting human?
4. **Automation flags** - Are you using Playwright/Selenium?

The session scraper addresses all of these!

## 🎯 Quick Test Commands

### 1. Test URL Redirect Behavior
```bash
python3 test_spar_url_redirect.py
```

### 2. Test Session Scraper (10 pages)
```bash
python3 scrapers/spar_session_scraper.py
```

### 3. Check Current Progress
```bash
python3 check_spar_progress.py
```

## 📁 Files Created

1. **`test_spar_url_redirect.py`** - Test URL behavior and redirects
2. **`scrapers/spar_session_scraper.py`** - Session-based scraper
3. **`SPAR_URL_REDIRECT_FIX.md`** - This guide

## 🚀 Next Steps

### Step 1: Run URL Test
```bash
python3 test_spar_url_redirect.py
```

This will tell you:
- Which URL format works (if any)
- If clicking pagination works
- What approach to use

### Step 2: Based on Results

**If URL navigation works:**
- Use the session scraper with URL navigation
- Should get all products

**If clicking works:**
- Use the click-based scraper
- Should get all products

**If neither works:**
- SPAR has very strong bot protection
- Options:
  1. Try undetected-chromedriver
  2. Use slower delays (5+ seconds)
  3. Focus on other stores (Billa, Hofer, Lidl)
  4. Contact SPAR for API access

## 🔬 Understanding the Redirect

### Why SPAR Redirects

```
User visits: /produktwelt/suche?page=2
SPAR checks: Do you have a valid session?
SPAR sees: No session cookies
SPAR thinks: This is a bot!
SPAR redirects: Back to page 1
```

### How Session Scraper Fixes It

```
1. Visit homepage → Get cookies
2. Accept cookie banner → Show you're interactive
3. Navigate to products → Natural flow
4. Scroll and wait → Human behavior
5. Now visit page 2 → SPAR allows it!
```

## ⚡ Quick Summary

**Problem**: SPAR redirects page 2 → page 1 (bot protection)

**Solution**: Establish session first, then scrape

**Test**: `python3 test_spar_url_redirect.py`

**Try**: `python3 scrapers/spar_session_scraper.py`

**Result**: Should get different products on each page!

---

Run the URL test first and let me know what it shows! 🔍
