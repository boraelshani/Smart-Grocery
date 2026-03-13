import requests
import json
import urllib3
import time
import re
from datetime import datetime, UTC
from bs4 import BeautifulSoup

# Disable insecure request warnings (Billa sometimes has cert issues depending on local CA)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

class RealBillaScraper:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "de-DE,de;q=0.9,en-US;q=0.8,en;q=0.7",
        })

    def resolve_nuxt_data(self, data, idx, resolved=None):
        if resolved is None:
            resolved = {}
        if not isinstance(idx, int) or idx < 0 or idx >= len(data):
            return idx
        if idx in resolved:
            return resolved[idx]
        
        val = data[idx]
        if isinstance(val, dict):
            res = {}
            resolved[idx] = res # put early to avoid cyclic
            for k, v in val.items():
                res[k] = self.resolve_nuxt_data(data, v, resolved)
            return res
        elif isinstance(val, list):
            res = []
            resolved[idx] = res
            for v in val:
                res.append(self.resolve_nuxt_data(data, v, resolved))
            return res
        return val

    def _extract_unit_from_text(self, text):
        """Extract a compact unit string from product text, e.g. 500g / 1L / 10 pack."""
        if not text:
            return ''
        hay = str(text).lower().replace(',', '.')
        m = re.search(r'(\d+(?:\.\d+)?)\s*(kg|g|l|ml|stk|st\.|pack|packs|er\b)', hay)
        if not m:
            return ''
        qty = m.group(1)
        unit = m.group(2)
        unit = {'st.': 'stk', 'packs': 'pack'}.get(unit, unit)
        return f"{qty}{unit}"

    def search_products(self, query):
        """
        Searches Billa utilizing Nuxt SSR payload scraping.
        This completely bypasses their new SPA/API protections.
        """
        print(f"[*] Billa Scraper: Searching for '{query}'...")
        url = f"https://shop.billa.at/suche/{query}"
        
        try:
            response = self.session.get(url, verify=False, timeout=15)
            response.raise_for_status()
        except Exception as e:
            print(f"[!] Billa Scraper Error: HTTP request failed: {e}")
            return []

        soup = BeautifulSoup(response.text, "html.parser")
        nuxt_script = soup.find("script", id="__NUXT_DATA__")
        
        if not nuxt_script:
            print("[!] Billa Scraper Error: Could not find __NUXT_DATA__ in HTML. Billa may have changed their Nuxt architecture.")
            return []

        try:
            data = json.loads(nuxt_script.string)
        except json.JSONDecodeError:
            print("[!] Billa Scraper Error: Failed to parse __NUXT_DATA__ string as JSON.")
            return []

        # Find and resolve product objects
        products = []
        found_slugs = set()

        for idx, item in enumerate(data):
            if isinstance(item, dict):
                # Identifying a product dict in Billa Nuxt 3 devalue array
                # Products usually have 'price', 'name', 'slug', 'sku'
                if "price" in item and "name" in item and "slug" in item:
                    try:
                        p = self.resolve_nuxt_data(data, idx)
                        
                        name = p.get("name", "")
                        slug = p.get("slug", "")
                        
                        # Avoid duplicates
                        if not slug or slug in found_slugs:
                            continue
                            
                        # Price is structured as {'regular': 123, 'baseUnitLong': ...}
                        price_obj = p.get("price", {})
                        if isinstance(price_obj, dict):
                            price_val = price_obj.get("regular", 0)
                            if isinstance(price_val, dict):
                                price_val = price_val.get("value", 0)  # Just a guess if it's nested
                        else:
                            price_val = price_obj
                            
                        try:
                            final_price = float(price_val)
                            # Billa returns raw prices usually in cents (e.g. 139 for 1.39) 
                            # Let's adjust if > 0
                            if final_price > 0:
                                pass # Wait, let's see. If I divide by 100, 139 -> 1.39. Correct.
                                final_price = final_price / 100.0
                        except (ValueError, TypeError):
                            final_price = 0.0

                        if final_price <= 0:
                            continue
                            
                        # Product image URL — strictly use Commercetools CDN
                        images = p.get("images", [])
                        image_url = ""
                        if images and isinstance(images, list):
                            raw = images[0] if isinstance(images[0], str) else ""
                            if raw.startswith("http"):
                                image_url = raw
                            
                        description = p.get("descriptionShort") or p.get("descriptionLong") or ""
                        base_unit_long = ''
                        if isinstance(price_obj_full, dict):
                            base_unit_long = str(price_obj_full.get("baseUnitLong") or "").strip()
                        unit_value = self._extract_unit_from_text(name) or self._extract_unit_from_text(description) or base_unit_long
                        now_iso = datetime.now(UTC).isoformat()

                        # Offer / promotion data
                        in_promo = bool(p.get("inPromotion"))
                        price_obj_full = p.get("price", {}) if isinstance(p.get("price"), dict) else {}
                        crossed_cents = price_obj_full.get("crossed", 0) or 0
                        discount_pct = price_obj_full.get("discountPercentage", 0) or 0
                        promo_value_cents = 0
                        if isinstance(price_obj_full.get("regular"), dict):
                            promo_value_cents = price_obj_full["regular"].get("promotionValue", 0) or 0
                        
                        offer = None
                        if in_promo and crossed_cents:
                            original_price = float(crossed_cents) / 100.0
                            offer = {
                                "type": "discount",
                                "original_price": original_price,
                                "discount_percentage": abs(int(discount_pct)),
                            }

                        scraped_p = {
                            "store": "Billa",
                            "name": name,
                            "price": final_price,
                            "original_price": final_price,
                            "url": f"https://shop.billa.at/angebote/{slug}" if "angebote" in slug else f"https://shop.billa.at/produkte/{slug}",
                            "image_url": image_url,
                            "organic": "bio" in name.lower() or "bio" in description.lower(),
                            "categories": [p.get("category", "")],
                            "description": str(description),
                            "unit": unit_value,
                            "price_confirmed_at": now_iso,
                            "updated_at": now_iso,
                            "in_promotion": in_promo,
                            "offer": offer,
                        }
                        
                        products.append(scraped_p)
                        found_slugs.add(slug)
                    except Exception as parse_e:
                        print(f"Skipping a product due to parse error: {parse_e}")

        # Basic sorting by relevance (exact match usually comes first in Nuxt, but we just return what we have)
        print(f"[*] Billa Scraper: Successfully parsed {len(products)} products from Nuxt state.")
        return products

if __name__ == "__main__":
    scraper = RealBillaScraper()
    results = scraper.search_products("milch")
    for r in results[:5]:
        print(r)
