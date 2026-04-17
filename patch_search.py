import re

with open('routes/compare/common.py', 'r', encoding='utf-8') as f:
    text = f.read()

old_search = r'''    if search_query:
        search_regex = \{'\$regex': search_query, '\$options': 'i'\}

        # Build the \$or list
        or_list = \[
            \{'name': search_regex\},
            \{'title': search_regex\},
            \{'category': search_regex\},
            \{'stores.store': search_regex\},
            \{'stores.name': search_regex\},
            \{'barcode': search_query\},
            \{'gtin': search_query\},
            \{'ean': search_query\},
            \{'upc': search_query\}
        \]
        import bson
        try:
            if bson.ObjectId.is_valid\(search_query\):
                or_list.append\(\{\'_id': bson.ObjectId\(search_query\)\}\)
        except: pass

        product_query\['\$or'\] = or_list
    total_products = products_model.count_products\(product_query\)
    total_pages = \(total_products \+ per_page - 1\) // per_page if total_products else 1
    page = min\(page, total_pages\) if total_products else 1
    skip_amount = \(page - 1\) \* per_page
    raw_products = products_model.list_products\(query=product_query, skip=skip_amount, limit=per_page\)
'''

new_search = '''    if search_query:
        # Try Atlas Semantic / Vector Search first
        try:
            pipeline = [
                {
                    '$search': {
                        'index': 'default',
                        'text': {
                            'query': search_query,
                            'path': ['name', 'description', 'category', 'stores.store'],
                            'fuzzy': {'maxEdits': 1}
                        }
                    }
                },
                {'$match': query},
                {'$skip': (page - 1) * per_page},
                {'$limit': per_page}
            ]
            from utils.db import mongo
            raw_products = list(mongo.db.products.aggregate(pipeline))
            total_products = len(raw_products) # approximation for search
            total_pages = 1
        except Exception:
            # Fallback to regex if Atlas Search index is missing
            search_regex = {'$regex': search_query, '$options': 'i'}
            or_list = [
                {'name': search_regex},
                {'title': search_regex},
                {'category': search_regex},
                {'stores.store': search_regex},
                {'stores.name': search_regex},
                {'barcode': search_query},
                {'gtin': search_query},
                {'ean': search_query},
                {'upc': search_query}
            ]
            import bson
            try:
                if bson.ObjectId.is_valid(search_query):
                    or_list.append({'_id': bson.ObjectId(search_query)})
            except: pass

            product_query['$or'] = or_list
            total_products = products_model.count_products(product_query)
            total_pages = (total_products + per_page - 1) // per_page if total_products else 1
            page = min(page, total_pages) if total_products else 1
            skip_amount = (page - 1) * per_page
            raw_products = products_model.list_products(query=product_query, skip=skip_amount, limit=per_page)
    else:
        total_products = products_model.count_products(product_query)
        total_pages = (total_products + per_page - 1) // per_page if total_products else 1
        page = min(page, total_pages) if total_products else 1
        skip_amount = (page - 1) * per_page
        raw_products = products_model.list_products(query=product_query, skip=skip_amount, limit=per_page)
'''

# Use an exact string replace mechanism or exact regex:
if 'if search_query:' in text and 'skip_amount = (page - 1) * per_page' in text:
    patched = re.sub(old_search, new_search, text)
    if patched != text:
        with open('routes/compare/common.py', 'w', encoding='utf-8') as f:
            f.write(patched)
        print("Semantic search injected")
    else:
        print("Regex failed to match")
else:
    print("Could not find block")
