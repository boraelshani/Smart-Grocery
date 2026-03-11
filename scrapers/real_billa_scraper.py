import requests
import json

def scrape_billa_search(query):
    """
    REAL SCRAPER: Actively pings Billa's public search API.
    Returns live prices and product names.
    """
    url = f"https://shop.billa.at/api/search/full?searchTerm={query}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json",
        "Referer": "https://shop.billa.at/"
    }
    
    print(f"Scraping live Billa API for '{query}'...")
    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            data = response.json()
            if "tiles" in data:
                products = []
                for item in data["tiles"]:
                    if "data" in item and "article" in item["data"]:
                        article = item["data"]["article"]
                        name = article.get("title")
                        price = article.get("price", {}).get("final")
                        
                        if name and price:
                            products.append({
                                "name": name,
                                "price": price,
                                "store": "BILLA",
                                "source_id": article.get("id")
                            })
                return products
    except Exception as e:
        print(f"Error scraping Billa: {e}")
    return []

if __name__ == "__main__":
    results = scrape_billa_search("Milch")
    if results:
        print(json.dumps(results[:3], indent=2))
    else:
        print("No results found.")
