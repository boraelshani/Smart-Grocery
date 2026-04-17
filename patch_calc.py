import re

with open('routes/compare/common.py', 'r', encoding='utf-8') as f:
    text = f.read()

new_calc = '''        import itertools
        
        all_stores = set()
        for prod in products:
            for s in prod.get('stores', []):
                if s.get('price') is not None and s.get('store'):
                    all_stores.add(s.get('store'))
                    s['effective_cost'] = calculate_effective_price(prod, float(s.get('price')))

        # Single store calculation
        single_stores = []
        for name in all_stores:
            total = 0.0
            coverage = 0
            for prod in products:
                match = next((s for s in (prod.get('stores') or []) if s.get('store') == name), None)
                if match:
                    total += match['effective_cost']
                    coverage += 1
            if coverage == len(products):
                single_stores.append({'store': name, 'total': round(total, 2)})
        
        single_stores.sort(key=lambda x: x['total'])

        # Two-Stop Shop calculation
        two_stop_options = []
        for s1, s2 in itertools.combinations(all_stores, 2):
            total = 0.0
            coverage = 0
            breakdown = []
            for prod in products:
                matches = [s for s in (prod.get('stores') or []) if s.get('store') in (s1, s2)]
                if not matches:
                    break
                best = min(matches, key=lambda s: s['effective_cost'])
                total += best['effective_cost']
                coverage += 1
                breakdown.append({
                    'product_id': prod.get('id'),
                    'product_name': prod.get('name'),
                    'store': best.get('store'),
                    'price': best.get('price'),
                    'effective_cost': best.get('effective_cost'),
                    'qty': prod.get('requested_qty')
                })
            
            if coverage == len(products):
                two_stop_options.append({
                    'store': f"{s1} + {s2}",
                    'total': round(total, 2),
                    'breakdown': breakdown
                })
        
        two_stop_options.sort(key=lambda x: x['total'])

        # Multi-store (Absolute lowest possible picking from any store)
        mixed_total = 0.0
        mixed_breakdown = []
        for prod in products:
            stores = [s for s in (prod.get('stores') or []) if s.get('price') is not None and s.get('store')]
            if not stores: continue
            best = min(stores, key=lambda s: s.get('effective_cost', float('inf')))
            mixed_total += best.get('effective_cost')
            mixed_breakdown.append({
                'product_id': prod.get('id'),
                'product_name': prod.get('name'),
                'store': best.get('store'),
                'price': best.get('price'),
                'effective_cost': best.get('effective_cost'),
                'qty': prod.get('requested_qty')
            })

        return jsonify({
            'products_count': len(products),
            'mixed': {'total': round(mixed_total, 2), 'breakdown': mixed_breakdown},
            'two_stop_options': two_stop_options[:3],
            'single_store_options': single_stores
        })'''

text = re.sub(
    r'\s+mixed_total = 0\.0; mixed_breakdown = \[\]; single_store_totals = \{\}[\s\S]*?return jsonify\(.*?\}\)',
    '\n' + new_calc,
    text
)

with open('routes/compare/common.py', 'w', encoding='utf-8') as f:
    f.write(text)

print("Split basket applied")