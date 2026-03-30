import re
from difflib import SequenceMatcher

STORE_BRAND_GROUPS = ["clever", "s-budget", "ja!", "ja natürlich", "ja natuerlich", "ja naturally", "basic", "milfina", "milbona"]

def normalize_product(raw_title, raw_desc="", raw_category="", raw_brand="", raw_unit=""):
    """
    Normalizer: Extract category, size, brand, and attributes.
    """
    text = f"{raw_title} {raw_desc} {raw_brand} {raw_unit}".lower()
    
    # 1. Evaluate Brand
    brand = "Unknown"
    if raw_brand:
        brand = raw_brand
    else:
        for b in STORE_BRAND_GROUPS:
            if b in text:
                brand = "StoreBrand"
                break
            
    # 2. Use regex to detect sizes: (\d+\.?\d*) ?(L|ml|g|kg)
    # Check raw_unit first as it's more reliable
    size_match = None
    if raw_unit:
        size_match = re.search(r'(\d+\.?\d*)\s?(l|ml|g|kg)', raw_unit.lower())
    
    if not size_match:
        size_match = re.search(r'(\d+\.?\d*)\s?(l|ml|g|kg)', text)
        
    size = None
    unit = None
    if size_match:
        try:
            size = float(size_match.group(1).replace(',', '.'))
            unit = size_match.group(2).lower()
            # standardize everything to grams / milliliters for matching logic
            if unit == 'kg':
                size *= 1000
                unit = 'g'
            elif unit == 'l':
                size *= 1000
                unit = 'ml'
        except:
            pass
            
    # 3. Detect fat percent: (1\.5|3\.2|0\.5)% for fat level
    fat_match = re.search(r'(\d+\.?\d*)\s?%', text)
    fat = None
    if fat_match:
        try:
            fat = float(fat_match.group(1).replace(',', '.'))
        except:
            pass
        
    # 4. Mandatory category constraint: Fresh vs Frozen
    is_frozen = "frozen" in text or "tiefkühl" in text or "gefroren" in text
    is_fresh = "fresh" in text or "frisch" in text
    
    category = raw_category.lower()
    product_state = "neutral"
    if is_frozen and "frozen" not in category:
        category = "frozen " + category
        product_state = "frozen"
    elif is_fresh and "fresh" not in category:
        category = "fresh " + category
        product_state = "fresh"
        
    # Attempt to find an EAN barcode (13 digits) if provided in desc/text
    ean_match = re.search(r'\b\d{13}\b', text)
    ean = ean_match.group(0) if ean_match else None
        
    return {
        "original_title": raw_title,
        "normalized_name": raw_title.lower(),
        "brand": brand,
        "size": size,
        "unit": unit,
        "fat_percent": fat,
        "category": category,
        "state": product_state,
        "ean": ean
    }

def calculate_similarity(a, b):
    return SequenceMatcher(None, a, b).ratio()

def get_category_group(cat):
    cat = cat.lower()
    if any(x in cat for x in ["dairy", "milch", "käse", "joghurt", "butter", "eier"]): return "dairy"
    if any(x in cat for x in ["produce", "obst", "gemüse", "frisch", "fruit", "veg"]): return "produce"
    if any(x in cat for x in ["bakery", "brot", "backwaren", "toast", "gebäck"]): return "bakery"
    if any(x in cat for x in ["frozen", "tiefkühl", "eis"]): return "frozen"
    if any(x in cat for x in ["beverage", "getränke", "wasser", "saft"]): return "beverages"
    if any(x in cat for x in ["pantry", "vorrat", "öl", "nudeln", "reis", "konserven"]): return "pantry"
    if any(x in cat for x in ["household", "haushalt", "papier", "hygiene", "bad"]): return "household"
    return cat

def smart_product_match(prod_a, prod_b):
    """
    Matcher: Core feature.
    Takes two normalized products and scores them.
    Only match if score >= 70.
    """
    # 1️⃣ Extract EAN/Barcode whenever possible (BEST CASE)
    if prod_a.get('ean') and prod_b.get('ean') and prod_a['ean'] == prod_b['ean']:
        return {"match": True, "score": 100, "reason": "EAN Match"}
        
    # Fresh vs Frozen NEVER match
    if prod_a.get('state') != prod_b.get('state') and (prod_a.get('state') != "neutral" and prod_b.get('state') != "neutral"):
        return {"match": False, "score": 0, "reason": "Fresh vs Frozen mismatch"}
        
    score = 0
    
    # + 40 if same category group
    cat_a = get_category_group(prod_a.get('category', ''))
    cat_b = get_category_group(prod_b.get('category', ''))
    if cat_a and cat_b and cat_a == cat_b:
        score += 40
        
    # Brand logic
    brand_a = prod_a.get('brand', 'Unknown')
    brand_b = prod_b.get('brand', 'Unknown')
    
    is_private_a = brand_a.lower() in STORE_BRAND_GROUPS or brand_a == "StoreBrand"
    is_private_b = brand_b.lower() in STORE_BRAND_GROUPS or brand_b == "StoreBrand"
    
    if brand_a != "Unknown" and brand_b != "Unknown":
        if brand_a == brand_b:
            score += 20
        elif is_private_a and is_private_b:
            # Cross-matching store brands (e.g. S-Budget vs Clever) is OK and desired
            score += 15
        else:
            # Specific branded mismatch (e.g. Philadelphia vs Bresso)
            score -= 20 
            
    # + 20 if weight is within ±10%
    if prod_a.get('size') and prod_b.get('size'):
        if prod_a.get('unit') == prod_b.get('unit'):
            diff = abs(prod_a['size'] - prod_b['size']) / max(prod_a['size'], prod_b['size'])
            if diff <= 0.10:
                score += 25 # Increased reward for size match
            else:
                score -= 50 # Heavier penalty for size mismatch (prevents matching 150g with 400g)
        else:
            score -= 20
            
    # + 10 if fat% matches
    if prod_a.get('fat_percent') is not None and prod_b.get('fat_percent') is not None:
        if prod_a['fat_percent'] == prod_b['fat_percent']:
            score += 10
        else:
            score -= 20 # wrong fat percent penalty
            
    # Text similarity logic
    brands = ["s-budget", "clever", "ja! natürlich", "ja natuerlich", "spar", "billa", "hofer", "lidl", "natur*pur"]
    
    def clean_text(t):
        t = t.lower()
        t = re.sub(r'[\d\.\,]+[a-z%]+', '', t)
        for b in brands:
            t = t.replace(b, "")
        t = t.replace("haltbarmilch", "milch")
        t = t.replace("vollmilch", "milch")
        t = t.replace("leichtmilch", "milch")
        t = t.replace("scheiben", "")
        t = re.sub(r'[^a-zäöüß ]+', ' ', t)
        return " ".join(t.split())

    clean_a = clean_text(prod_a['normalized_name'])
    clean_b = clean_text(prod_b['normalized_name'])
    name_sim = calculate_similarity(clean_a, clean_b)
    
    # Keyword Overlap Reward (Specifics)
    keywords = ["milch", "brot", "apfel", "banane", "tomate", "ei", "butter", "joghurt", "pizza", "wasser", "saft", "kaffee", "öl", "nudel", "reis", "mehl", "zucker", "emmentaler", "salami", "gouda", "mozzarella", "toilettenpapier"]
    for k in keywords:
        if k in clean_a and k in clean_b:
            score += 20 # Lowered slightly to prevent false positives
            break

    # Mutual Exclusion (Check for keyword mismatches)
    # If one has 'emmentaler' and other has 'gouda' -> Hard penalty
    mismatch_pairs = [("emmentaler", "gouda"), ("emmentaler", "mozzarella"), ("gouda", "mozzarella"), ("apfel", "birne"), ("orange", "zitrone")]
    for k1, k2 in mismatch_pairs:
        if (k1 in clean_a and k2 in clean_b) or (k2 in clean_a and k1 in clean_b):
            score -= 60 # Hard block

    # Organic (Bio) Sync
    is_bio_a = "bio" in prod_a['normalized_name'].lower() or "natürlich" in prod_a['normalized_name'].lower()
    is_bio_b = "bio" in prod_b['normalized_name'].lower() or "natürlich" in prod_b['normalized_name'].lower()
    
    if is_bio_a == is_bio_b:
        score += 10
    else:
        score -= 30 
    
    if name_sim >= 0.70:
        score += 25
    elif name_sim >= 0.40:
        score += 15
        
    a_words = set(clean_a.split())
    b_words = set(clean_b.split())
    if a_words and b_words and (a_words.issubset(b_words) or b_words.issubset(a_words)):
        score += 15

    # Final threshold
    is_match = score >= 70
    
    needs_review = False
    if 50 <= score < 70:
        needs_review = True
        
    return {
        "match": is_match,
        "score": score,
        "needs_review": needs_review,
        "reason": f"Scored {score}/100 (Sim: {name_sim:.2f} | Bio: {is_bio_a}/{is_bio_b} | A: '{clean_a}' | B: '{clean_b}')"
    }

