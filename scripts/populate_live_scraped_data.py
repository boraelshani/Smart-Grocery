import requests
import sys
import os

# Add parent directory to path to import app and utils
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, parent_dir)

from utils.db import mongo
from app import app

def fetch_live_spar_products(queries):
    """
    Fetches real live prices and images from the official SPAR online shop API.
    """
    results = []
    headers = {"User-Agent": "Mozilla/5.0"}
    
    for q in queries:
        print(f"Scraping SPAR live for '{q}'...")
        url = f"https://search-spar.spar-ics.com/fact-finder/rest/v4/search/products_lmos_at?query={q}&q={q}"
        try:
            resp = requests.get(url, headers=headers, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                hits = data.get("hits", [])
                
                # Take top 3 results for each query
                for h in hits[:3]:
                    master = h.get("masterValues", {})
                    
                    name = master.get("title", "")
                    short_desc = master.get("short-description", "")
                    full_name = f"{name} {short_desc}".strip()
                    
                    price = float(master.get("price", 0))
                    image = master.get("image-url", "")
                    
                    if full_name and price > 0:
                        results.append({
                            "name": full_name,
                            "price": price,
                            "image": image,
                            "store": "SPAR",
                            "unit": master.get("sales-unit", "1 pc"),
                            "category": q.capitalize()
                        })
        except Exception as e:
            print(f"Error scraping {q}: {e}")
            
    return results

def populate_database_with_live_scraped_data():
    queries = ["Milch", "Brot", "Käse", "Apfel", "Hendl", "Pasta", "Wasser", "Reis", "Jogurt", "Tomaten"]
    print(f"Starting LIVE network scrape across {len(queries)} categories...")
    
    live_items = fetch_live_spar_products(queries)
    
    with app.app_context():
        # First, clear the products marked as demo/scraped so we don't duplicate
        mongo.db.products.delete_many({"is_scraped": True})
        # I'll also clear the ones I just injected because they had freepik images
        mongo.db.products.delete_many({"is_demo": True})
        
        insert_records = []
        for item in live_items:
            # We construct the real DB object
            # By saving SPAR as the only price, the AI Predictor will automatically do the rest for HOFER/BILLA!
            doc = {
                "name": item["name"],
                "unit": item["unit"],
                "image": item["image"], # REAL SPAR IMAGE
                "category": item["category"],
                "price": item["price"], # REAL SPAR PRICE
                "stores": [
                    {
                        "store": "SPAR",
                        "price": item["price"],
                        "url": "https://www.interspar.at/shop/lebensmittel/" # Base url since we don't have direct
                    }
                ],
                "is_scraped": True # Mark it so it can be updated
            }
            insert_records.append(doc)
            
        if insert_records:
            mongo.db.products.insert_many(insert_records)
            print(f"SUCCESS: Injected {len(insert_records)} 100% REAL LIVE scraped products into the database.")
            print("These have actual CDN images from Spar and actual cents/prices from today.")
        else:
            print("Failed to scrape any live data.")

if __name__ == "__main__":
    populate_database_with_live_scraped_data()
