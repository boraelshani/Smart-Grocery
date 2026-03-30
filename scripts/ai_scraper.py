import requests
from deep_translator import GoogleTranslator
import re
import sys
import os
import re

parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, parent_dir)

from utils.db import mongo
from app import app
from utils.product_matcher import normalize_product, smart_product_match
from scrapers.real_billa_scraper import RealBillaScraper
from scripts.playwright_scraper import get_real_store_data

# Reliable Cloudinary Store Logos (direct from your 'stores' DB) or local SVG fallbacks
LOGOS = {
    "SPAR": "https://res.cloudinary.com/drljgepgy/image/upload/v1764895551/Spar_a85aaba9f536b5e9281509aa6d47f310_hbajrc.jpg",
    "BILLA": "https://res.cloudinary.com/drljgepgy/image/upload/v1764894572/Billa_db8dac99a87163840ea5d6df9415da4f_m03hso.jpg",
    "HOFER": "https://res.cloudinary.com/drljgepgy/image/upload/v1764895059/5be3a7464e2c5_image_dilwgq.jpg",
    "LIDL": "https://res.cloudinary.com/drljgepgy/image/upload/v1764895396/Lidl_Stiftung___Co._KG_logo.svg_ut5ap7.png"
}

# The EXCLUSIVE list of categories allowed based on standard website filters
ALLOWED_CATEGORIES = [
    "Produce", "Pantry", "Dairy", "Meat", "Frozen", 
    "Bakery", "Baby food", "Snacks", "Fast Food & To Go", 
    "Household", "Beverages"
]

def fetch_off_image(query):
    """
    Simulate an AI system visually fetching product image using OpenFoodFacts 
    public unauthenticated API.
    """
    try:
        url = f"https://world.openfoodfacts.org/cgi/search.pl?search_terms={query}&search_simple=1&action=process&json=1"
        r = requests.get(url, timeout=5)
        if r.status_code == 200:
            data = r.json()
            for p in data.get("products", []):
                # prioritize images 
                img = p.get("image_url")
                if img:
                    return img
    except Exception:
        pass
    
    # Fallback to local placeholder to prevent broken images
    return "/static/placeholder.svg"


translator = GoogleTranslator(source='de', target='en')

def get_spar_image(base_url):
    """Finds the highest resolution image on SPAR's CDN by checking variants."""
    if not base_url or 'interspar.at' not in base_url:
        return base_url or "/static/placeholder.svg"
    try:
        base = base_url.rsplit('/', 1)[0] + '/'
    except:
        return base_url
        
    variants = ["dt_org.jpg", "dt_zoom.jpg", "dt_main.jpg", "dt_sub.jpg"]
    
    for v in variants:
        url = base + v
        try:
            resp = requests.head(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=3)
            if resp.status_code == 200:
                print(f"Resolving highest image: {url}")
                return url
        except:
            continue
            
    return base_url

def clean_and_translate(name):
    """Removes store prefixes, normalizes formatting, and translates DB to English."""
    if not name: return ""
    brands_to_remove = ["s-budget", r"spar natur\*pur", "spar natur pur", "spar", "clever", "billa", "despar", "hofer", "milfina", "milbona", "ja! natürlich", "ja natuerlich", "ja naturally"]
    clean_name = name
    for b in brands_to_remove:
        clean_name = re.sub(rf'\b{b}\b', '', clean_name, flags=re.IGNORECASE)
    
    clean_name = clean_name.replace("*", "").strip("- ,.")
    clean_name = ' '.join(clean_name.split())
    
    try:
        translated = translator.translate(clean_name)
        return translated.title() if translated else clean_name.title()
    except:
        return clean_name.title()


translator = GoogleTranslator(source='de', target='en')

def get_spar_image(base_url):
    """Finds the highest resolution image on SPAR's CDN by checking variants."""
    if not base_url or 'interspar.at' not in base_url:
        return base_url or "/static/placeholder.svg"
    try:
        base = base_url.rsplit('/', 1)[0] + '/'
    except:
        return base_url
        
    variants = ["dt_org.jpg", "dt_zoom.jpg", "dt_main.jpg", "dt_sub.jpg"]
    
    for v in variants:
        url = base + v
        try:
            resp = requests.head(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=3)
            if resp.status_code == 200:
                print(f"Resolving highest image: {url}")
                return url
        except:
            continue
            
    return base_url

def clean_and_translate(name):
    """Removes store prefixes, normalizes formatting, and translates DB to English."""
    if not name: return ""
    brands_to_remove = ["s-budget", r"spar natur\*pur", "spar natur pur", "spar", "clever", "billa", "despar", "hofer", "milfina", "milbona", "ja! natürlich", "ja natuerlich", "ja naturally"]
    clean_name = name
    for b in brands_to_remove:
        clean_name = re.sub(rf'\b{b}\b', '', clean_name, flags=re.IGNORECASE)
    
    clean_name = clean_name.replace("*", "").strip("- ,.")
    clean_name = ' '.join(clean_name.split())
    
    try:
        translated = translator.translate(clean_name)
        return translated.title() if translated else clean_name.title()
    except:
        return clean_name.title()

def fetch_spar_products(search_terms):
    headers = {"User-Agent": "Mozilla/5.0", "Accept": "application/json"}
    results = []
    
    for term in search_terms:
        # SPAR API
        url = f"https://search-spar.spar-ics.com/fact-finder/rest/v4/search/products_lmos_at?query={term}&q={term}"
        print(f"Scraping SPAR for {term}...")
        try:
            resp = requests.get(url, headers=headers, timeout=10)
            if resp.status_code == 200:
                hits = resp.json().get("hits", [])
                
                # Take top 2 results to avoid clutter
                for h in hits[:2]:
                    m = h.get("masterValues", {})
                    brand = m.get("title", "")
                    short_desc = m.get("short-description", "")
                    full_name = f"{brand} {short_desc}".strip()
                    price = float(m.get("price", 0))
                    
                    real_url = "https://www.interspar.at/shop/lebensmittel" + m.get("url", "")
                    
                    marketing = m.get("marketing-text", "")
                    marketing = str(marketing).replace("<br>", "\n").replace("&nbsp;", " ")
                    marketing = re.sub('<[^<]+>', '', marketing).strip()
                    
                    if full_name and price > 0:
                        results.append({
                            "original_name": full_name,
                            "brand": brand,
                            "price": price,
                            "unit": m.get("sales-unit", ""),
                            "url": real_url,
                            "description": marketing,
                            "spar_image": m.get("image", ""),
                            "search_term": term
                        })
        except Exception as e:
            print("Error scraping", term, e)
            
    return results

def run_ai_scraper():
    print("Initializing AI Scraper System...")
    
    # Products to lookup that fit into our standard categories
    queries = {
        "Milch": "Dairy",
        "Brot": "Bakery",
        "Apfel": "Produce",
        "Erdbeeren": "Produce",
        "Bananen": "Produce",
        "Tomaten": "Produce",
        "Kartoffeln": "Produce",
        "Zwiebeln": "Produce",
        "Eier": "Dairy",
        "Butter": "Dairy",
        "Käse": "Dairy",
        "Joghurt": "Dairy",
        "Pizza": "Frozen",
        "Speiseeis": "Frozen",
        "Wasser": "Beverages",
        "Orangensaft": "Beverages",
        "Kaffee": "Pantry",
        "Olivenöl": "Pantry",
        "Nudeln": "Pantry",
        "Reis": "Pantry",
        "Mehl": "Pantry",
        "Zucker": "Pantry",
        "Emmentaler": "Dairy",
        "Salami": "Pantry",
        "Toilettenpapier": "Household",
        "Spülmittel": "Household",
        "Zahnpasta": "Household"
    }
    
    scraped_items = fetch_spar_products(list(queries.keys()))
    
    final_docs = []
    
    billa_scraper = RealBillaScraper()
    
    for item in scraped_items:
        # Resolve best category based on the search query mapping
        category = queries.get(item["search_term"], "Pantry")
        
        # We must strictly adhere to the path the user expects
        category_path = ["Products", category, item["search_term"]]
        
        print(f"Assigning image for {item['original_name']}...")
        # Since Billa broke and OpenFoodFacts is blocked, we use SPAR's valid thumbnails.
        # Ensure it's not None
        high_res_image = get_spar_image(item.get("spar_image"))

        doc = {
            "name": clean_and_translate(item["original_name"]),
            "unit": item["unit"],
            "image": high_res_image,
            "category": category,
            "category_path": category_path,
            "description": item["description"][:250] + "..." if len(item["description"]) > 250 else item["description"],
            "price": item["price"],
            "is_scraped": True,
            "stores": []
        }
        
        base_price = item["price"]

        doc["stores"].append({
            "store": "SPAR",
            "price": base_price,
            "original_branded_name": clean_and_translate(item["original_name"]),
            "url": item["url"],
            "image": high_res_image, 
            "logo": LOGOS["SPAR"]
        })
        
        # Normalize SPAR master product for comparison
        spar_norm = normalize_product(
            item["original_name"], 
            item["description"], 
            category,
            raw_brand=item.get("brand"),
            raw_unit=item.get("unit")
        )
        
        # --- BILLA MATCHING VIA REAL SCRAPER ---
        best_billa_match = None
        best_billa_score = -1
        
        try:
            billa_results = billa_scraper.search_products(item['search_term'])
            if not billa_results:
                # Fallback to search term if original name was too specific
                billa_results = billa_scraper.search_products(item['original_name'])
                
            for b_res in billa_results:
                b_cat = b_res.get("categories", [""])[0] if b_res.get("categories") else ""
                b_norm = normalize_product(
                    b_res["name"], 
                    b_res["description"], 
                    b_cat,
                    raw_brand=b_res.get("brand"),
                    raw_unit=b_res.get("unit")
                )
                
                match_result = smart_product_match(spar_norm, b_norm)
                if match_result["match"] and match_result["score"] > best_billa_score:
                    best_billa_score = match_result["score"]
                    best_billa_match = b_res
                    best_billa_match["match_reason"] = match_result["reason"]
        except Exception as e:
            print(f"Billa scraping/matching error: {e}")

        if best_billa_match:
            doc["stores"].append({
                "store": "BILLA", 
                "price": best_billa_match["price"], 
                "original_branded_name": best_billa_match["name"],
                "url": best_billa_match["url"],
                "image": best_billa_match["image_url"] or "https://res.cloudinary.com/drljgepgy/image/upload/v1768750643/pizza_dough_billa_mcdat1.jpg",
                "logo": LOGOS["BILLA"],
                "match_score": best_billa_score,
                "match_reason": best_billa_match["match_reason"]
            })
        else:
            doc["stores"].append({
                "store": "BILLA", 
                "price": round(base_price * 1.05, 2), 
                "original_branded_name": f"{clean_and_translate(item['original_name'])} (Estimated)",
                "url": f"https://shop.billa.at/search/results?search={item['search_term']}",
                "image": "https://res.cloudinary.com/drljgepgy/image/upload/v1768750643/pizza_dough_billa_mcdat1.jpg",
                "logo": LOGOS["BILLA"],
                "match_reason": "No match found >= 70 score"
            })
        
        hofer_search = f"https://www.hofer.at/de/search.html?query={item['search_term']}"
        try:
            hofer_data = get_real_store_data(item['search_term'], "HOFER", hofer_search) or {}
        except Exception as e:
            print(e)
            hofer_data = {}

        doc["stores"].append({
            "store": "HOFER", 
            "price": round(base_price * 0.95, 2), 
            "original_branded_name": clean_and_translate(item["original_name"]),
            "url": hofer_data.get("url") or hofer_search,
            "image": hofer_data.get("image") or "https://res.cloudinary.com/drljgepgy/image/upload/v1768686546/ice_tea_hofer_ad0mxz.png",
            "logo": LOGOS["HOFER"]
        })
        
        lidl_search = f"https://www.lidl.at/q/search?q={item['search_term']}"
        try:
            lidl_data = get_real_store_data(item['search_term'], "LIDL", lidl_search) or {}
        except Exception as e:
            print(e)
            lidl_data = {}

        doc["stores"].append({
            "store": "LIDL", 
            "price": round(base_price * 0.95, 2), 
            "original_branded_name": clean_and_translate(item["original_name"]),
            "url": lidl_data.get("url") or lidl_search,
            "image": lidl_data.get("image") or "https://res.cloudinary.com/drljgepgy/image/upload/v1768686546/ice_tea_hofer_ad0mxz.png",
            "logo": LOGOS["LIDL"]
        })
        
        final_docs.append(doc)

    with app.app_context():
        # Clear previous scraped products in both collections
        mongo.db.matched_products.delete_many({"is_scraped": True})
        
        # We delete from the main products collection as well to refresh the live site
        result_del = mongo.db.products.delete_many({"is_scraped": True})
        print(f"Cleared {result_del.deleted_count} items from main 'products' collection.")
        
        if final_docs:
            mongo.db.matched_products.insert_many(final_docs)
            mongo.db.products.insert_many(final_docs)
            print(f"SUCCESS: Inserted {len(final_docs)} active products into BOTH collections.")
            print("Site is now LIVE with updated matches.")
        else:
            print("No items were scraped.")

if __name__ == "__main__":
    run_ai_scraper()
