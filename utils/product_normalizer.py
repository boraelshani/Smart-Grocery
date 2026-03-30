import re

def normalize_product_name(raw_name: str) -> str:
    """
    Normalizes a product name by lowercasing, removing punctuation, 
    extracting brand, size, quantity, and removing promotional text.
    """
    if not raw_name:
        return ""
    
    name = raw_name.lower()
    
    # Remove promotional text
    promo_words = [r'-?\d+%', r'discount', r'aktion', r'promo', r'sale', r'angebot']
    for word in promo_words:
        name = re.sub(word, '', name)
        
    # Remove punctuation (keep alphanumeric and spaces)
    name = re.sub(r'[^\w\s]', '', name)
    
    # Clean up extra spaces
    name = ' '.join(name.split())
    
    return name

def extract_size(raw_name: str) -> str:
    """Extracts size like 500g, 1L, etc."""
    match = re.search(r'(\d+(?:\.\d+)?\s*(g|kg|l|ml|oz|lb))', raw_name.lower())
    if match:
        return match.group(0).replace(' ', '')
    return ""

def extract_quantity(raw_name: str) -> str:
    """Extracts quantity like 6-pack, 12x, etc."""
    match = re.search(r'(\d+)\s*(?:pack|x)', raw_name.lower())
    if match:
        return match.group(0)
    return ""

def extract_brand(raw_name: str, known_brands: list = None) -> str:
    """Extracts brand if it matches a known list."""
    if not known_brands:
        known_brands = ['milka', 'coca-cola', 'pepsi', 'nestle', 'knorr', 'maggi', 'red bull']
    
    lower_name = raw_name.lower()
    for brand in known_brands:
        if brand in lower_name:
            return brand.title()
    return ""

def create_unified_product(id, raw_name, description="", category="", store_prices=None, images=None):
    """
    Creates a unified Product model containing:
    id, name, normalizedName, brand, size, quantity, description, 
    category, categoryPath, images[], storePrices[], sourceStore, lastUpdated.
    """
    normalized_name = normalize_product_name(raw_name)
    size = extract_size(raw_name)
    quantity = extract_quantity(raw_name)
    brand = extract_brand(raw_name)
    
    return {
        "id": id,
        "name": raw_name,
        "normalizedName": normalized_name,
        "brand": brand,
        "size": size,
        "quantity": quantity,
        "description": description,
        "category": category,
        "categoryPath": [category] if category else [],
        "images": images or [],
        "storePrices": store_prices or [],
        "sourceStore": None,
        "lastUpdated": None
    }
