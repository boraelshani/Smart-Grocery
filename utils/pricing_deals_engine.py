"""
MODULE 7 & 8 - Price Comparison Engine & Deal Aggregation System
"""

def generate_price_comparison(product):
    """
    MODULE 7: Create a price comparison service
    """
    prices = product.get('storePrices', [])
    if not prices:
        return {"warning": "Missing pricing data."}
        
    valid_prices = [p for p in prices if p.get('price') is not None]
    if not valid_prices: return {"warning": "All prices invalid."}

    sorted_prices = sorted(valid_prices, key=lambda x: x['price'])
    min_price_obj = sorted_prices[0]
    max_price_obj = sorted_prices[-1]
    
    savings = max_price_obj['price'] - min_price_obj['price']
    savings_percent = (savings / max_price_obj['price']) * 100 if max_price_obj['price'] > 0 else 0
    
    return {
        "minPrice": min_price_obj['price'],
        "maxPrice": max_price_obj['price'],
        "cheapestStore": min_price_obj.get('store'),
        "savingsSummary": f"Save {savings_percent:.1f}% by shopping at {min_price_obj.get('store')}",
        "savingsPercent": savings_percent,
        "storeComparison": sorted_prices,
        "priceHistory": product.get("priceHistory", [])
    }


def extract_deals(products_list):
    """
    MODULE 8: Extract discounted products by detecting promotion tags and merge them.
    """
    deals = []
    
    for prod in products_list:
        name_lower = prod.get('name', '').lower()
        has_promo = any(tag in name_lower for tag in ['aktion', 'discount', '-20%', 'sale'])
        
        # Check if crossed out price exists (mock logic based on storePrices object)
        for store in prod.get('storePrices', []):
            if store.get('original_price') and store.get('price') < store.get('original_price'):
                has_promo = True
                discount_perc = ((store['original_price'] - store['price']) / store['original_price']) * 100
                store['discount_percentage'] = discount_perc
                
        if has_promo:
            deals.append(prod)
            
    # Sort deals by highest discount percentage
    def get_max_discount(p):
        max_d = 0
        for s in p.get('storePrices', []):
            if s.get('discount_percentage', 0) > max_d:
                max_d = s['discount_percentage']
        return max_d
        
    return sorted(deals, key=get_max_discount, reverse=True)
