from scrapers.real_billa_scraper import RealBillaScraper
import json, sys

class DebugBilla(RealBillaScraper):
    def search_products(self, query):
        url = f"https://shop.billa.at/suche/{query}"
        response = self.session.get(url, verify=False, timeout=15)
        
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(response.text, "html.parser")
        nuxt_script = soup.find("script", id="__NUXT_DATA__")
        data = json.loads(nuxt_script.string)
        
        for idx, item in enumerate(data):
            if isinstance(item, dict) and "price" in item and "name" in item and "slug" in item:
                p = self.resolve_nuxt_data(data, idx)
                name = p.get("name", "")
                if "Emmentaler" in name:
                    print(json.dumps(p, indent=2))
                    break

scraper = DebugBilla()
scraper.search_products("Emmentaler Scheiben")
