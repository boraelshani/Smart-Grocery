import re

with open("routes/ui/product.py", "r") as f:
    text = f.read()

replacement = """def attach_deals_to_product(product_doc):
    \"\"\"Find deals matching the product and inject them into the stores array.\"\"\"
    if not isinstance(product_doc, dict): return
    store_list = product_doc.get('stores', [])
    if not store_list:
        # If it's a stand-alone deal/offer, wrap it in a store array so it looks like a product
        store_name = product_doc.get('store') or product_doc.get('source')
        if store_name:
            store_entry = {
                'store': store_name,
                'price': product_doc.get('price'),
                'has_deal': True,
                'deal_info': product_doc
            }
            if product_doc.get('original_price'): store_entry['original_price'] = product_doc['original_price']
            if product_doc.get('discount_label'): store_entry['discount_label'] = product_doc['discount_label']
            if product_doc.get('valid_until'): store_entry['valid_until'] = product_doc['valid_until']
            product_doc['stores'] = [store_entry]
        return

    name = product_doc.get('name') or product_doc.get('title')
    if not name: return
    
    try:
        from models.featured_deals_model import featured_deals_model
        # Simple exact name or regex match for deals
        deal = featured_deals_model.collection.find_one({"$or": [{"title": name}, {"name": name}]})
        if not deal:
            # try case-insensitive regex
            deal = featured_deals_model.collection.find_one({"$or": [{"title": {"$regex": f"^{re.escape(name)}$", "$options": "i"}}, {"name": {"$regex": f"^{re.escape(name)}$", "$options": "i"}}]})
        
        if deal:
            deal_store = (deal.get('store') or deal.get('source') or '').lower()
            for s in store_list:
                s_name = (s.get('store') or s.get('name') or '').lower()
                if deal_store and s_name == deal_store:
                    s['has_deal'] = True
                    s['deal_info'] = deal
                    if deal.get('price'): s['price'] = deal['price']
                    if deal.get('original_price'): s['original_price'] = deal['original_price']
                    if deal.get('discount_label'): s['discount_label'] = deal['discount_label']
                    if deal.get('valid_until'): s['valid_until'] = deal['valid_until']
    except Exception as e:
        print("Error attaching deals:", e)

@main_bp.route('/product-info/<product_id>')
@main_bp.route('/product/<product_id>')
def product_detail(product_id):
    \"\"\"Detailed product comparison page.\"\"\"
    product = products_model.get_product_by_id(product_id)
    is_deal_direct = False
    
    if not product:
        # Check deals
        deal = featured_deals_model.get_deal_by_id(product_id) or \
               multibuy_offers_model.get_offer_by_id(product_id) or \
               quantity_discounts_model.get_discount_by_id(product_id)
        if deal:
            # attempt to find master product by name
            name = deal.get('title') or deal.get('name')
            if name:
                matches = products_model.search_by_name(name, limit=1)
                if matches:
                    product = matches[0]
            if not product:
                product = deal
                is_deal_direct = True
    
    if not product:
        return render_template('404.html'), 404
        
    attach_deals_to_product(product)
"""

text = re.sub(r"@main_bp\.route\('/product-info/<product_id>'\).*?if not product:\n        return render_template\('404\.html'\), 404", replacement, text, flags=re.DOTALL)

with open("routes/ui/product.py", "w") as f:
    f.write(text)
