from utils.product_matcher import normalize_product, smart_product_match

spar_name = "SPAR Emmentaler Scheiben 400g"
spar_norm = normalize_product(spar_name, "", "Dairy", raw_unit="400g")

billa_name = "Ja! Natürlich Emmentaler Scheiben"
billa_norm = normalize_product(billa_name, "", "Hartkäse", raw_brand="Ja! Natürlich", raw_unit="150g")

billa_name_400 = "Clever Emmentaler Scheiben"
billa_norm_400 = normalize_product(billa_name_400, "", "Hartkäse", raw_brand="Clever", raw_unit="400g")

print(f"SPAR: {spar_norm}")
print(f"BILLA 150g: {billa_norm}")
print(f"BILLA 400g: {billa_norm_400}")

match_150 = smart_product_match(spar_norm, billa_norm)
match_400 = smart_product_match(spar_norm, billa_norm_400)

print(f"\nMatch 150g: {match_150}")
print(f"Match 400g: {match_400}")
