from utils.product_matcher import normalize_product, smart_product_match

# CASE 1: Emmentaler 400g vs 400g (Should Match)
spar = normalize_product("SPAR Emmentaler 400g", "", "Dairy", raw_unit="400g")
billa = normalize_product("Clever Emmentaler", "", "Dairy", raw_brand="Clever", raw_unit="400g")
res = smart_product_match(spar, billa)
print(f"Match 400g vs 400g: {res['match']} (Score: {res['score']})")

# CASE 2: Emmentaler 400g vs 150g (Should FAIL)
billa_small = normalize_product("Ja! Natürlich Emmentaler", "", "Dairy", raw_brand="Ja! Natürlich", raw_unit="150g")
res_small = smart_product_match(spar, billa_small)
print(f"Match 400g vs 150g: {res_small['match']} (Score: {res_small['score']})")
