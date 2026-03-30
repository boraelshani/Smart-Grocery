import json
import re
from playwright.sync_api import sync_playwright
import time

def extract_largest_image(page, store):
    """
    Extracts the best possible image from a loaded Playwright page 
    by checking data-src, srcset, and script JSON blocks.
    """
    best_image = None
    
    # 1. Billa: Check data-src or srcset
    if store == "BILLA":
        print("[BILLA] Checking for srcset or data-src...")
        images = page.locator("img").all()
        for img in images:
            srcset = img.get_attribute("srcset")
            if srcset:
                # Srcset looks like: "url1 300w, url2 800w" - get the largest width
                sources = srcset.split(',')
                try:
                    largest = sorted(sources, key=lambda s: int(re.search(r'(\d+)w', s).group(1)) if re.search(r'(\d+)w', s) else 0)[-1]
                    best_image = largest.strip().split(' ')[0]
                    if "http" not in best_image: 
                        best_image = "https://shop.billa.at" + best_image
                    break
                except:
                    pass
                    
            if not best_image:
                data_src = img.get_attribute("data-src")
                if data_src:
                    best_image = data_src
                    break

    # 2. Hofer: Extract from JSON API inside the HTML
    elif store == "HOFER":
        print("[HOFER] Extracting scene7 / aldi image...")
        
        # 1. Look for img tags with scene7 or aldi in src/data-src
        images = page.locator("img").all()
        for img in images:
            src = img.get_attribute("src") or ""
            data_src = img.get_attribute("data-src") or ""
            
            target = None
            if "scene7.com" in data_src or "aldi" in data_src.lower():
                target = data_src
            elif "scene7.com" in src or "aldi" in src.lower():
                target = src
                
            if target:
                # Ensure we apply the $H10-XL$ high-res tag instead of small versions
                target = re.sub(r'\$H10-[a-zA-Z0-9]+\$', '$H10-XL$', target)
                if "$H10" not in target:
                    if "?" in target:
                        target = target.split("?")[0] + "?$H10-XL$"
                    else:
                        target = target + "?$H10-XL$"
                        
                best_image = target
                break
                
        # 2. Fallback to JSON state if still missing
        if not best_image:
            scripts = page.locator("script").all()
            for script in scripts:
                content = script.inner_text()
                if "window.INITIAL_STATE =" in content or "productData" in content:
                    matches = re.findall(r'"image":\s*"([^"]+)"', content)
                    if matches:
                        best_image = matches[0].replace('\\/', '/')
                        # Try to upgrade this one too
                        if "scene7.com" in best_image:
                            best_image = re.sub(r'\$H10-[a-zA-Z0-9]+\$', '$H10-XL$', best_image)
                        break

    # 3. Lidl: Extract CDN URL from JSON embedded in <script>
    elif store == "LIDL":
        print("[LIDL] Extracting from application/ld+json...")
        scripts = page.locator('script[type="application/ld+json"]').all()
        for script in scripts:
            try:
                data = json.loads(script.inner_text())
                if isinstance(data, dict):
                    # Sometimes wrapped in @graph or main Object
                    if "image" in data:
                        imgs = data["image"]
                        best_image = imgs[0] if isinstance(imgs, list) else imgs
                        break
                elif isinstance(data, list):
                    for item in data:
                        if "image" in item:
                            imgs = item["image"]
                            best_image = imgs[-1] if isinstance(imgs, list) else imgs # get last/largest
                            break
            except Exception as e:
                pass

    # Generic Fallback: find any high-res indicators in the DOM
    if not best_image:
        images = page.locator('img').all()
        for img in images:
            src = img.get_attribute("src")
            if src and any(x in src.lower() for x in ['/large/', 'full', 'zoom', 'high']):
                best_image = src
                break

    # Replace size variants universally
    if best_image:
        for low, high in [('/small/', '/large/'), ('thumbnail', 'full'), ('_small.jpg', '_large.jpg'), ('150x150', '800x800')]:
            best_image = best_image.replace(low, high)
            
    return best_image

def get_real_store_data(search_term, store_name, search_url):
    print(f"[{store_name}] Launching Playwright to scrape: {search_term}")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
        page = context.new_page()
        page.route("**/*", lambda route: route.continue_() if route.request.resource_type in ["document", "script", "xhr", "fetch"] else route.abort())
        
        try:
            print(f"[{store_name}] Loading search: {search_url}")
            page.goto(search_url, timeout=20000)
            page.wait_for_load_state("domcontentloaded")
            time.sleep(2)
            
            real_url = search_url
            links = page.locator('a[href*="/p/"], a[href*="/product/"], a[href*="/pr/"]').all()
            if links:
                href = links[0].get_attribute("href")
                if href:
                    if store_name == "BILLA" and "http" not in href: real_url = "https://shop.billa.at" + href
                    elif store_name == "HOFER" and "http" not in href: real_url = "https://www.hofer.at" + href
                    elif store_name == "LIDL" and "http" not in href: real_url = "https://www.lidl.at" + href
                    else: real_url = href
            
            if real_url == search_url and "/p/" not in page.url and "/product/" not in page.url and "/pr/" not in page.url:
                real_url = page.url
                
            print(f"[{store_name}] Navigating to product page: {real_url}")
            if real_url != search_url or page.url != real_url:
                page.goto(real_url, timeout=20000)
                page.wait_for_load_state("domcontentloaded")
                time.sleep(3)
            else:
                time.sleep(2)
                
            image_url = extract_largest_image(page, store_name)
            
            browser.close()
            return {
                "image": image_url,
                "url": real_url
            }
        except Exception as e:
            print(f"[{store_name}] Playwright execution failed: {e}")
            try:
                browser.close()
            except:
                pass
            return None
