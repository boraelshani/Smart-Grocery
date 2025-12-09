# ===============================================
# HELPER FUNCTIONS - Shared utilities used by routes/models
# ===============================================

def format_price(price):
    # CONVERT: Price string to float (remove € or $ symbols)
    if isinstance(price, str):
        return float(price.replace('$', ''))
    return price

def find_cheapest_product(product):
    # FIND BEST DEAL: Get store with lowest price for this product
    min_price = float('inf')
    cheapest = None
    
    for store in product['stores']:
        price = format_price(store['price'])
        if price < min_price:
            min_price = price
            cheapest = store
    
    return cheapest

def calculate_total_cost(shopping_list, products):
    # CALCULATE TOTAL: Sum up costs of all items in shopping list
    total = 0.0
    for item in shopping_list:
        for product in products:
            if product['name'].lower() == item.lower():
                cheapest = find_cheapest_product(product)
                total += format_price(cheapest['price'])
    return round(total, 2)

def search_products(query, products):
    # SEARCH: Filter products by name (case-insensitive)
    return [p for p in products if query.lower() in p['name'].lower()]
