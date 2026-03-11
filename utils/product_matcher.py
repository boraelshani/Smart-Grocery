import Levenshtein
from jellyfish import jaro_winkler_similarity # Note: Requires 'jellyfish' package
import re

def fuzzy_match_products(prod1, prod2):
    """
    MODULE 3 - Fuzzy product matcher
    compares normalizedName, extracts and compares brand/size,
    uses Levenshtein distance and Jaro-Winkler similarity.
    """
    norm1 = prod1.get('normalizedName', '')
    norm2 = prod2.get('normalizedName', '')
    
    if not norm1 or not norm2:
        return False, 0.0

    # Basic strict match
    if norm1 == norm2:
        return True, 1.0

    # Check brand and size explicitly
    if prod1.get('brand') and prod2.get('brand') and prod1.get('brand') != prod2.get('brand'):
        return False, 0.0 # Different brands
    
    if prod1.get('size') and prod2.get('size') and prod1.get('size') != prod2.get('size'):
        return False, 0.0 # Different sizes

    # Score calculation
    try:
        jaro_score = jaro_winkler_similarity(norm1, norm2)
    except:
        # Fallback if jellyfish not installed
        jaro_score = 0
        
    max_len = max(len(norm1), len(norm2))
    lev_score = 1 - (Levenshtein.distance(norm1, norm2) / max_len) if max_len > 0 else 0
    
    final_score = (jaro_score * 0.6) + (lev_score * 0.4)
    
    if final_score > 0.85:
        return True, final_score
        
    # Fallback Logic (title similarity 0.75-0.85)
    if 0.75 <= final_score <= 0.85:
        conditions_met = 0
        # Condition 1: Compare category
        if prod1.get('categoryPath') == prod2.get('categoryPath'):
            conditions_met += 1
            
        # Condition 2: Ingredients/Description
        desc1 = set(re.findall(r'\w+', prod1.get('description', '').lower()))
        desc2 = set(re.findall(r'\w+', prod2.get('description', '').lower()))
        if desc1 and desc2 and len(desc1.intersection(desc2)) > 3:
             conditions_met += 1
             
        # Condition 3: Price range
        prices1 = [p.get('price') for p in prod1.get('storePrices', []) if p.get('price')]
        prices2 = [p.get('price') for p in prod2.get('storePrices', []) if p.get('price')]
        if prices1 and prices2:
            avg1 = sum(prices1)/len(prices1)
            avg2 = sum(prices2)/len(prices2)
            if abs(avg1 - avg2) / max(avg1, avg2) < 0.2: # within 20%
                conditions_met += 1
                
        if conditions_met >= 2:
            return True, final_score + 0.1 # Boosted score

    return False, final_score
