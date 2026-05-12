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

        # Clean title of common prefixes and suffixes
        # Remove "Meine HOFER Produktempfehlung:" prefix (Hofer specific)
        title = re.sub(r'^Meine\s+HOFER\s+Produktempfehlung:\s*', '', title, flags=re.IGNORECASE)
        # Remove store name suffixes (e.g., " | BILLA" or " - SPAR")
        title = re.split(r'\s*\|\s*|\s*-\s*(?:BILLA|SPAR|HOFER|LIDL|MERKUR)', title, flags=re.IGNORECASE)[0].strip()
        # Remove trailing " | " or " - " if any remain
        title = re.sub(r'\s*[\|\-]\s*$', '', title).strip()

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
        
        # 3. Determine Price (Base and Promo)
        price = ""
        promo_price = ""
        
        # Try OpenGraph price first
        og_price = soup.find("meta", property="product:price:amount")
        if og_price and og_price.get("content"):
            price = og_price.get("content").strip()
        
        # Try JSON-LD for price data
        if not price:
            for script in soup.find_all("script", type="application/ld+json"):
                try:
                    data = json.loads(script.string)
                    if isinstance(data, list):
                        data = data[0]
                    
                    # Check for offers with price
                    if "offers" in data:
                        offers = data["offers"]
                        if isinstance(offers, dict):
                            if "price" in offers:
                                price = str(offers["price"])
                            if "lowPrice" in offers:
                                promo_price = str(offers["lowPrice"])
                        elif isinstance(offers, list) and offers:
                            if "price" in offers[0]:
                                price = str(offers[0]["price"])
                except:
                    continue
        
        # Fallback: Extract from page text with improved regex
        if not price:
            text = soup.get_text(separator=' ', strip=True)
            
            # Look for price patterns with € symbol
            # Matches: €1.49, € 1.49, 1,49 €, 1.49€, etc.
            price_patterns = [
                r'€\s*(\d{1,3}[,\.]\d{2})',  # €1.49 or € 1.49
                r'(\d{1,3}[,\.]\d{2})\s*€',  # 1.49€ or 1,49 €
                r'Preis[:\s]+€?\s*(\d{1,3}[,\.]\d{2})',  # Preis: €1.49
                r'(?:Statt|UVP)[:\s]+€?\s*(\d{1,3}[,\.]\d{2})',  # Statt: €2.49 (old price)
            ]
            
            # Try to find promotional price first (usually marked with special keywords)
            promo_keywords = r'(?:Aktion|Angebot|Rabatt|Reduziert|Jetzt|Nur|ab\s*\d+\s*Stück)'
            promo_match = re.search(rf'{promo_keywords}[^€\d]*€?\s*(\d{{1,3}}[,\.]\d{{2}})', text, re.IGNORECASE)
            if promo_match:
                promo_price = promo_match.group(1).replace(',', '.')
            
            # Billa-specific: Look for "ab X Stück/Dosen" quantity discount patterns
            # Example: "ab 24 Stück 0,99" or "ab 24 Dosen € 0,99" or "24er Aktion € 0,99"
            billa_qty_patterns = [
                r'(?:ab|per)\s*(\d+)\s*(?:Stück|stk|stück|Dosen|dosen|Flaschen|flaschen)[^€\d]{0,30}€?\s*(\d{1,3}[,\.]\d{2})',
                r'(\d+)\s*(?:Stück|stk|Dosen|dosen)[^€\d]{0,20}(?:Aktion|Angebot)[^€\d]{0,20}€?\s*(\d{1,3}[,\.]\d{2})',
                r'(\d+)er[^€\d]{0,30}€?\s*(\d{1,3}[,\.]\d{2})',
                r'(?:ab|per)\s*(\d+)[^€\d]{0,10}€?\s*(\d{1,3}[,\.]\d{2})',  # Fallback: "ab 24 €0.99"
            ]
            qty_for_offer = None
            for pattern in billa_qty_patterns:
                billa_qty_match = re.search(pattern, text, re.IGNORECASE)
                if billa_qty_match:
                    qty_for_offer = billa_qty_match.group(1)
                    qty_price = billa_qty_match.group(2).replace(',', '.')
                    # This is likely a promotional price for bulk purchase
                    if not promo_price or (qty_price and float(qty_price) < float(promo_price or '999')):
                        promo_price = qty_price
                    break
            
            # Find regular price
            for pattern in price_patterns:
                price_match = re.search(pattern, text, re.IGNORECASE)
                if price_match:
                    found_price = price_match.group(1).replace(',', '.')
                    # If we found a promo price, this might be the old price
                    if promo_price and "Statt" in pattern or "UVP" in pattern:
                        price = found_price  # This is the old/regular price
                    elif not price:
                        price = found_price
                    break
            
            # If we have both prices, ensure promo is lower than regular
            if price and promo_price:
                try:
                    if float(promo_price) >= float(price):
                        # Swap them if promo is higher (we got them backwards)
                        price, promo_price = promo_price, price
                except:
                    pass
        
        # Normalize price format
        if price:
            price = price.replace(',', '.')
        if promo_price:
            promo_price = promo_price.replace(',', '.')

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

        # 3. Map Categories using our core taxonomy mapper with enhanced context
        mapped_cat_id = ""
        category_confidence = 0
        matched_keywords = []
        try:
            from utils.category_mapper import CategoryMapper
            mapper = CategoryMapper()
            # Map based on the full store breadcrumb, product name, and description
            target_string = category_path_raw if category_path_raw else ""
            # Use the extracted description or the generated one
            desc_for_mapping = description if description else desc_de
            cat_result = mapper.map_category_with_path(
                store_category_path=target_string,
                product_name=name_de,
                product_description=desc_for_mapping
            )
            if cat_result and isinstance(cat_result, dict):
                mapped_cat_id = cat_result.get("categoryId", "")
                category_confidence = cat_result.get("confidence", 0)
                matched_keywords = cat_result.get("matched_keywords", [])
        except Exception as e:
            print(f"[Category Mapping Error]: {e}")
            pass

        # 4. Map Brand string to an ID structure safely
        brand_id = ""
        if brand:
            if "-" in brand:
                brand = " ".join([w.capitalize() for w in brand.split("-")])
            else:
                brand = brand.title()
            brand_id = brand

        # 5. Extract Size, Unit Price, and Offer Details
        size_str = ""
        unit_price_str = ""
        offer_details = ""
        
        full_text = text if 'text' in locals() else soup.get_text(separator=' ', strip=True)
        search_corpus = f"{title} {description} {full_text}"
        
        # Extract offer details with improved patterns
        offer_patterns = [
            r'(\d+\s*\+\s*\d+\s*(?:gratis|free|geschenkt))',  # 2+1 gratis
            r'(-\d+%|\d+%\s*(?:rabatt|discount|günstiger))',  # -50% or 50% Rabatt
            r'((?:ab|per)\s*\d+\s*(?:stück|stk|dosen|flaschen|packungen)[^\.]{0,30}€?\s*\d+[,\.]\d{2})',  # ab 24 Dosen €0.99
            r'(\d+er[^\.]{0,20}(?:aktion|angebot))',  # 24er Aktion
            r'(nur\s*€?\s*\d+[,\.]\d{2})',  # Nur €1.99
            r'(statt\s*€?\s*\d+[,\.]\d{2})',  # Statt €2.99
            r'(aktion|angebot|sonderpreis|aktionspreis)',  # General promo keywords (fallback)
        ]
        
        # If we found a quantity-based discount earlier, use that for offer details
        if 'qty_for_offer' in locals() and qty_for_offer and promo_price:
            offer_details = f"ab {qty_for_offer} Stück €{promo_price}"
        else:
            # Otherwise, search for offer patterns
            for pattern in offer_patterns:
                offer_match = re.search(pattern, search_corpus, re.IGNORECASE)
                if offer_match:
                    offer_details = offer_match.group(1).strip()
                    break
        
        # If we have a promo price, add it to offer details
        if promo_price and price:
            try:
                regular = float(price)
                promo = float(promo_price)
                if promo < regular:
                    discount_pct = int(((regular - promo) / regular) * 100)
                    if not offer_details:
                        offer_details = f"-{discount_pct}%"
                    else:
                        offer_details += f" (-{discount_pct}%)"
            except:
                pass
        
        # Try to find printed unit price first
        explicit_unit_match = re.search(r'(?:€|EUR)?\s*(\d{1,3}[.,]\d{2})\s*(?:€|EUR)?\s*/\s*(100\s?g|1\s?kg|100\s?ml|1\s?l|liter|kg)', search_corpus, re.IGNORECASE)
        if explicit_unit_match:
            up_val, up_unit = explicit_unit_match.groups()
            unit_price_str = f"€{up_val.replace(',', '.')}/{up_unit.replace(' ', '').lower()}"

        # Find true product size (ignoring low integers like 2 or 3 that might be from 2+1)
        size_match = re.search(r'\b(\d+(?:[.,]\d+)?)\s*(g|kg|ml|l|liter|lite|piece|stk|stück|gramm|milliliter)(?:\b|\s|$)', search_corpus, re.IGNORECASE)
        
        if size_match:
            val_str, unit = size_match.groups()
            val = float(val_str.replace(',', '.'))
            unit = unit.lower()
            
            size_str = f"{val_str}{unit}"
            
            # Calculate unit price if not found and we have a price
            if not unit_price_str:
                # Use promo price if available, otherwise regular price
                calc_price = promo_price if promo_price else price
                if calc_price:
                    try:
                        p = float(calc_price)
                        if unit in ['g', 'gramm']:
                            unit_price = (p / val) * 100
                            unit_price_str = f"€{unit_price:.2f}/100g"
                            if val >= 1000:
                                unit_price = (p / val) * 1000
                                unit_price_str = f"€{unit_price:.2f}/1kg"
                        elif unit in ['kg']:
                            unit_price = p / val
                            unit_price_str = f"€{unit_price:.2f}/1kg"
                        elif unit in ['ml', 'milliliter']:
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
                "category": mapped_cat_id, # Add this for UI fallback
                "category_confidence": category_confidence,
                "category_matched_keywords": matched_keywords,
                "size": size_str,
                "unit_price": unit_price_str,
                "promo_price": promo_price,
                "offer_details": offer_details,
                "min_quantity": int(qty_for_offer) if 'qty_for_offer' in locals() and qty_for_offer else None
            }
        }
    except Exception as e:
        return {"success": False, "error": f"Failed to parse page internally: {str(e)}"}

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        print(json.dumps(fetch_product_from_url(sys.argv[1]), indent=2))
