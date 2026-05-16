"""
Recipe ingredient matcher - matches ingredients to PostgreSQL products.
"""
import re
from models.postgres_models import Product, ProductStore, Store, Category
from models.postgres_models import db as sa_db
from sqlalchemy import func, or_


def clean_ingredient_term(ingredient):
    """
    Cleans up a raw AI ingredient strings (e.g., '500g ripe tomatoes' -> 'tomatoes')
    by removing common quantities, numbers, and measurement units.
    """
    cleaned = re.sub(r'^\s*[\d\.\/]+\s*', '', ingredient)

    units = [
        "g", "kg", "ml", "l", "oz", "lb", "cup", "cups",
        "tbsp", "tsp", "tablespoon", "teaspoon", "clove", "cloves",
        "slice", "slices", "piece", "pieces", "can", "cans", "tin", "tins",
        "dash", "pinch", "package", "pack", "box", "stick", "sticks", "bag", "handful"
    ]
    units_pattern = r'\b(?:' + '|'.join(units) + r')\b'
    cleaned = re.sub(units_pattern, '', cleaned, flags=re.IGNORECASE)

    fillers = ["of", "ripe", "fresh", "large", "small", "medium", "chopped", "diced", "sliced", "melted", "softened", "crushed", "minced", "grated"]
    return cleaned


def calculate_proportion_message(req_text, prod_unit, price):
    if not req_text or not prod_unit or price is None:
        return None

    def parse_amt(text):
        if not text:
            return None, None
        m = re.search(r'([\d\.,]+)\s*([a-zA-Z%]+)', str(text).replace(',', '.'))
        if m:
            return float(m.group(1)), m.group(2).lower()
        return None, None

    req_q, req_u = parse_amt(req_text)
    prod_q, prod_u = parse_amt(prod_unit)

    if not req_q or not prod_q or not req_u or not prod_u:
        return None

    if req_u in ('kg', 'kilo', 'kilos'):
        req_q *= 1000; req_u = 'g'
    if req_u in ('l', 'liter', 'liters'):
        req_q *= 1000; req_u = 'ml'
    if prod_u in ('kg', 'kilo', 'kilos'):
        prod_q *= 1000; prod_u = 'g'
    if prod_u in ('l', 'liter', 'liters'):
        prod_q *= 1000; prod_u = 'ml'

    if req_u != prod_u:
        return None
    if req_q >= prod_q:
        return None

    prop = req_q / prod_q
    cents = round(price * prop * 100)
    euros = cents / 100.0
    unit_cost = round((price * 100) / prod_q, 2)
    qty_int = int(req_q) if req_q.is_integer() else req_q
    return f"Proportion: using {qty_int}{req_u} costs Approx ~\u20ac{euros:.2f} ({unit_cost}\u00a2/{req_u})"


def _get_product_price(product):
    """Get the lowest available price for a product across all stores."""
    cheapest = ProductStore.query.filter_by(
        product_id=product.id, is_available=True
    ).order_by(ProductStore.base_price.asc()).first()
    return float(cheapest.base_price) if cheapest and cheapest.base_price else None


def _get_product_cheapest_store(product):
    """Get the store name for the cheapest product-store entry."""
    cheapest = ProductStore.query.filter_by(
        product_id=product.id, is_available=True
    ).order_by(ProductStore.base_price.asc()).first()
    if not cheapest:
        return None
    store = Store.query.filter_by(store_id=cheapest.store_id).first()
    return store.name if store else cheapest.store_id


def match_ingredients_to_products(ingredients):
    """
    Takes a list of generic ingredients, cleans them, and queries the database
    for the top 3 cheapest actual store items for each ingredient.
    """
    results = []
    exclusion_cats = [
        "Snacks", "Beverages", "Household", "Baby food", "Fast Food & To Go",
        "Bakery", "Bread & Bakery", "Ready Meals", "Frozen Meals", "Sweets & Treats",
        "Sweets", "Confectionery", "Desserts", "Ice Cream", "Biscuits", "Cookies",
        "Snacks & Sweets", "Household & Cleaning", "Baby & Kids", "Bakery & Bread"
    ]

    for raw_ing in ingredients:
        search_term = clean_ingredient_term(raw_ing)

        if not search_term:
            search_term = raw_ing

        escaped_search = re.escape(search_term).replace(r"\ ", " ")

        # Query PostgreSQL for products containing this text
        pattern = f"%{search_term}%"
        products = Product.query.filter(
            Product.name_de.ilike(pattern)
        ).order_by(Product.name_de).limit(50).all()

        # Score and sort products
        scored = []
        for p in products:
            name_lower = (p.name_de or "").lower()
            search_lower = search_term.lower()

            exact = 0 if name_lower == search_lower else 1
            starts = 0 if name_lower.startswith(search_lower) else 1

            # Check if category is in exclusion list
            is_junk = 0
            if p.category_id:
                cat = Category.query.get(p.category_id)
                if cat and (cat.name_en or cat.name_de) in exclusion_cats:
                    is_junk = 1

            price = _get_product_price(p)
            if price and price > 0:
                scored.append((exact, starts, is_junk, len(name_lower), price, p))

        # Sort: exact match, starts with, non-junk categories, name length, price
        scored.sort(key=lambda x: (x[0], x[1], x[2], x[3], x[4] if x[4] else float('inf')))

        snack_keywords = ["chocolate", "chip", "cookie", "candy", "drink", "soda", "beer", "wine", "juice", "water", "snack"]
        strict_exclusions = {
            "butter": ["peanut", "almond", "cashew", "cacao", "cocoa", "cookie", "cake", "croissant"],
            "garlic": ["bruschetta", "bread", "baguette", "sauce", "salt", "powder", "paste", "bagel"],
            "salt": ["butter", "chips", "crisps", "peanuts", "nuts", "pretzel", "crackers", "popcorn"],
            "rice": ["cake", "cakes", "cracker", "crisp", "pudding", "noodle"],
            "milk": ["chocolate", "condensed", "biscuit", "cookie"],
            "cheese": ["mozzarella", "parmesan", "cheddar", "gouda", "brie", "swiss", "emmenthal", "ricotta", "feta", "blue", "goat", "cottage", "mascarpone", "provolone", "edam", "camembert", "pecorino", "havarti", "gruyere", "munster", "asiago", "fontina", "halloumi", "paneer", "manchego", "colby", "monterey"],
            "oil": ["chips", "crisps"],
            "water": ["melon"]
        }
        excluded_words = strict_exclusions.get(search_term.lower().strip(), [])

        matches = []
        for score in scored:
            p = score[5]
            # Check category exclusion
            if score[2] == 1 and not any(k in search_term.lower() for k in snack_keywords):
                continue
            # Check strict exclusions
            if any(ew in (p.name_de or "").lower() for ew in excluded_words):
                continue

            price = _get_product_price(p)
            unit = p.unit_normalized or ""
            store = _get_product_cheapest_store(p)

            m_dict = {
                "id": str(p.id),
                "productId": p.fingerprint,
                "name": p.name_de,
                "name_de": p.name_de,
                "brand": p.brand,
                "price": price,
                "price_val": price,
                "store": store,
                "unit": unit,
                "quantity": unit,
                "image": p.default_image_url,
                "defaultImageUrl": p.default_image_url,
            }
            matches.append(m_dict)
            if len(matches) == 3:
                break

        # Fallback: try last word
        if not matches and ' ' in search_term:
            last_word = search_term.split()[-1]
            if len(last_word) >= 3:
                pattern = f"%{last_word}%"
                fallback_products = Product.query.filter(
                    Product.name_de.ilike(pattern)
                ).order_by(Product.name_de).limit(50).all()

                scored_fb = []
                for p in fallback_products:
                    name_lower = (p.name_de or "").lower()
                    last_lower = last_word.lower()
                    exact = 0 if name_lower == last_lower else 1
                    starts = 0 if name_lower.startswith(last_lower) else 1
                    price = _get_product_price(p)
                    if price and price > 0:
                        scored_fb.append((exact, starts, len(name_lower), price, p))

                scored_fb.sort(key=lambda x: (x[0], x[1], x[2], x[3] if x[3] else float('inf')))
                excluded_fb = strict_exclusions.get(last_word.lower(), [])

                for score in scored_fb:
                    p = score[4]
                    if any(ew in (p.name_de or "").lower() for ew in excluded_fb):
                        continue
                    if len(matches) >= 3:
                        break
                    price = _get_product_price(p)
                    unit = p.unit_normalized or ""
                    store = _get_product_cheapest_store(p)
                    m_dict = {
                        "id": str(p.id),
                        "productId": p.fingerprint,
                        "name": p.name_de,
                        "name_de": p.name_de,
                        "brand": p.brand,
                        "price": price,
                        "price_val": price,
                        "store": store,
                        "unit": unit,
                        "quantity": unit,
                        "image": p.default_image_url,
                        "defaultImageUrl": p.default_image_url,
                    }
                    matches.append(m_dict)

        # Add proportional messages
        for m in matches:
            price = m.get('price_val') or m.get('price')
            unit = m.get('unit') or m.get('quantity')
            prop_msg = calculate_proportion_message(raw_ing, unit, price)
            if prop_msg:
                m['proportional_message'] = prop_msg

        results.append({
            "original_request": raw_ing,
            "search_term": search_term,
            "matches": matches
        })

    return results


if __name__ == "__main__":
    from app import app
    test_ig = ["500g tomatoes", "1 yellow onion", "2 cloves garlic", "500ml vegetable broth", "olive oil"]
    print("Testing Matcher...")

    with app.app_context():
        results = match_ingredients_to_products(test_ig)
        for r in results:
            print(f"\n--- {r['original_request']} --> searching '{r['search_term']}' ---")
            for m in r['matches']:
                price = m.get('price_val') or m.get('price')
                print(f"   [\u20ac{price}] {m.get('name')} (Store: {m.get('store', 'Unknown')})")
