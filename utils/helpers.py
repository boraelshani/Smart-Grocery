# Helper utility functions

def format_price(price):
    """Format price string to float"""
    if isinstance(price, str):
        return float(price.replace('$', ''))
    return price

def find_cheapest_product(product):
    """Find cheapest store for a product"""
    min_price = float('inf')
    cheapest = None
    
    for store in product['stores']:
        price = format_price(store['price'])
        if price < min_price:
            min_price = price
            cheapest = store
    
    return cheapest

def calculate_total_cost(shopping_list, products):
    """Calculate total cost of shopping list"""
    total = 0.0
    for item in shopping_list:
        for product in products:
            if product['name'].lower() == item.lower():
                cheapest = find_cheapest_product(product)
                total += format_price(cheapest['price'])
    return round(total, 2)

def search_products(query, products):
    """Search products by name"""
    return [p for p in products if query.lower() in p['name'].lower()]
