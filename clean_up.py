with open('templates/compare_prices.html', 'r', encoding='utf-8') as f:
    text = f.read()

text = text.replace('<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>', '')

with open('templates/compare_prices.html', 'w', encoding='utf-8') as f:
    f.write(text)

with open('routes/compare/common.py', 'r', encoding='utf-8') as f:
    rtext = f.read()

import re
rtext = re.sub(
    r'@compare_bp\.route\(\'/price-history/<product_id>\'\)\ndef get_price_history\(product_id\):[\s\S]*?return doc',
    r'def _fetch_product_or_deal_by_id(product_id):\n    if not product_id: return None\n    doc = products_model.get_product_by_id(str(product_id))\n    if not doc: doc = featured_deals_model.get_deal_by_id(str(product_id))\n    if not doc: doc = multibuy_offers_model.get_offer_by_id(str(product_id))\n    if not doc:\n        try: doc = quantity_discounts_model.get_discount_by_id(str(product_id))\n        except: doc = None\n    return doc',
    rtext
)

with open('routes/compare/common.py', 'w', encoding='utf-8') as f:
    f.write(rtext)

print("Backend and HTML cleaned")