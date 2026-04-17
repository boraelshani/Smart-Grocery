import re

with open('routes/compare/common.py', 'r', encoding='utf-8') as f:
    text = f.read()

old_code = r'''    store_meta = build_store_meta_map\(stores_model.list_stores\(\)\)
    products = \[build_compare_product_payload\(helpers.sanitize_mongo_doc\(p\), store_meta_map=store_meta\) for p in raw_products\]
    return jsonify\((\{
        \'products\': products,
        \'pagination\':.*
    \})\)'''

new_code = '''    store_meta = build_store_meta_map(stores_model.list_stores())
    products = [build_compare_product_payload(helpers.sanitize_mongo_doc(p), store_meta_map=store_meta) for p in raw_products]
    
    sort_param = request.args.get('sort')
    if sort_param == 'unit_price':
        # Strict Unit-Price Normalization Post-Filter sorting
        for p in products:
            p['normalized_unit_price'] = p.get('normalized_unit_price') or float('inf')
        products.sort(key=lambda x: x['normalized_unit_price'])

    return jsonify({
        'products': products,
        'pagination': {'page': page, 'per_page': per_page, 'total_products': total_products, 'total_pages': total_pages, 'has_prev': page > 1, 'has_next': page < total_pages, 'showing_start': ((page-1)*per_page)+1 if total_products else 0, 'showing_end': min(page*per_page, total_products)}
    })'''

patched = re.sub(old_code, new_code, text)
if patched != text:
    with open('routes/compare/common.py', 'w', encoding='utf-8') as f:
        f.write(patched)
    print("Unit Price Sort Added")
else:
    print("Failed to replace unit price sort")
