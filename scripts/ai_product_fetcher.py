import requests
from bs4 import BeautifulSoup
import re
import json
import urllib.parse

def fetch_product_from_url(url):
    """
    Fetches a product page and extracts basic OpenGraph, JSON-LD, and meta data securely.
    Uses Playwright dynamically to bypass 403 blocks (like Spar).
    """
    html_content = ""
    try:
        headers = {
             "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
             "Accept-Language": "en-US,en;q=0.9,de;q=0.8"
        }
        res = requests.get(url, headers=headers, timeout=8)
        if res.status_code == 403:
            raise Exception("403 Forbidden")
        res.raise_for_status()
        html_content = res.text
    except Exception as e:
        print(f"[Smart Fetcher] HTTP Requests failed ({e}). Attempting Playwright bypass...")
        try:
            from playwright.sync_api import sync_playwright
            with sync_playwright() as p:
                browser = p.chromium.launch(args=["--disable-blink-features=AutomationControlled"])
                context = browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
                page = context.new_page()
                page.goto(url, timeout=15000)
                page.wait_for_load_state("domcontentloaded")
                html_content = page.content()
                browser.close()
        except Exception as pw_err:
            return {"success": False, "error": f"Failed to reach URL (Playwright bypass also failed). Ensure it's valid. (Error: {str(pw_err)})"}

    try:
        soup = BeautifulSoup(html_content, "html.parser")
        
        # 1. Determine Title / Name
        title = "Extracted Product"
        og_title = soup.find("meta", property="og:title")
        if og_title and og_title.get("content"):
            title = og_title.get("content").strip()
        elif soup.title and soup.title.string:
            title = soup.title.string.strip()

        # Clean title of common suffixes (e.g., " | BILLA" or " - SPAR")
        title = re.split(r'\s*\|\s*|\s*-\s*', title)[0].strip()

        # 2. Determine Image
        image_url = ""
        og_image = soup.find("meta", property="og:image")
        if og_image and og_image.get("content"):
            image_url = og_image.get("content").strip()
        elif soup.find("img"):
            # Aggressive fallback just to grab the first useful image if OG fails
            img_tag = soup.find("img")
            if img_tag.get("src"):
                image_url = img_tag.get("src")
        
        # 3. Determine Price
        price = ""
        og_price = soup.find("meta", property="product:price:amount")
        if og_price and og_price.get("content"):
            price = og_price.get("content").strip()
        else:
            text = soup.get_text(separator=' ', strip=True)
            # Find common € formatting, matches 1.49, € 1.49, 1,49 € etc.
            price_match = re.search(r'(?:€\s*)?([0-9]{1,3}[,\.][0-9]{2})(?:\s*€)?', text)
            if price_match:
                price = price_match.group(1).replace(',', '.')

        # 4. JSON-LD parsing (Brand, Breadcrumbs, Descriptions)
        brand = ""
        category_path_raw = ""
        description = ""
        
        for script in soup.find_all("script", type="application/ld+json"):
            try:
                data = json.loads(script.string)
                if isinstance(data, list):
                    data = data[0]

                # Brand
                if "brand" in data and isinstance(data["brand"], dict):
                    brand = data["brand"].get("name", "")
                elif "brand" in data and isinstance(data["brand"], str):
                    brand = data["brand"]

                # Breadcrumbs
                if data.get("@type") == "BreadcrumbList" and "itemListElement" in data:
                    elements = data["itemListElement"]
                    if elements:
                        path_names = [e.get("item", {}).get("name", e.get("name", "")) for e in elements]
                        path_names = [n for n in path_names if n]
                        category_path_raw = " > ".join(path_names)

                # Find description
                if not description and "description" in data:
                    description = data["description"]
            except:
                continue

        # 5. Fallback Description and Breadcrumbs
        if not category_path_raw:
            bread_div = soup.find(class_=re.compile("breadcrumb", re.I))
            if bread_div:
                category_path_raw = " > ".join([a.get_text(strip=True) for a in bread_div.find_all("a")])

        if not description:
            og_desc = soup.find("meta", property="og:description")
            if og_desc and og_desc.get("content"):
                description = og_desc.get("content").strip()

        # Fallback Brand via meta
        if not brand:
             meta_brand = soup.find("meta", property="product:brand")
             if meta_brand and meta_brand.get("content"):
                 brand = meta_brand.get("content").strip()

        # ----------------------------------------------------
        # AI Mocks (Translation & Legal Copyright Rewrite)
        # ----------------------------------------------------
        # 1. Names: Usually German on AT domains
        name_de = title
        name_en = title  # Or some better translation logic
        
        # 2. Descriptions: Ensure uniqueness. AI summarizes into both languages.
        desc_en = f"A carefully selected, high-quality {name_en} essential for your pantry. It pairs nicely with fresh meals."
        desc_de = f"Ein sorgfältig ausgewähltes, hochwertiges Produkt ({name_de}), das in keiner Speisekammer fehlen darf. Passt perfekt zu frischen Mahlzeiten."
        
        if not description:
            desc_en = f"{name_en} - " + desc_en
            desc_de = f"{name_de} - " + desc_de

        if not image_url:
            encoded_name = urllib.parse.quote(name_en[:30])
            image_url = f"https://dummyimage.com/600x400/e0e0e0/555.png&text=AI+Gen:+{encoded_name}"

        # 3. Map Categories using our core taxonomy mapper
        mapped_cat_id = ""
        try:
            from utils.category_mapper import CategoryMapper
            mapper = CategoryMapper()
            # Map based on the full store breadcrumb or the title if no breadcrumb found
            target_string = category_path_raw if category_path_raw else title
            cat_result = mapper.map_category_with_path(target_string)
            if cat_result and isinstance(cat_result, dict):
                 mapped_cat_id = cat_result.get("categoryId", "")
        except:
            pass

        # 4. Map Brand string to an ID structure safely
        brand_id = ""
        if brand:
            if "-" in brand:
                brand = " ".join([w.capitalize() for w in brand.split("-")])
            else:
                brand = brand.title()
            brand_id = brand

        # 5. Extract Size and Unit Price
        size_str = ""
        unit_price_str = ""
        
        full_text = text if 'text' in locals() else soup.get_text(separator=' ', strip=True)
        search_corpus = f"{title} {description} {full_text}"
        
        # Try to find printed unit price first
        explicit_unit_match = re.search(r'(?:€|EUR)?\s*(\d{1,3}[.,]\d{2})\s*(?:€|EUR)?\s*/\s*(100\s?g|1\s?kg|100\s?ml|1\s?l|liter|kg)', search_corpus, re.IGNORECASE)
        if explicit_unit_match:
            up_val, up_unit = explicit_unit_match.groups()
            unit_price_str = f"€{up_val.replace(',', '.')}/{up_unit.replace(' ', '').lower()}"

        # Find size
        size_match = re.search(r'\b(\d+(?:[.,]\d+)?)\s*(g|kg|ml|l|liter|lite|piece|stk|stück|gramm|milliliter)(?:\b|\s|$)', search_corpus, re.IGNORECASE)
        
        if size_match:
            val_str, unit = size_match.groups()
            val = float(val_str.replace(',', '.'))
            unit = unit.lower()
            
            size_str = f"{val_str}{unit}"
            
            if price and not unit_price_str:
                try:
                    p = float(price)
                    if unit in ['g']:
                        unit_price = (p / val) * 100
                        unit_price_str = f"€{unit_price:.2f}/100g"
                        if val >= 1000:
                            unit_price = (p / val) * 1000
                            unit_price_str = f"€{unit_price:.2f}/1kg"
                    elif unit in ['kg']:
                        unit_price = p / val
                        unit_price_str = f"€{unit_price:.2f}/1kg"
                    elif unit in ['ml']:
                        unit_price = (p / val) * 100
                        unit_price_str = f"€{unit_price:.2f}/100ml"
                    elif unit in ['l', 'liter', 'lite']:
                        unit_price = p / val
                        unit_price_str = f"€{unit_price:.2f}/1l"
                    else:
                        unit_price = p / val
                        unit_price_str = f"€{unit_price:.2f}/unit"
                except:
                    pass

        return {
            "success": True,
            "data": {
                "name_en": name_en,
                "name_de": name_de,
                "description_en": desc_en,
                "description_de": desc_de,
                "price": price,
                "url": url,
                "image_url": image_url,
                "brand_raw": brand,
                "brandId": brand_id,
                "category_path": category_path_raw,
                "categoryId": mapped_cat_id,
                "size": size_str,
                "unit_price": unit_price_str
            }
        }
    except Exception as e:
        return {"success": False, "error": f"Failed to parse page internally: {str(e)}"}