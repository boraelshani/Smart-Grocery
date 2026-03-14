import os
import certifi
import pymongo
from utils.product_matcher import normalize_product, smart_product_match

uri = "mongodb+srv://drenbuqa:boradren@cluster0.vmrpj9o.mongodb.net/smart_grocery?appName=Cluster0"
client = pymongo.MongoClient(uri, tlsCAFile=certifi.where())
db = client['smart_grocery']

# Let's try to simulate the matching for one search term that failed, e.g., "Olivenöl" or "Brot"
# We'll fetch SPAR results for "Olivenöl" first
import requests
headers = {"User-Agent": "Mozilla/5.0"}
spar_url = "https://search-spar.spar-ics.com/fact-finder/rest/v4/search/products_lmos_at?query=Olivenöl&q=Olivenöl"
spar_resp = requests.get(spar_url, headers=headers).json()
spar_hits = spar_resp.get("hits", [])

from scrapers.real_billa_scraper import RealBillaScraper
billa_scraper = RealBillaScraper()

print("--- DEBUGGING OLIVENÖL MATCHING ---")
for h in spar_hits[:2]:
    m = h.get("masterValues", {})
    spar_name = f"{m.get('title', '')} {m.get('short-description', '')}".strip()
    spar_unit = m.get("sales-unit", "")
    
    spar_norm = normalize_product(spar_name, "", "Pantry", raw_unit=spar_unit)
    print(f"\nSPAR: {spar_name} | Unit: {spar_unit} | NormSize: {spar_norm['size']}")
    
    billa_results = billa_scraper.search_products("Olivenöl")
    best_score = -1
    best_candidate = None
    
    for b in billa_results:
        b_norm = normalize_product(b['name'], b['description'], "", raw_brand=b.get('brand'), raw_unit=b.get('unit'))
        match = smart_product_match(spar_norm, b_norm)
        if match['score'] > best_score:
            best_score = match['score']
            best_candidate = b
        if "Clever" in b['name'] or "Budget" in spar_name:
             print(f"  Candidate: {b['name']} | Size: {b_norm['size']} | Score: {match['score']} | Reason: {match['reason']}")
    
    print(f"BEST MATCH for {spar_name}: {best_candidate['name'] if best_candidate else 'None'} Score: {best_score}")

