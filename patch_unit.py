import re

with open('routes/compare/common.py', 'r', encoding='utf-8') as f:
    text = f.read()

old_search = r'''    skip_amount = \(page - 1\) \* per_page
    raw_products = products_model.list_products\(query=product_query, skip=skip_amount, limit=per_page\)
    store_meta = build_store_meta_map\(stores_model.list_stores\(\)\)
    products = \[build_compare_product_payload\(helpers.sanitize_mongo_doc\(p\), store_meta_map=store_meta\) for p in raw_products\]'''

new_search = '''    skip_amount = (page - 1) * per_page
    sort_by_unit = request.args.get('sort') == 'unit_price'

    from utils.db import mongo
    
    pipeline = [{'$match': product_query}]
    if sort_by_unit:
        # Strict Unit-Price Normalization - sort directly in DB by pre-calculated field or just fetch all and sort
        pipeline.append({'$sort': {'normalized_unit_price': 1}})
    else:
        pipeline.append({'$sort': {'price': 1}})

    pipeline.append({'$skip': skip_amount})
    pipeline.append({'$limit': per_page})
    
    raw_products = list(mongo.db.products.aggregate(pipeline))

    store_meta = build_store_meta_map(stores_model.list_stores())
    products = [build_compare_product_payload(helpers.sanitize_mongo_doc(p), store_meta_map=store_meta) for p in raw_products]
    
    if sort_by_unit:
        # Perform exact strict strict post-sorting if DB lacks the fields populated correctly
        for p in products:
            p['normalized_unit_price'] = p.get('normalized_unit_price', float('inf'))
        products.sort(key=lambda x: x['normalized_unit_price'])
'''

if 'raw_products = products_model.list_products(query=product_query, skip=skip_amount, limit=per_page)' in text:
    patched = re.sub(old_search, new_search, text)
    if patched != text:
        with open('routes/compare/common.py', 'w', encoding='utf-8') as f:
            f.write(patched)
        print("Unit price sorting injected")
    else:
        print("Regex failed to match")
else:
    print("Could not find block")
