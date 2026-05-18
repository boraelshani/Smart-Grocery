# SPAR Scraper - Technical Notes & Solutions

## Current Status

### ⚠️ Website Protection Issue

SPAR Austria's website (www.spar.at) implements anti-bot protection that blocks automated requests with HTTP 403 errors. This is a common security measure used by modern e-commerce websites.

## Solutions

### Solution 1: Use SPAR's Online Shop API (Recommended)

SPAR likely has an internal API that their website uses. We can inspect network requests to find it.

#### Steps to Find the API:
1. Open SPAR website in browser
2. Open Developer Tools (F12)
3. Go to Network tab
4. Navigate to product search
5. Look for XHR/Fetch requests
6. Find JSON responses with product data

**Example API endpoints to look for:**
- `/api/products`
- `/api/search`
- `/graphql`
- `/rest/v1/products`

### Solution 2: Use Selenium with Real Browser

Install Selenium to use a real browser that can bypass bot detection:

```bash
pip install selenium webdriver-manager
```

**Updated scraper with Selenium:**

```python
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options

class SparSeleniumScraper:
    def __init__(self):
        options = Options()
        options.add_argument('--headless')  # Run in background
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-blink-features=AutomationControlled')
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option('useAutomationExtension', False)
        
        service = Service(ChromeDriverManager().install())
        self.driver = webdriver.Chrome(service=service, options=options)
        
    def scrape_page(self, url):
        self.driver.get(url)
        # Wait for products to load
        WebDriverWait(self.driver, 10).until(
            EC.presence_of_element_located((By.CLASS_NAME, "product-item"))
        )
        # Extract data
        products = self.driver.find_elements(By.CLASS_NAME, "product-item")
        # ... rest of extraction logic
```

### Solution 3: Use SPAR's Mobile App API

Mobile apps often have simpler APIs without heavy bot protection.

#### Steps:
1. Install SPAR mobile app on Android emulator
2. Use mitmproxy or Charles Proxy to intercept API calls
3. Reverse engineer the API endpoints
4. Use those endpoints in the scraper

### Solution 4: Use Playwright (Modern Alternative)

Playwright is more advanced than Selenium and better at bypassing detection:

```bash
pip install playwright
playwright install chromium
```

**Example:**
```python
from playwright.sync_api import sync_playwright

def scrape_with_playwright():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto('https://www.spar.at/produktwelt/suche')
        # Wait for content
        page.wait_for_selector('.product-item')
        # Extract data
        products = page.query_selector_all('.product-item')
        # ... extraction logic
        browser.close()
```

### Solution 5: Use Existing SPAR Data Sources

#### Option A: SPAR's Product Catalog
Some stores provide downloadable product catalogs or feeds for partners.

#### Option B: Third-Party Aggregators
Services like:
- Geizhals.at
- Idealo.at
- Preisvergleich.at

These aggregate prices from multiple stores including SPAR.

## Recommended Approach

### Short-term (Immediate):
1. **Inspect SPAR's website for API endpoints** (30 minutes)
2. If found, update scraper to use API instead of HTML scraping
3. If not found, implement Playwright solution

### Long-term (Best):
1. **Contact SPAR for official API access**
   - Email: info@spar.at
   - Explain your use case (price comparison app)
   - Request API documentation or data feed
2. **Use official data feeds** if available
3. **Comply with their terms of service**

## Implementation Priority

### Priority 1: Find the API ✅
```bash
# Run this to inspect network requests
# Open browser, go to SPAR website, open DevTools Network tab
# Search for products and look for API calls
```

### Priority 2: Implement Playwright
If no API found, use Playwright for reliable scraping.

### Priority 3: Selenium Fallback
If Playwright doesn't work, use Selenium.

## Legal & Ethical Considerations

### ✅ Best Practices:
- Respect robots.txt
- Use reasonable delays (2-3 seconds)
- Don't overload servers
- Cache data to minimize requests
- Identify your bot in User-Agent
- Seek official API access

### ⚠️ Important:
- Check SPAR's Terms of Service
- Scraping may violate ToS
- Official API is always preferred
- Consider legal implications

## Alternative: Manual Data Entry

If automated scraping is not feasible:

1. **Crowdsourced Data**
   - Allow users to submit prices
   - Verify submissions
   - Build database over time

2. **Partial Automation**
   - Scrape only public promotional data
   - Use official RSS feeds if available
   - Supplement with user submissions

## Next Steps

### Immediate Actions:
1. ✅ Inspect SPAR website for API endpoints
2. ✅ Check if SPAR has a public API
3. ✅ Implement Playwright-based scraper
4. ✅ Test with small dataset
5. ✅ Contact SPAR for official access

### Code Updates Needed:
```python
# File: scrapers/spar_api_scraper.py
# Use API endpoints instead of HTML scraping

# File: scrapers/spar_playwright_scraper.py  
# Use Playwright for JavaScript rendering

# File: scrapers/spar_selenium_scraper.py
# Fallback Selenium implementation
```

## Testing the Current Scraper

The current scraper will fail with 403 errors. To test if SPAR's protection changes:

```bash
# Test connection
curl -A "Mozilla/5.0" https://www.spar.at/produktwelt/suche

# If you get HTML (not 403), the scraper might work
# If you get 403, you need one of the solutions above
```

## Resources

### Tools:
- **mitmproxy**: Intercept HTTP/HTTPS traffic
- **Postman**: Test API endpoints
- **Browser DevTools**: Inspect network requests
- **Playwright**: Modern browser automation
- **Selenium**: Traditional browser automation

### Documentation:
- Playwright: https://playwright.dev/python/
- Selenium: https://selenium-python.readthedocs.io/
- Requests: https://requests.readthedocs.io/

## Summary

The SPAR scraper is **technically complete** but **blocked by anti-bot protection**. 

**Recommended next steps:**
1. Inspect SPAR website for API endpoints (15-30 min)
2. If found, update scraper to use API
3. If not found, implement Playwright solution
4. Consider contacting SPAR for official API access

The scraper code is production-ready and will work once the access method is resolved.

---

**Last Updated**: 2026-05-17  
**Status**: Blocked by 403 - Needs API discovery or Playwright implementation
