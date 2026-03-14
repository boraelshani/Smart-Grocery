from scrapers.real_billa_scraper import RealBillaScraper
scraper = RealBillaScraper()
res = scraper.search_products("Milch")
for r in res[:10]:
    print(f"Name: {r['name']} | Unit: {r['unit']} | Brand: {r.get('brand')}")
